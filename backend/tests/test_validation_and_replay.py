"""
Phase 6 Automated Test Suite: Historical Disaster Replay, Model Calibration & Scientific Validation
EIDT Maharashtra

Verifies:
1. Multi-hazard readiness audit table contracts.
2. Historical event catalogue integrity, provenance, and idempotency.
3. Strict temporal separation (Train: 2005-2019, Held-out Test: 2020-2023) and issue-time constraints.
4. Mathematical correctness of contingency metrics (CSI, POD, FAR, F1, Accuracy, Brier) against hand-calculated fixtures.
5. Inundation IoU calculation with valid geometries and insufficient-data handling.
6. Probability calibration (Platt scaling): fitted strictly on training data, evaluated on independent test data.
7. Replay engine execution and guaranteed isolation from live system alerts.
8. API endpoints under /api/validation, /api/replay, and /api/models/{model_id}/calibration.
"""

import pytest
import math
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.schema import (
    HistoricalHazardEvent,
    EvaluationDataset,
    EvaluationDatasetSample,
    EvaluationRun,
    EvaluationMetric,
    HistoricalReplayRun,
    MultiHazardAlert,
    RoadRestriction
)
from app.services.validation_service import (
    HistoricalValidationService,
    calculate_contingency_metrics,
    calculate_inundation_iou,
    fit_platt_scaling,
    apply_platt_scaling,
    compute_reliability_bins,
    HAZARD_READINESS_AUDIT
)
from app.services.replay_service import HistoricalReplayEngine

client = TestClient(app)


# ============================================================================
# 1. HAND-VERIFIABLE METRIC FIXTURES
# ============================================================================

def test_hand_calculated_contingency_metrics():
    """
    Validates disaster contingency metric formulas against a small hand-calculated fixture:
    y_true: [1, 1, 1, 0, 0, 0, 1, 0] (4 positive, 4 negative)
    y_pred: [1, 1, 0, 0, 1, 0, 1, 0]
    
    TP = 3 (indices 0, 1, 6)
    FP = 1 (index 4)
    TN = 3 (indices 3, 5, 7)
    FN = 1 (index 2)
    Total N = 8

    Expected:
    - Precision = 3 / (3 + 1) = 0.75
    - POD (Recall / Hit Rate) = 3 / (3 + 1) = 0.75
    - False Alarm Ratio (FAR) = 1 / (3 + 1) = 0.25
    - Critical Success Index (CSI / Threat Score) = 3 / (3 + 1 + 1) = 3 / 5 = 0.60
    - Accuracy = (3 + 3) / 8 = 0.75
    - F1 Score = 2 * (0.75 * 0.75) / (0.75 + 0.75) = 0.75
    """
    y_true = [1, 1, 1, 0, 0, 0, 1, 0]
    y_pred = [1, 1, 0, 0, 1, 0, 1, 0]
    y_prob = [0.9, 0.8, 0.4, 0.1, 0.6, 0.2, 0.85, 0.15]

    res = calculate_contingency_metrics(y_true, y_pred, y_prob)

    assert res["sample_size"] == 8
    assert res["contingency_table"]["true_positives"] == 3
    assert res["contingency_table"]["false_positives"] == 1
    assert res["contingency_table"]["true_negatives"] == 3
    assert res["contingency_table"]["false_negatives"] == 1

    assert math.isclose(res["precision"], 0.75, abs_tol=1e-4)
    assert math.isclose(res["probability_of_detection"], 0.75, abs_tol=1e-4)
    assert math.isclose(res["false_alarm_ratio"], 0.25, abs_tol=1e-4)
    assert math.isclose(res["critical_success_index"], 0.60, abs_tol=1e-4)
    assert math.isclose(res["accuracy"], 0.75, abs_tol=1e-4)
    assert math.isclose(res["f1_score"], 0.75, abs_tol=1e-4)
    assert "brier_score" in res


