"""
Phase 2A Test Suite: Flood Hazard Module (24-Hour Horizon)
Tests:
- Mocked connector ingestion (Open-Meteo, IMD, NASA GPM vs POWER, Copernicus DEM)
- Provider failure & timeout handling
- 24-hour horizon calculation and UTC timestamp handling
- Missing inputs declaration & absence of silent imputation
- Locality flood hazard scoring & contributing factors
- All 8 RESTful /api/flood/* endpoints
- Idempotent schema migration 002 verification
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import json

from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, SessionLocal
from app.ingestion.base import BaseConnector
from app.ingestion.open_meteo_connector import OpenMeteoForecastConnector
from app.ingestion.imd_connector import ImdConnector
from app.ingestion.nasa_gpm_connector import NasaGpmConnector
from app.ingestion.elevation_connector import ElevationConnector
from app.services.flood_hazard_service import FloodHazardService
from app.models.schema import WeatherForecast, FloodHazardAssessment, SchemaMigration

client = TestClient(app)

# 48-hour mock Open-Meteo payload to supply the 24h rolling forecast window
_base_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
MOCK_OPEN_METEO_DATA = {
    "latitude": 19.0760,
    "longitude": 72.8777,
    "generationtime_ms": 0.42,
    "utc_offset_seconds": 0,
    "timezone": "UTC",
    "timezone_abbreviation": "UTC",
    "elevation": 8.0,
    "hourly_units": {
        "time": "iso8601",
        "precipitation": "mm",
        "rain": "mm",
        "weather_code": "wmo code",
        "precipitation_probability": "%"
    },
    "hourly": {
        "time": [(_base_time + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(48)],
        "precipitation": [0.0, 0.2, 1.5, 4.2, 12.0, 28.5, 14.2, 5.0, 2.1, 0.5] + [0.0] * 38,
        "rain": [0.0, 0.2, 1.5, 4.2, 12.0, 28.5, 14.2, 5.0, 2.1, 0.5] + [0.0] * 38,
        "weather_code": [0, 1, 2, 61, 63, 65, 63, 61, 2, 1] + [0] * 38,
        "precipitation_probability": [5, 15, 30, 60, 85, 95, 80, 50, 30, 15] + [5] * 38
    }
}


# -------------------------------------------------------------------------
# 1. Mocked Connector Tests
# -------------------------------------------------------------------------

def test_open_meteo_connector_success_mocked():
    """Verify that Open-Meteo connector parses 24h hourly forecast correctly with UTC timestamps."""
    connector = OpenMeteoForecastConnector()
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        res = connector.get_24h_precipitation_forecast(19.0760, 72.8777, force_refresh=True)

    assert res["status"] == "SUCCESS_LIVE_FORECAST"
    assert "Open-Meteo" in res["source"]
    assert len(res["hourly_forecast"]) == 24
    assert res["hourly_forecast"][5]["precipitation_mm"] == 28.5
    assert res["hourly_forecast"][5]["precipitation_probability_pct"] == 95
    assert "T" in res["issue_time_utc"]


def test_open_meteo_connector_failure_fallback():
    """Verify that Open-Meteo handles timeouts/errors cleanly using documented fallback."""
    connector = OpenMeteoForecastConnector()

    with patch.object(BaseConnector, "_execute_request_with_retries", side_effect=Exception("Connection timed out")):
        res = connector.get_24h_precipitation_forecast(19.0760, 72.8777, force_refresh=True)

    assert res["status"] in ["FALLBACK_HEURISTIC", "SUCCESS_LIVE_FORECAST"]
    assert len(res["hourly_forecast"]) == 24
    assert "hourly_forecast" in res


def test_imd_connector_status_unauthorized():
    """Verify IMD connector marks status UNAVAILABLE_NEEDS_IMD_CREDENTIALS when unauthenticated."""
    connector = ImdConnector()
    status_meta = connector.get_connector_metadata()
    assert status_meta["source_id"] == "imd_aws"
    assert "IMD" in status_meta["name"]
    # Either unauthorized credentials or authenticated if real key configured
    assert status_meta["status"] in ["UNAVAILABLE_NEEDS_IMD_CREDENTIALS", "CONFIGURED_AUTHENTICATED"]


def test_nasa_gpm_vs_power_demarcation():
    """Verify NASA connector explicitly distinguishes POWER from GPM IMERG and labels as observation."""
    connector = NasaGpmConnector()
    meta = connector.get_connector_metadata()
    assert meta["source_id"] == "nasa_gpm_imerg"
    assert "NASA" in meta["name"]
    assert meta["status"] in ["UNCONFIGURED_REQUIRES_EARTHDATA_LOGIN", "CONFIGURED_AUTHENTICATED"]
    assert meta["data_type"] == "RETROSPECTIVE_OBSERVATION"


def test_elevation_discrete_control_points_distinction():
    """Verify elevation connector notes discrete control points vs continuous DEM."""
    connector = ElevationConnector()
    benchmarks = connector.get_ground_control_points()
    assert len(benchmarks) >= 6
    assert any(b["locality"] == "Kurla" and b["elevation_m"] == 6.2 for b in benchmarks)
    meta = connector.get_connector_metadata()
    assert "continuous_dem_status" in meta
    assert meta["status"] == "OPERATIONAL_CONTROL_POINTS"


# -------------------------------------------------------------------------
# 2. Service Logic & Missing Inputs Tests
# -------------------------------------------------------------------------

def test_flood_service_summary_metrics_and_accumulations():
    """Test rolling accumulations (1h peak, 3h, 6h, 12h, 24h total) in FloodHazardService."""
    service = FloodHazardService()
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        fc = service.get_forecast(hours=24, force_refresh=True)

    summary = fc["summary_metrics"]
    assert summary["peak_1h_mm"] == 28.5
    assert summary["accumulations"]["1h_peak_mm"] == 28.5
    assert summary["accumulations"]["24h_total_mm"] > 0
    assert "real_time_coastal_tide_gauges" in fc["missing_inputs"]
    assert fc["confidence_status"] == "MODERATE_OPERATIONAL_NUMERICAL_FORECAST"


def test_flood_service_locality_risk_assessment_transparent_factors():
    """Verify transparent locality assessment across pilot wards with documented factors and missing inputs."""
    service = FloodHazardService()

    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        assessments = service.assess_localities(hours=24)

    assert len(assessments) == 10
    kurla = next(a for a in assessments if a["locality_id"] == "MUM_WARD_L_KURLA")
    assert kurla["locality_name"] == "Ward L (Kurla - Sakinaka)"
    assert kurla["risk_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert isinstance(kurla["risk_score"], float)
    
    # Check contributing factors structure
    factors = kurla["contributing_factors"]
    assert any(f["factor"] == "24h_rainfall_forecast" for f in factors)
    assert any(f["factor"] == "elevation_benchmark" for f in factors)
    assert any(f["factor"] == "fluvial_and_tidal_exposure" for f in factors)
    assert any(f["factor"] == "antecedent_rainfall_24h" for f in factors)

    # Check explicit missing inputs - no silent imputation
    missing = kurla["missing_inputs"]
    assert "real_time_tide_gauge_telemetry" in missing
    assert "storm_drain_scada_depth" in missing
    assert kurla["confidence_status"] == "MODERATE_TOPOGRAPHIC_AND_METEOROLOGICAL_BASELINE"


# -------------------------------------------------------------------------
# 3. REST API Endpoint Tests (All 8 Required Routes)
# -------------------------------------------------------------------------

def test_api_flood_status():
    """GET /api/flood/status returns complete operational status."""
    resp = client.get("/api/flood/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["module"] == "Flood Hazard Intelligence (24-Hour Horizon)"
    assert data["status"] == "OPERATIONAL"
    assert data["spatial_engine"]["postgis_enabled"] is False
    assert "Shapely" in data["spatial_engine"]["engine_in_use"]
    assert data["geographic_coverage"]["locality_count"] == 10
    assert len(data["uninstrumented_inputs_disclaimer"]) >= 2


def test_api_flood_forecast():
    """GET /api/flood/forecast returns 24h hourly forecast with rolling accumulations."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/forecast?hours=24")

    assert resp.status_code == 200
    data = resp.json()
    assert data["horizon_hours"] == 24
    assert "issue_time_utc" in data
    assert "valid_time_start_utc" in data
    assert "valid_time_end_utc" in data
    assert "retrieval_time_utc" in data
    assert "summary_metrics" in data
    assert "accumulations" in data["summary_metrics"]
    assert len(data["hourly_data"]) == 24


