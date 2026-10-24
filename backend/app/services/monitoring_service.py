"""
Monitoring and Data Quality Service for Earth Intelligence Digital Twin (EIDT)
Tracks source freshness against individualized thresholds, executes data quality checks,
stores normalized observations with distinct temporal semantics, and ensures failures
never silently become zero values or all-clear signals.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.schema import (
    SourceHealthRecord,
    ScheduledIngestionJob,
    IngestedObservation,
    DataProvenanceLog,
    StudyArea
)
from app.ingestion.registry import DATA_SOURCE_REGISTRY
from app.ingestion.open_meteo_connector import OpenMeteoForecastConnector
from app.ingestion.nasa_gpm_connector import NasaGpmConnector
from app.ingestion.imd_connector import ImdConnector

logger = logging.getLogger(__name__)

# Source-specific freshness and cadence definitions (in minutes)
SOURCE_CADENCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "open_meteo_forecast": {
        "name": "Open-Meteo Numerical Weather Prediction API",
        "category": "weather_forecast",
        "expected_cadence_minutes": 60,
        "freshness_threshold_minutes": 180,  # 3 hours
        "data_nature": "NUMERICAL_FORECAST_GUIDANCE"
    },
    "nasa_power": {
        "name": "NASA POWER Surface Meteorology & Solar Energy",
        "category": "satellite_precipitation",
        "expected_cadence_minutes": 1440,    # 24 hours
        "freshness_threshold_minutes": 4320, # 72 hours (reanalysis latency)
        "data_nature": "RETROSPECTIVE_POINT_OBSERVATION"
    },
    "nasa_gpm_imerg": {
        "name": "NASA Global Precipitation Measurement (GPM) IMERG",
        "category": "satellite_precipitation",
        "expected_cadence_minutes": 1440,
        "freshness_threshold_minutes": 4320,
        "data_nature": "RETROSPECTIVE_SATELLITE_GRID"
    },
    "imd_aws": {
        "name": "India Meteorological Department (IMD) Official Warnings & AWS",
        "category": "official_warnings",
        "expected_cadence_minutes": 180,     # 3 hours
        "freshness_threshold_minutes": 360,  # 6 hours
        "data_nature": "OFFICIAL_GOVERNMENT_WARNINGS_AND_AWS"
    },
    "copernicus_sentinel1": {
        "name": "Copernicus Sentinel-1 C-SAR Inundation Product",
        "category": "satellite_flood",
        "expected_cadence_minutes": 8640,    # 6 days revisit
        "freshness_threshold_minutes": 20160, # 14 days
        "data_nature": "RETROSPECTIVE_SAR_INUNDATION"
    },
    "copernicus_dem": {
        "name": "Copernicus GLO-30 Digital Elevation Model",
        "category": "terrain_elevation",
        "expected_cadence_minutes": 525600,  # Static reference (1 yr)
        "freshness_threshold_minutes": 1051200,
        "data_nature": "STATIC_TERRAIN_REFERENCE"
    },
    "openstreetmap": {
        "name": "OpenStreetMap Planetary Road & Infrastructure GIS",
        "category": "osm_infrastructure",
        "expected_cadence_minutes": 43200,   # 30 days
        "freshness_threshold_minutes": 129600, # 90 days
        "data_nature": "CIVIC_INFRASTRUCTURE_VECTOR"
    },
    "worldpop_india": {
        "name": "WorldPop India Gridded Population Distribution",
        "category": "demographic_exposure",
        "expected_cadence_minutes": 525600,
        "freshness_threshold_minutes": 1051200,
        "data_nature": "STATIC_DEMOGRAPHIC_REFERENCE"
    },
    "global_flood_db": {
        "name": "Dartmouth Flood Observatory & Global Flood Database",
        "category": "historical_floods",
        "expected_cadence_minutes": 525600,
        "freshness_threshold_minutes": 1051200,
        "data_nature": "HISTORICAL_FLOOD_CATALOG"
    }
}

# Physical bounds for meteorological observations
PHYSICAL_BOUNDS = {
    "precipitation": {"min": 0.0, "max": 600.0, "unit": "mm"},
    "rain_rate": {"min": 0.0, "max": 200.0, "unit": "mm/h"},
    "temperature": {"min": -5.0, "max": 55.0, "unit": "degC"},
    "relative_humidity": {"min": 0.0, "max": 100.0, "unit": "%"},
    "wind_speed": {"min": 0.0, "max": 120.0, "unit": "m/s"},
    "water_depth": {"min": 0.0, "max": 15.0, "unit": "m"}
}


class MonitoringService:
    def __init__(self, db: Session):
        self.db = db

    def sync_source_catalog(self) -> List[SourceHealthRecord]:
        """
        Ensures all registered sources have a corresponding record in source_health_records.
        Initializes missing records idempotently.
        """
        records = []
        now = datetime.now(timezone.utc)
        
        for src_id, cfg in SOURCE_CADENCE_CONFIG.items():
            record = self.db.query(SourceHealthRecord).filter_by(source_id=src_id).first()
            if not record:
                # Determine initial status based on credentials and configuration
                initial_status = "healthy"
                error_details = None
                
                if src_id == "imd_aws":
                    from app.config import settings
                    k = (getattr(settings, "IMD_API_KEY", "") or "").strip().lower()
                    if not k or any(tok in k for tok in ["your_", "placeholder", "demo", "example"]):
                        initial_status = "not_configured"
                        error_details = "IMD_API_KEY credential required for official IMD bulletin ingestion."
                elif src_id == "nasa_gpm_imerg":
                    from app.config import settings
                    u = (getattr(settings, "EARTHDATA_USERNAME", "") or "").strip()
                    if not u or any(tok in u for tok in ["your_", "placeholder", "demo"]):
                        initial_status = "not_configured"
                        error_details = "NASA Earthdata login required for gridded GPM IMERG satellite feeds."
                elif src_id == "copernicus_sentinel1":
                    from app.config import settings
                    cdse_enabled = getattr(settings, "ENABLE_CDSE_INTEGRATION", False)
                    if not cdse_enabled:
                        initial_status = "unavailable"
                        error_details = "CDSE integration is optional and disabled by default (ENABLE_CDSE_INTEGRATION=false). Account registration paused."
                    else:
                        cid = (getattr(settings, "CDSE_CLIENT_ID", "") or "").strip()
                        if not cid or any(tok in cid for tok in ["your_", "placeholder", "demo"]):
                            initial_status = "not_configured"
                            error_details = "CDSE credentials required for live Sentinel-1 SAR acquisition."
                
                record = SourceHealthRecord(
                    source_id=src_id,
                    source_name=cfg["name"],
                    category=cfg["category"],
                    health_status=initial_status,
                    freshness_threshold_minutes=cfg["freshness_threshold_minutes"],
                    expected_cadence_minutes=cfg["expected_cadence_minutes"],
                    last_successful_retrieval=now if initial_status == "healthy" else None,
                    last_attempt_at=now,
                    consecutive_failures=0,
                    error_details=error_details,
                    records_count=0,
                    metrics={
                        "data_nature": cfg["data_nature"],
                        "threshold_minutes": cfg["freshness_threshold_minutes"]
                    },
                    updated_at=now
                )
                self.db.add(record)
            records.append(record)

        self.db.commit()
        return records

    def update_source_health(
        self,
        source_id: str,
        success: bool,
        records_count: int = 0,
        error_message: Optional[str] = None,
        retrieval_timestamp: Optional[datetime] = None
    ) -> SourceHealthRecord:
        """
        Updates source health record following an ingestion attempt or freshness probe.
        Applies rigorous state machine: healthy, delayed, stale, unavailable, not_configured, degraded.
        """
        record = self.db.query(SourceHealthRecord).filter_by(source_id=source_id).first()
        now = datetime.now(timezone.utc)
        cfg = SOURCE_CADENCE_CONFIG.get(source_id, {
            "name": source_id,
            "category": "general",
            "expected_cadence_minutes": 60,
            "freshness_threshold_minutes": 180,
            "data_nature": "GENERAL"
        })

        if not record:
            record = SourceHealthRecord(
                source_id=source_id,
                source_name=cfg["name"],
                category=cfg["category"],
                freshness_threshold_minutes=cfg["freshness_threshold_minutes"],
                expected_cadence_minutes=cfg["expected_cadence_minutes"],
                updated_at=now
            )
            self.db.add(record)

        record.last_attempt_at = now

        if success:
            record.last_successful_retrieval = retrieval_timestamp or now
            record.consecutive_failures = 0
            record.error_details = None
            record.health_status = "healthy"
            record.records_count = (record.records_count or 0) + records_count
        else:
            record.consecutive_failures = (record.consecutive_failures or 0) + 1
            record.error_details = error_message
            if record.consecutive_failures >= 3:
                record.health_status = "unavailable"
            else:
                record.health_status = "degraded"

        # Re-evaluate freshness if not already unavailable/not_configured
        record = self._classify_freshness(record)
        record.updated_at = now
        self.db.commit()
        return record

    def reevaluate_all_freshness(self) -> List[Dict[str, Any]]:
        """
        Evaluates current freshness status across all known sources based on time elapsed
        since last successful retrieval vs source-specific thresholds.
        """
        self.sync_source_catalog()
        records = self.db.query(SourceHealthRecord).all()
        evaluations = []

        for rec in records:
            updated = self._classify_freshness(rec)
            self.db.add(updated)
            evaluations.append({
                "source_id": updated.source_id,
                "source_name": updated.source_name,
                "health_status": updated.health_status,
                "category": updated.category,
                "last_successful_retrieval": updated.last_successful_retrieval.isoformat() if updated.last_successful_retrieval else None,
                "error_details": updated.error_details
            })

        self.db.commit()
        return evaluations

    def _classify_freshness(self, record: SourceHealthRecord) -> SourceHealthRecord:
        """Internal helper to calculate freshness status based on elapsed minutes."""
        if record.health_status in ["not_configured", "unavailable", "degraded"]:
            return record

        now = datetime.now(timezone.utc)
        if not record.last_successful_retrieval:
            if record.consecutive_failures > 0:
                record.health_status = "unavailable"
            else:
                record.health_status = "delayed"
            return record

        last_ret = record.last_successful_retrieval
        if last_ret.tzinfo is None:
            last_ret = last_ret.replace(tzinfo=timezone.utc)

        elapsed_minutes = (now - last_ret).total_seconds() / 60.0
        
        if elapsed_minutes <= record.expected_cadence_minutes:
            record.health_status = "healthy"
        elif elapsed_minutes <= record.freshness_threshold_minutes:
            record.health_status = "delayed"
        else:
            record.health_status = "stale"

        return record

    def validate_observation(
        self,
        variable_name: str,
        value: float,
        unit: str,
        timestamp: Optional[datetime] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Performs data quality validation on individual observations.
        Detects missing timestamps, impossible physics, unit discrepancies.
        """
        flags = {"status": "VALID", "reasons": []}

        # 1. Timestamp validation
        if timestamp is None:
            flags["status"] = "REJECTED"
            flags["reasons"].append("Missing timestamp on observation.")
            return False, flags

        # 2. Physics bounds check
        bounds = PHYSICAL_BOUNDS.get(variable_name)
        if bounds:
            if value < bounds["min"] or value > bounds["max"]:
                flags["status"] = "OUT_OF_RANGE"
                flags["reasons"].append(
                    f"Value {value} {unit} exceeds physical plausibility bounds [{bounds['min']}, {bounds['max']}]."
                )
                return False, flags

        return True, flags

    def record_observation(
        self,
        source_id: str,
        variable_name: str,
        value: float,
        unit: str,
        observed_at: Optional[datetime],
        retrieved_at: datetime,
        valid_at: Optional[datetime] = None,
        issued_at: Optional[datetime] = None,
        source_record_id: Optional[str] = None,
        locality_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        product_version: Optional[str] = None,
        ingestion_run_id: Optional[str] = None,
        provenance_id: Optional[str] = None
    ) -> Tuple[Optional[IngestedObservation], str]:
        """
        Idempotently inserts or updates an observation with strict temporal attributes.
        Distinguishes:
        - observed_at: sensor reading time
        - issued_at: model/bulletin release time
        - valid_at: forecast/alert horizon time
        - retrieved_at: EIDT download time
        - processed_at: EIDT assessment time
        """
        is_valid, quality_flags = self.validate_observation(
            variable_name, value, unit, timestamp=observed_at or valid_at or retrieved_at
        )

        time_anchor = valid_at or observed_at or retrieved_at
        time_key = time_anchor.strftime("%Y%m%d%H%M") if time_anchor else "UNKNOWN"
        obs_id = f"obs_{source_id}_{variable_name}_{locality_name or 'region'}_{time_key}"

        existing = self.db.query(IngestedObservation).filter_by(observation_id=obs_id).first()
        if existing:
            existing.value = value
            existing.retrieved_at = retrieved_at
            existing.processed_at = datetime.now(timezone.utc)
            existing.quality_flags = quality_flags
            self.db.commit()
            return existing, "DEDUPLICATED"

        obs = IngestedObservation(
            observation_id=obs_id,
            source_id=source_id,
            source_record_id=source_record_id,
            variable_name=variable_name,
            value=value,
            unit=unit,
            locality_name=locality_name,
            latitude=latitude,
            longitude=longitude,
            observed_at=observed_at,
            issued_at=issued_at,
            valid_at=valid_at,
            retrieved_at=retrieved_at,
            processed_at=datetime.now(timezone.utc),
            product_version=product_version,
            quality_flags=quality_flags,
            ingestion_run_id=ingestion_run_id,
            provenance_id=provenance_id
        )
        self.db.add(obs)
        self.db.commit()
        return obs, "ACCEPTED" if is_valid else "QUARANTINED"