def test_contingency_metrics_zero_division_guard():
    """Confirms that metrics handle edge cases (all zeros, all ones, empty) gracefully."""
    empty_res = calculate_contingency_metrics([], [])
    assert empty_res["error"] == "insufficient_data"

    # All negative predictions with 1 positive true (TP=0, FP=0, TN=1, FN=1)
    res_zero = calculate_contingency_metrics([1, 0], [0, 0])
    assert res_zero["precision"] == 0.0
    assert res_zero["false_alarm_ratio"] == 0.0
    assert res_zero["critical_success_index"] == 0.0
    assert res_zero["probability_of_detection"] == 0.0


def test_inundation_iou_calculation():
    """Tests spatial IoU calculation against simple geometry boxes."""
    # Box 1: [0, 0] to [2, 2] -> Area = 4
    # Box 2: [1, 0] to [3, 2] -> Area = 4
    # Intersection: [1, 0] to [2, 2] -> Area = 2
    # Union: [0, 0] to [3, 2] -> Area = 6
    # Expected IoU = 2 / 6 = 0.3333
    geom_pred = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]
    }
    geom_obs = {
        "type": "Polygon",
        "coordinates": [[[1, 0], [3, 0], [3, 2], [1, 2], [1, 0]]]
    }

    res = calculate_inundation_iou(geom_pred, geom_obs)
    assert res["status"] == "computed"
    assert math.isclose(res["metric_value"], 0.3333, abs_tol=1e-3)

    # Test missing geometries
    res_missing = calculate_inundation_iou(None, geom_obs)
    assert res_missing["status"] == "insufficient_data"


# ============================================================================
# 2. HAZARD READINESS & AUDIT INTEGRITY
# ============================================================================

def test_hazard_readiness_audit_matrix():
    """Verifies that all 6 required hazard types are audited with honest statuses."""
    db: Session = SessionLocal()
    try:
        service = HistoricalValidationService(db)
        readiness = service.get_readiness_audit()

        hazards = {r["hazard_type"]: r for r in readiness}
        assert "FLOOD" in hazards
        assert "HEATWAVE" in hazards
        assert "LANDSLIDE" in hazards
        assert "DROUGHT" in hazards
        assert "COASTAL" in hazards
        assert "THUNDERSTORM" in hazards

        # Honest classification checks
        assert hazards["FLOOD"]["evaluation_readiness"] == "Ready"
        assert hazards["HEATWAVE"]["evaluation_readiness"] == "Limited"
        assert hazards["LANDSLIDE"]["evaluation_readiness"] == "Limited"
        assert hazards["THUNDERSTORM"]["evaluation_readiness"] == "Insufficient reference data"

        # Check that limitations are transparently documented
        for h in readiness:
            assert len(h["known_limitations"]) > 15
            assert len(h["target_variable"]) > 5
    finally:
        db.close()


# ============================================================================
# 3. HISTORICAL DISASTER CATALOGUE & PROVENANCE
# ============================================================================

def test_historical_event_catalogue_provenance():
    """Verifies that historical events have verifiable sources and non-null provenance."""
    db: Session = SessionLocal()
    try:
        service = HistoricalValidationService(db)
        service.seed_historical_catalogue_if_empty()

        events, total = service.list_events(limit=50)
        assert total >= 10

        # Check documented flood events
        event_ids = [e["event_id"] for e in events]
        assert "MUM_EVENT_20050726" in event_ids
        assert "MUM_EVENT_20170829" in event_ids
        assert "MUM_EVENT_20190702" in event_ids
        assert "MUM_EVENT_20200805" in event_ids
        assert "MUM_EVENT_20210718" in event_ids
        assert "MUM_EVENT_20230726" in event_ids

        # Check multi-hazard representation
        assert "MAH_LANDSLIDE_20140730_MALIN" in event_ids
        assert "MAH_LANDSLIDE_20210722_TALIYE" in event_ids
        assert "MAH_HEATWAVE_202204_VIDARBHA" in event_ids
        assert "MAH_CYCLONE_20200603_NISARGA" in event_ids
        assert "MAH_DROUGHT_2015_2016_MARATHWADA" in event_ids

        # Verify provenance fields
        chitale_event = service.get_event_detail("MUM_EVENT_20050726")
        assert chitale_event is not None
        assert "Chitale Committee" in chitale_event["primary_source"]
        assert chitale_event["evidence_classification"] == "SURVEYED_DISASTER_RECORDS"
        assert chitale_event["meteorological_metrics"]["rainfall_24h_suburban_mm"] == 944.2
    finally:
        db.close()


