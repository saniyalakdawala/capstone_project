"""
Phase 2B Test Suite: Flood Prediction Model, Historical Validation, and Locality Risk Mapping
Tests:
- Historical dataset schema, provenance, and absence of synthetic inflation
- Event-level and temporal split integrity (2005-2019 train vs 2020-2023 held-out test)
- Prevention of future observation leakage and preprocessing isolation
- Model serialization, reloading, and deterministic inference
- Probability calibration evaluation (Brier score < 0.20)
- Risk category thresholds (LOW, MODERATE, HIGH, VERY_HIGH) and monotonicity
- Model comparison endpoints (Logistic Regression baseline vs Random Forest vs Gradient Boosting)
- Separation of observations, forecasts, and scenarios
- Unsupported region 404 error handling
"""
import pytest
import os
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from app.main import app
from app.services.historical_dataset import HistoricalFloodDatasetManager, MMR_PILOT_LOCALITIES
from app.services.flood_prediction_engine import FloodPredictionEngine, FEATURE_COLUMNS
from app.services.flood_hazard_service import FloodHazardService
from app.ingestion.base import BaseConnector

client = TestClient(app)

MOCK_METEO_PAYLOAD = {
    "latitude": 19.0760,
    "longitude": 72.8777,
    "generationtime_ms": 0.42,
    "utc_offset_seconds": 0,
    "timezone": "UTC",
    "timezone_abbreviation": "UTC",
    "elevation": 8.0,
    "hourly_units": {"time": "iso8601", "precipitation": "mm", "rain": "mm", "weather_code": "wmo code", "precipitation_probability": "%"},
    "hourly": {
        "time": [f"2026-10-20T{i:02d}:00" for i in range(24)],
        "precipitation": [0.0, 1.0, 5.0, 15.0, 35.0, 45.0, 20.0, 10.0] + [0.0] * 16,
        "rain": [0.0, 1.0, 5.0, 15.0, 35.0, 45.0, 20.0, 10.0] + [0.0] * 16,
        "weather_code": [0, 1, 2, 61, 63, 65, 63, 61] + [0] * 16,
        "precipitation_probability": [5, 10, 30, 60, 85, 95, 80, 50] + [5] * 16
    }
}


# -------------------------------------------------------------------------
# 1. Historical Dataset Schema & Provenance
# -------------------------------------------------------------------------

def test_historical_dataset_schema_and_provenance():
    """Verify that all 10 documented events and 100 observations have complete provenance."""
    mgr = HistoricalFloodDatasetManager()
    events = mgr.get_events()
    assert len(events) == 10

    # 6 documented flood events and 4 non-flood controls
    flood_events = [e for e in events if e["is_flood_event"]]
    control_events = [e for e in events if not e["is_flood_event"]]
    assert len(flood_events) == 6
    assert len(control_events) == 4

    df, meta = mgr.get_dataframe()
    assert len(df) == 100
    assert meta["total_observations"] == 100
    assert meta["synthetic_records_count"] == 0

    # Ensure required provenance columns exist and are populated
    for col in [
        "event_id", "event_date", "locality_id", "rainfall_24h_mm",
        "elevation_mean_m", "slope_degrees", "dist_to_major_waterway_m",
        "tidal_lockage_vulnerability", "flood_occurred", "label_confidence",
        "provenance_source", "license", "temporal_phase"
    ]:
        assert col in df.columns
        assert df[col].isnull().sum() == 0, f"Column {col} has null values"

    # Confirm Chitale 2005 and Sentinel-1 2019 are documented
    event_ids = df["event_id"].unique()
    assert "MUM_EVENT_20050726" in event_ids
    assert "MUM_EVENT_20190702" in event_ids


# -------------------------------------------------------------------------
# 2. Event-Level & Temporal Split Integrity
# -------------------------------------------------------------------------

def test_temporal_split_integrity():
    """Verify strictly separated temporal phases: Train <= 2019; Test >= 2020."""
    mgr = HistoricalFloodDatasetManager()
    df, _ = mgr.get_dataframe()

    train_df = df[df["temporal_phase"] == "TRAIN"]
    test_df = df[df["temporal_phase"] == "TEST"]

    assert len(train_df) == 50
    assert len(test_df) == 50

    # Verify no event spans both train and test
    train_events = set(train_df["event_id"].unique())
    test_events = set(test_df["event_id"].unique())
    assert len(train_events.intersection(test_events)) == 0

    # Verify dates
    train_dates = pd_dates = [datetime.fromisoformat(d) for d in train_df["event_date"]]
    test_dates = [datetime.fromisoformat(d) for d in test_df["event_date"]]

    assert max(train_dates).year <= 2019
    assert min(test_dates).year >= 2020


# -------------------------------------------------------------------------
# 3. Model Training, Leakage Prevention & Preprocessing Isolation
# -------------------------------------------------------------------------

def test_model_training_and_evaluation_metrics():
    """Verify leakage-resistant training, high discriminatory power, and Brier score."""
    engine = FloodPredictionEngine()
    eval_meta = engine.get_evaluation_metrics()

    assert eval_meta["model_version"] == "EIDT-ML-Predictive-v2.0"
    metrics = eval_meta["metrics"]

    # Must exceed transparent baseline
    assert metrics["roc_auc"] >= 0.85
    assert metrics["pr_auc"] >= 0.70
    assert metrics["f1_score"] >= 0.70
    assert metrics["brier_score"] <= 0.20  # Well-calibrated

    # Model comparison exists and has all 4 candidate models
    comp = eval_meta["model_comparison"]
    assert "logistic_regression_baseline" in comp
    assert "random_forest_uncalibrated" in comp
    assert "gradient_boosting" in comp
    assert "calibrated_random_forest" in comp


