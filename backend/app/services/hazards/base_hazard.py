"""
Base Hazard Module Architecture (EIDT Phase 3)
Establishes the common contract and lifecycle interfaces for all disaster hazard categories:
Flood, Heatwave, Landslide, Drought, Coastal, and Thunderstorm.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class BaseHazardModule(ABC):
    """
    Abstract contract for all multi-hazard modules in Maharashtra Digital Twin.
    Ensures consistent metadata, provenance, risk thresholds, and lifecycle tracking.
    """

    def __init__(
        self,
        hazard_id: str,
        name: str,
        version: str,
        operational_status: str,  # OPERATIONAL, EVALUATED, EXPERIMENTAL, UNAVAILABLE_INSUFFICIENT_DATA
        responsible_authority: str,
        prediction_target: str,
        forecast_horizon_hours: int = 24
    ):
        self.hazard_id = hazard_id
        self.name = name
        self.version = version
        self.status = operational_status
        self.responsible_authority = responsible_authority
        self.prediction_target = prediction_target
        self.forecast_horizon_hours = forecast_horizon_hours

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Returns module status, coverage, resolution, and input freshness."""
        pass

    @abstractmethod
    def get_forecast(self, hours: int = 24) -> Dict[str, Any]:
        """Returns forecast products and timelines where supported."""
        pass

    @abstractmethod
    def assess_localities(self) -> List[Dict[str, Any]]:
        """Returns standardized locality assessments across supported administrative wards/districts."""
        pass

    @abstractmethod
    def get_locality_assessment(self, locality_id: str) -> Optional[Dict[str, Any]]:
        """Returns in-depth diagnostic assessment for a specific locality or district."""
        pass

    @abstractmethod
    def get_map_layers(self) -> Dict[str, Any]:
        """Returns GeoJSON FeatureCollection of spatial hazard extents or risk zones."""
        pass

    @abstractmethod
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Returns active and candidate alerts for this hazard type."""
        pass

    @abstractmethod
    def get_provenance(self) -> Dict[str, Any]:
        """Returns traceable dataset sources, CRS, native resolutions, and licences."""
        pass

    @abstractmethod
    def get_validation_results(self) -> Dict[str, Any]:
        """Returns empirical validation metrics, sample sizes, and known limitations."""
        pass

    def build_meta_summary(self) -> Dict[str, Any]:
        """Standardized JSON summary across all hazards."""
        prov = self.get_provenance()
        sources = [s.get("dataset", s.get("dataset_name", "Source")) for s in prov.get("sources", prov.get("datasets", []))]
        return {
            "hazard_id": self.hazard_id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "operational_status": self.status,
            "prediction_target": self.prediction_target,
            "target_definition": self.prediction_target,
            "prediction_horizon": f"{self.forecast_horizon_hours} Hours",
            "forecast_horizon_hours": self.forecast_horizon_hours,
            "responsible_authority": self.responsible_authority,
            "coverage": "MMR Pilot (10 Municipal Wards), extensible across Maharashtra",
            "verified_data_sources": sources,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