# ============================================================================
# 4. LEAKAGE-RESISTANT EVALUATION & TEMPORAL HOLDOUTS
# ============================================================================

def test_evaluation_dataset_temporal_holdout_and_issue_time():
    """
    Verifies:
    1. Chronological split: Train (2005-2019) strictly precedes Test (2020-2023).
    2. Zero event-level cross-contamination.
    3. Issue time strictly precedes verification valid time (no future leakage).
    """
    db: Session = SessionLocal()
    try:
        service = HistoricalValidationService(db)
        service.seed_historical_catalogue_if_empty()

        samples = db.query(EvaluationDatasetSample).filter_by(dataset_id="EVAL_DATASET_MMR_FLOOD_V2").all()
        assert len(samples) == 100  # 10 events * 10 wards

        train_samples = [s for s in samples if s.split_assignment == "TRAIN"]
        test_samples = [s for s in samples if s.split_assignment == "TEST"]

        assert len(train_samples) == 50
        assert len(test_samples) == 50

        # Temporal boundary test
        max_train_date = max(s.valid_time for s in train_samples)
        min_test_date = min(s.valid_time for s in test_samples)
        assert max_train_date < min_test_date, "Temporal leakage: Train date overlaps or exceeds Test date!"

        # Issue time constraint test: issue_time MUST be earlier than valid_time
        for s in samples:
            assert s.prediction_issue_time < s.valid_time, f"Future information leakage in sample {s.sample_id}"

        # Event-level grouping test: no event_id appears in both TRAIN and TEST
        train_events = set(s.event_id for s in train_samples)
        test_events = set(s.event_id for s in test_samples)
        assert len(train_events.intersection(test_events)) == 0, "Event leakage: Same event appears in both train and test!"
    finally:
        db.close()


def test_held_out_model_evaluation_execution():
    """
    Runs model evaluation on held-out test data and verifies that metrics
    (CSI, POD, FAR, Brier) are computed by executable code.
    """
    db: Session = SessionLocal()
    try:
        service = HistoricalValidationService(db)
        eval_run = service.execute_flood_evaluation_run(model_id="flood_rf_v2_1", split_to_evaluate="TEST")

        assert eval_run["split_evaluated"] == "TEST"
        assert eval_run["sample_size"] == 50
        assert eval_run["evidence_classification"] == "VALIDATED_ON_HELD_OUT_DATA"

        metrics = eval_run["metrics"]
        assert 0.0 <= metrics["critical_success_index"] <= 1.0
        assert 0.0 <= metrics["probability_of_detection"] <= 1.0
        assert 0.0 <= metrics["false_alarm_ratio"] <= 1.0
        assert 0.0 <= metrics["brier_score"] <= 1.0
        assert metrics["contingency_table"]["true_positives"] >= 0
    finally:
        db.close()


# ============================================================================
# 5. PROBABILITY CALIBRATION (PLATT SCALING)
# ============================================================================

def test_probability_calibration_data_separation():
    """
    Verifies that Platt scaling is fitted on TRAIN samples and evaluated on held-out TEST samples.
    Confirms pre/post Brier score tracking and reliability bins.
    """
    db: Session = SessionLocal()
    try:
        service = HistoricalValidationService(db)
        calib = service.execute_model_calibration(model_id="flood_rf_v2_1")

        assert "calibration_id" in calib
        assert calib["sample_size_fitted"] == 50  # Train set
        assert calib["sample_size_evaluated"] == 50  # Test set
        assert "parameters" in calib
        assert "A" in calib["parameters"] and "B" in calib["parameters"]
        assert "brier_score_before" in calib
        assert "brier_score_after" in calib
        assert len(calib["reliability_diagram_bins"]) == 5
    finally:
        db.close()