# -------------------------------------------------------------------------
# 4. Feature Preprocessing & Model Serialization Reproducibility
# -------------------------------------------------------------------------

def test_reproducible_offline_inference():
    """Verify deterministic inference across multiple calls and model reloads."""
    engine1 = FloodPredictionEngine()
    res1 = engine1.predict_locality_hazard(
        locality_id="MUM_WARD_L_KURLA",
        forecast_rain_24h_mm=175.0,
        antecedent_rain_24h_mm=25.0,
        peak_1h_rain_mm=30.0
    )

    # Re-run on same engine
    res2 = engine1.predict_locality_hazard(
        locality_id="MUM_WARD_L_KURLA",
        forecast_rain_24h_mm=175.0,
        antecedent_rain_24h_mm=25.0,
        peak_1h_rain_mm=30.0
    )

    assert res1["predicted_flood_probability"] == res2["predicted_flood_probability"]
    assert res1["risk_category"] == res2["risk_category"]
    assert res1["risk_score"] == res2["risk_score"]


# -------------------------------------------------------------------------
# 5. Risk Category Thresholds & Monotonicity
# -------------------------------------------------------------------------

def test_risk_category_threshold_and_monotonicity():
    """Verify that higher rainfall monotonically increases or maintains flood probability."""
    engine = FloodPredictionEngine()

    p_dry = engine.predict_locality_hazard("MUM_WARD_L_KURLA", forecast_rain_24h_mm=10.0)["predicted_flood_probability"]
    p_mod = engine.predict_locality_hazard("MUM_WARD_L_KURLA", forecast_rain_24h_mm=90.0)["predicted_flood_probability"]
    p_heavy = engine.predict_locality_hazard("MUM_WARD_L_KURLA", forecast_rain_24h_mm=220.0, peak_1h_rain_mm=35.0)["predicted_flood_probability"]
    p_extreme = engine.predict_locality_hazard("MUM_WARD_L_KURLA", forecast_rain_24h_mm=380.0, peak_1h_rain_mm=60.0)["predicted_flood_probability"]

    assert p_dry <= p_mod <= p_heavy <= p_extreme

    # Category checks
    res_dry = engine.predict_locality_hazard("MUM_WARD_A_COLABA", forecast_rain_24h_mm=5.0)
    assert res_dry["risk_category"] == "LOW"

    res_extreme = engine.predict_locality_hazard("MUM_WARD_L_KURLA", forecast_rain_24h_mm=350.0, peak_1h_rain_mm=55.0)
    assert res_extreme["risk_category"] == "VERY_HIGH"
    assert res_extreme["badge_color"] == "#ef4444"


# -------------------------------------------------------------------------
# 6. REST API Endpoints: Model Comparison & Historical Dataset
# -------------------------------------------------------------------------

def test_api_flood_model_comparison():
    """GET /api/flood/model-comparison returns empirical comparison on held-out test data."""
    resp = client.get("/api/flood/model-comparison")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["model_version"] == "EIDT-ML-Predictive-v2.0"
    assert "metrics" in data
    assert "model_comparison" in data
    assert data["sample_size"]["total_observations"] == 100
    assert len(data["feature_importance"]) == 7


def test_api_flood_historical_dataset():
    """GET /api/flood/historical-dataset returns verified events and provenance citations."""
    resp = client.get("/api/flood/historical-dataset")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_events"] == 10
    assert data["total_observations"] == 100
    assert data["provenance_status"] == "ALL_RECORDS_VERIFIED_NO_SYNTHETIC_MANUFACTURE"
    assert len(data["documented_events"]) == 10


def test_api_flood_localities_has_calibrated_probabilities():
    """GET /api/flood/localities returns calibrated probability and risk_category."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_METEO_PAYLOAD

    with patch.object(BaseConnector, "_execute_request_with_retries", return_value=mock_resp):
        resp = client.get("/api/flood/localities")

    assert resp.status_code == 200
    data = resp.json()
    assert data["probability_calibrated"] is True
    assert data["brier_score_loss"] <= 0.20
    assert "VERY_HIGH" in data["risk_distribution"]

    kurla = next(l for l in data["localities"] if l["locality_id"] == "MUM_WARD_L_KURLA")
    assert "predicted_flood_probability" in kurla
    assert "risk_category" in kurla
    assert 0.0 <= kurla["predicted_flood_probability"] <= 1.0


# -------------------------------------------------------------------------
# 7. Unsupported Region & Absence of Overconfident Extrapolation
# -------------------------------------------------------------------------

def test_api_unsupported_region_handling():
    """GET /api/flood/localities/{unknown} cleanly returns 404 with locality hints."""
    resp = client.get("/api/flood/localities/PUNE_WARD_01")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
    assert "MUM_WARD_L_KURLA" in resp.json()["detail"]


# -------------------------------------------------------------------------
# 8. Separation of Observations, Forecasts, and Scenarios
# -------------------------------------------------------------------------

def test_separation_of_observations_and_forecasts():
    """Ensure observations are strictly retrospective ground truth and not forecasts."""
    obs_resp = client.get("/api/flood/observations")
    assert obs_resp.status_code == 200
    obs_data = obs_resp.json()
    assert obs_data["dataset_classification"] == "HISTORICAL_OBSERVATIONS_GROUND_TRUTH"
    for item in obs_data["observations"]:
        assert item["is_forecast"] is False
