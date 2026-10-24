"""
Flood Hazard Module (Module A)
Wraps and integrates Phase 2A/2B/2C flood prediction and inundation services into the common hazard architecture.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.services.hazards.base_hazard import BaseHazardModule
from app.services.flood_hazard_service import FloodHazardService
from app.services.inundation_service import FloodInundationService


class FloodHazardModule(BaseHazardModule):
    def __init__(self):
        super().__init__(
            hazard_id="flood",
            name="Pluvial & Fluvial Flood Intelligence",
            version="EIDT-Flood-v2.3",
            operational_status="OPERATIONAL",
            responsible_authority="MCGM / BMC Disaster Management Department & IMD",
            prediction_target="24-hour locality flood occurrence and topographic depression inundation depth",
            forecast_horizon_hours=24
        )
        self.hazard_service = FloodHazardService()
        self.inundation_service = FloodInundationService()

    def get_status(self) -> Dict[str, Any]:
        st = self.hazard_service.get_status()
        st["hazard_id"] = self.hazard_id
        st["name"] = self.name
        st["version"] = self.version
        st["operational_status"] = self.status
        st["responsible_authority"] = self.responsible_authority
        st["prediction_horizon"] = f"{self.forecast_horizon_hours} Hours"
        st["target_definition"] = self.prediction_target
        st["geographic_coverage"] = "MMR Pilot (10 Municipal Wards), extensible across Maharashtra"
        st["limitations"] = st.get("uninstrumented_inputs_disclaimer", [
            "Predictions reflect statistical locality flood occurrence susceptibility, not building-level inundation depth.",
            "Stormwater drain SCADA telemetry uninstrumented; gravity drainage outfall nominal."
        ])
        return st

    def get_forecast(self, hours: int = 24) -> Dict[str, Any]:
        fc = self.hazard_service.get_forecast(hours=hours)
        fc["hazard_id"] = self.hazard_id
        return fc

    def assess_localities(self) -> List[Dict[str, Any]]:
        return self.hazard_service.assess_localities()

    def get_locality_assessment(self, locality_id: str) -> Optional[Dict[str, Any]]:
        return self.hazard_service.get_locality_assessment(locality_id)

    def get_map_layers(self) -> Dict[str, Any]:
        risk_geojson = self.hazard_service.get_risk_layer_geojson()
        risk_geojson["hazard_id"] = self.hazard_id
        return risk_geojson

    def get_alerts(self) -> List[Dict[str, Any]]:
        raw_alerts = self.hazard_service.get_alerts()
        # Normalize keys for alert manager
        normalized = []
        for a in raw_alerts:
            normalized.append({
                "alert_id": a.get("alert_id"),
                "hazard_type": self.hazard_id,
                "geographic_scope": "MMR_COASTAL_LOWLANDS",
                "severity_level": a.get("severity", "WATCH"),
                "headline": a.get("title", "Flood Intelligence Advisory"),
                "title": a.get("title", "Flood Intelligence Advisory"),
                "description": a.get("description", ""),
                "message": a.get("description", ""),
                "issuing_authority": a.get("source", self.responsible_authority),
                "is_official_warning": a.get("is_official", False),
                "recommended_action": "Avoid underpasses; monitor civic advisories." if a.get("severity") in ["RED", "ORANGE"] else "Routine monsoon monitoring.",
                "protective_action": "Avoid underpasses; monitor civic advisories." if a.get("severity") in ["RED", "ORANGE"] else "Routine monsoon monitoring.",
                "valid_until_utc": a.get("valid_until_utc")
            })
        return normalized

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "hazard_id": self.hazard_id,
            "sources": [
                {
                    "dataset": "Open-Meteo Weather Forecast API",
                    "authority": "Open-Meteo",
                    "resolution": "Hourly / Multi-Model 0.1° (~11km)",
                    "license": "CC-BY 4.0"
                },
                {
                    "dataset": "Copernicus GLO-30 DEM",
                    "authority": "European Space Agency (ESA)",
                    "resolution": "30m spatial resolution",
                    "license": "Copernicus Open Access"
                },
                {
                    "dataset": "Historical Flood Event Registry (2005-2023)",
                    "authority": "MCGM / BMC Disaster Management & Chitale Committee",
                    "resolution": "Locality-level event records",
                    "license": "Government Open Data"
                }
            ],
            "missing_inputs": [
                "Real-time coastal tide gauge telemetry",
                "Stormwater drain SCADA depth telemetry",
                "Continuous 30m hydrological DEM raster (discrete surveyed benchmarks utilized)"
            ]
        }

    def get_validation_results(self) -> Dict[str, Any]:
        ml_eval = self.hazard_service.prediction_engine.get_evaluation_metrics()
        return {
            "hazard_id": self.hazard_id,
            "validation_status": "OPERATIONAL_PLATT_CALIBRATED",
            "metrics": ml_eval.get("metrics", {}),
            "benchmark_events": ["26_JULY_2005", "29_AUG_2017", "02_JULY_2019", "18_JULY_2021"],
            "scientific_limitations": [
                "Calibrated for pluvial/fluvial waterlogging across MMR 10 pilot wards.",
                "Compound tidal backwater is based on nominal astronomical thresholds."
            ]
        }