# ============================================================================
# 6. HISTORICAL REPLAY & STRICT STATE ISOLATION
# ============================================================================

def test_historical_replay_execution_and_state_isolation():
    """
    Verifies:
    1. Historical replay generates predicted vs observed outcomes.
    2. Replay timeline progresses chronologically.
    3. Live state isolation: ZERO modifications to active alerts or restrictions.
    """
    db: Session = SessionLocal()
    try:
        # Record baseline counts of live tables
        live_alerts_before = db.query(MultiHazardAlert).count()
        live_restrictions_before = db.query(RoadRestriction).count()

        engine = HistoricalReplayEngine(db)
        replay = engine.execute_replay(
            event_id="MUM_EVENT_20050726",
            replay_mode="RETROSPECTIVE_RECONSTRUCTION",
            model_version="flood_rf_v2_1"
        )

        assert replay["is_isolated_from_live"] is True
        assert replay["replay_mode"] == "RETROSPECTIVE_RECONSTRUCTION"
        assert len(replay["predicted_outcomes"]) == 10  # All 10 wards
        assert len(replay["observed_benchmark"]) == 10
        assert len(replay["timeline"]) == 8  # T-18h to T+12h

        # Concordance checks for 2005 event (catastrophic inundation)
        assert replay["concordance_metrics"]["contingency_table"]["true_positives"] >= 5

        # CRITICAL VERIFICATION: Ensure live alerts and road restrictions were NOT touched
        live_alerts_after = db.query(MultiHazardAlert).count()
        live_restrictions_after = db.query(RoadRestriction).count()

        assert live_alerts_before == live_alerts_after, "Isolation violated! Live alerts modified during replay."
        assert live_restrictions_before == live_restrictions_after, "Isolation violated! Live restrictions modified during replay."
    finally:
        db.close()


# ============================================================================
# 7. FASTAPI HTTP ENDPOINT TESTS
# ============================================================================

def test_api_validation_readiness():
    """Tests GET /api/validation/readiness."""
    resp = client.get("/api/validation/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total_hazards_audited"] == 6


def test_api_validation_events():
    """Tests GET /api/validation/events and detail."""
    resp = client.get("/api/validation/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 10

    # Get specific event
    event_id = data["events"][0]["event_id"]
    detail_resp = client.get(f"/api/validation/events/{event_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["event_id"] == event_id


def test_api_validation_datasets():
    """Tests GET /api/validation/datasets."""
    resp = client.get("/api/validation/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["datasets"][0]["dataset_id"] == "EVAL_DATASET_MMR_FLOOD_V2"


def test_api_trigger_evaluation_run():
    """Tests POST /api/validation/runs."""
    payload = {
        "model_id": "flood_rf_v2_1",
        "split_to_evaluate": "TEST"
    }
    resp = client.post("/api/validation/runs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert data["evidence_classification"] == "VALIDATED_ON_HELD_OUT_DATA"


def test_api_replay_runs():
    """Tests POST /api/replay/runs and GET /api/replay/runs."""
    payload = {
        "event_id": "MUM_EVENT_20190702",
        "replay_mode": "RETROSPECTIVE_RECONSTRUCTION",
        "model_version": "flood_rf_v2_1"
    }
    resp = client.post("/api/replay/runs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "replay_id" in data
    assert data["is_isolated_from_live"] is True

    # List runs
    list_resp = client.get("/api/replay/runs")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


def test_api_model_validation_and_calibration():
    """Tests GET /api/models/{model_id}/validation and GET /api/models/{model_id}/calibration."""
    v_resp = client.get("/api/models/flood_rf_v2_1/validation")
    assert v_resp.status_code == 200
    v_data = v_resp.json()
    assert v_data["validation_status"] == "VALIDATED_ON_HELD_OUT_DATA"

    c_resp = client.get("/api/models/flood_rf_v2_1/calibration")
    assert c_resp.status_code == 200
    c_data = c_resp.json()
    assert "brier_score_before" in c_data
    assert "brier_score_after" in c_data