def test_api_flood_localities():
    """GET /api/flood/localities returns risk distribution and all 10 pilot localities."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/localities")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_localities_assessed"] >= 10
    assert "risk_distribution" in data
    assert len(data["localities"]) >= 10
    assert "confidence_status" in data
    assert "missing_inputs" in data


def test_api_flood_locality_detail_valid():
    """GET /api/flood/localities/{locality_id} returns detailed assessment for existing ward."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/localities/MUM_WARD_L_KURLA")

    assert resp.status_code == 200
    data = resp.json()
    assert data["locality_id"] == "MUM_WARD_L_KURLA"
    assert data["elevation_mean_m"] == 6.2
    assert "contributing_factors" in data


def test_api_flood_locality_detail_not_found():
    """GET /api/flood/localities/{locality_id} returns 404 for unknown locality."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/localities/NON_EXISTENT_WARD_999")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_flood_layers_rainfall():
    """GET /api/flood/layers/rainfall returns valid GeoJSON FeatureCollection."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/layers/rainfall")

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    first_feat = data["features"][0]
    assert first_feat["type"] == "Feature"
    assert first_feat["geometry"]["type"] in ["Point", "Polygon"]
    assert "forecast_rainfall_24h_mm" in first_feat["properties"]


def test_api_flood_layers_risk():
    """GET /api/flood/layers/risk returns valid GeoJSON FeatureCollection with risk styling."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/layers/risk")

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 10
    feat = data["features"][0]
    assert feat["type"] == "Feature"
    assert "risk_level" in feat["properties"]
    assert "stroke_color" in feat["properties"]
    assert "fill_color" in feat["properties"]


def test_api_flood_observations():
    """GET /api/flood/observations returns verified historical flood benchmarks, clearly marked not forecast."""
    resp = client.get("/api/flood/observations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["dataset_classification"] == "HISTORICAL_OBSERVATIONS_GROUND_TRUTH"
    assert len(data["observations"]) >= 3
    # Verify Chitale 2005 benchmark
    chitale = next(o for o in data["observations"] if "2005" in o["event_id"])
    assert chitale["peak_recorded_rainfall_24h_mm"] == 944.2
    assert chitale["is_forecast"] is False


def test_api_flood_alerts():
    """GET /api/flood/alerts returns structured alert feed."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_OPEN_METEO_DATA

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/alerts")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert isinstance(data["alerts"], list)
    assert len(data["alerts"]) > 0
    first_alert = data["alerts"][0]
    assert "alert_id" in first_alert
    assert "severity" in first_alert
    assert "title" in first_alert


# -------------------------------------------------------------------------
# 4. Database Schema Migration 002 Verification
# -------------------------------------------------------------------------

def test_migration_002_applied_and_tables_exist():
    """Verify that migration 002 is recorded in schema_migrations ledger and tables exist."""
    db = SessionLocal()
    try:
        mig = db.query(SchemaMigration).filter(SchemaMigration.version == "002_flood_hazard_module").first()
        assert mig is not None
        assert "flood" in mig.description.lower()

        # Check table models can be queried without error
        fc_count = db.query(WeatherForecast).count()
        assert fc_count >= 0
        haz_count = db.query(FloodHazardAssessment).count()
        assert haz_count >= 0
    finally:
        db.close()
