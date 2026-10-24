"""
India Meteorological Department (IMD) Connector (Connector 7)
Follows official IMD National API Portal specifications:
Reference: https://api.imd.gov.in/public/api_reference.html
Official endpoints:
- District-wise Warnings: https://api.imd.gov.in/api/v1/districtwarning
- District-wise Nowcast: https://api.imd.gov.in/api/v1/districtnowcast
- City Forecast: https://api.imd.gov.in/api/v1/cityforecast

Security & Compliance:
- If IMD API key is absent or unauthorized (HTTP 401), the connector is marked UNAVAILABLE.
- Undocumented endpoints are NOT scraped and synthetic warnings are NEVER invented.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.ingestion.base import BaseConnector

logger = logging.getLogger(__name__)

class ImdConnector(BaseConnector):
    def __init__(self):
        super().__init__("imd_aws")
        self.api_base = "https://api.imd.gov.in/api/v1"
        self.district_warning_endpoint = f"{self.api_base}/districtwarning"
        self.district_nowcast_endpoint = f"{self.api_base}/districtnowcast"
        self.city_forecast_endpoint = f"{self.api_base}/cityforecast"
        self.reference_doc = "https://api.imd.gov.in/public/api_reference.html"

    def get_connector_status(self) -> Dict[str, Any]:
        """Returns official IMD authentication and connector availability state."""
        k = (self.config.IMD_API_KEY or "").strip().lower()
        is_placeholder = any(token in k for token in ["your_", "placeholder", "demo", "example"])
        has_key = bool(k and not is_placeholder)
        return {
            "source_id": "imd_aws",
            "name": "India Meteorological Department (IMD) Official API",
            "reference_url": self.reference_doc,
            "status": "CONFIGURED_AUTHENTICATED" if has_key else "UNAVAILABLE_NEEDS_IMD_CREDENTIALS",
            "auth_required": True,
            "credentials_present": has_key,
            "endpoints": {
                "district_warning": self.district_warning_endpoint,
                "district_nowcast": self.district_nowcast_endpoint,
                "city_forecast": self.city_forecast_endpoint
            },
            "policy": "Official Ministry of Earth Sciences (MoES) API only; no undocumented scraping or synthetic warnings."
        }

    def fetch_data(self) -> Dict[str, Any]:
        """
        Attempts retrieval from official IMD API endpoints.
        Marks connector unavailable if credentials are not configured or rejected.
        """
        api_key = self.config.IMD_API_KEY

        if not api_key:
            return {
                "data": {
                    "status": "UNAVAILABLE_NEEDS_IMD_CREDENTIALS",
                    "message": "Official IMD API credentials (IMD_API_KEY) not set in environment.",
                    "reference": self.reference_doc,
                    "warnings": [],
                    "retrieved_at": datetime.now(timezone.utc).isoformat()
                },
                "is_demo_fallback": False,
                "is_available": False,
                "details": f"IMD API requires official key from {self.reference_doc}. Connector safely marked unavailable."
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "EIDT-Mumbai-DigitalTwin/1.0"
        }

        try:
            # Query Mumbai suburban (District 573 or Mumbai City)
            resp = self._execute_request_with_retries(
                self.district_warning_endpoint,
                headers=headers,
                method="GET"
            )
            data = resp.json()

            raw_file = os.path.join(self.raw_dir, "imd_official_warnings_raw.json")
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            return {
                "data": data,
                "is_demo_fallback": False,
                "is_available": True,
                "details": "Successfully retrieved official IMD district warnings."
            }
        except Exception as e:
            logger.warning(f"Official IMD API request failed ({e}). Marking connector unavailable.")
            return {
                "data": {
                    "status": "UNAVAILABLE_API_ERROR",
                    "error": str(e),
                    "reference": self.reference_doc,
                    "warnings": [],
                    "retrieved_at": datetime.now(timezone.utc).isoformat()
                },
                "is_demo_fallback": False,
                "is_available": False,
                "details": f"IMD API connection failed: {e}. Undocumented fallback avoided."
            }

    def preprocess_data(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        data = raw_result.get("data", {})
        output_path = os.path.join(self.processed_dir, "imd_mumbai_official.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {
            "count": len(data.get("warnings", [])),
            "output_path": output_path,
            "status": data.get("status", "UNAVAILABLE"),
            "details": raw_result.get("details", "IMD data connector processed.")
        }

    def get_connector_metadata(self) -> Dict[str, Any]:
        """Alias returning comprehensive connector status and metadata."""
        return self.get_connector_status()

    def get_district_warnings(self, state: str = "Maharashtra", district: str = "Mumbai") -> Dict[str, Any]:
        """Retrieves verified warnings or reports explicit unavailable status."""
        raw = self.fetch_data()
        data = raw.get("data", {})
        return {
            "status": data.get("status", "UNAVAILABLE_NEEDS_IMD_CREDENTIALS"),
            "warnings": data.get("warnings", []),
            "retrieved_at": data.get("retrieved_at")
        }

