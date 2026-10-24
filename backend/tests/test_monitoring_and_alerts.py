"""
Comprehensive Test Suite for Phase 5: Monitoring, Ingestion Orchestration, and Early-Warning Alerts
Tests:
- Temporal decoupling (observed_at, issued_at, valid_at, retrieved_at, processed_at)
- Data quality physics bounds checks and anomaly detection
- Source freshness classification with tailored thresholds
- Idempotent observation deduplication
- Scheduler non-overlapping execution locks
- Alert lifecycle state machine (NEW/ACTIVE -> UPDATED -> EXPIRED)
- Strict segregation of Official Government Notices vs EIDT Advisories
- Notification safety defaults (NOTIFICATIONS_ENABLED=false)
- REST API contracts under /api/monitoring and /api/alerts
"""
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal, get_db
from app.models.schema import (
    SourceHealthRecord,
    ScheduledIngestionJob,
    IngestedObservation,
    MultiHazardAlert,
    AlertLifecycleEvent,
    AlertNotification
)
from app.services.monitoring_service import MonitoringService, PHYSICAL_BOUNDS
from app.services.alert_orchestrator import AlertOrchestrator
from app.services.notification_service import NotificationService
from app.services.scheduler_service import OrchestrationScheduler, get_orchestration_scheduler

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_monitoring_service_freshness_classification(db_session: Session):
    """Verifies that source freshness classifies correctly according to individual thresholds."""
    monitoring = MonitoringService(db_session)
    now = datetime.now(timezone.utc)

    # 1. Healthy source: updated 10 minutes ago (within 60m expected cadence)
    rec_healthy = monitoring.update_source_health(
        source_id="open_meteo_forecast",
        success=True,
        records_count=24,
        retrieval_timestamp=now - timedelta(minutes=10)
    )
    assert rec_healthy.health_status == "healthy"
    assert rec_healthy.consecutive_failures == 0

    # 2. Delayed source: updated 120 minutes ago (past 60m cadence, within 180m threshold)
    rec_delayed = monitoring.update_source_health(
        source_id="open_meteo_forecast",
        success=True,
        records_count=24,
        retrieval_timestamp=now - timedelta(minutes=120)
    )
    assert rec_delayed.health_status == "delayed"

    # 3. Stale source: updated 240 minutes ago (exceeds 180m threshold)
    rec_stale = monitoring.update_source_health(
        source_id="open_meteo_forecast",
        success=True,
        records_count=24,
        retrieval_timestamp=now - timedelta(minutes=240)
    )
    assert rec_stale.health_status == "stale"

    # 4. Failed source: records consecutive failures leading to degraded/unavailable
    rec_fail = monitoring.update_source_health(
        source_id="open_meteo_forecast",
        success=False,
        error_message="Connection timed out to Open-Meteo"
    )
    assert rec_fail.health_status in ["degraded", "unavailable"]
    assert rec_fail.consecutive_failures >= 1


def test_data_quality_physics_bounds(db_session: Session):
    """Verifies physical plausibility checking on observations."""
    monitoring = MonitoringService(db_session)
    now = datetime.now(timezone.utc)

    # Valid precipitation reading
    valid, flags = monitoring.validate_observation("precipitation", 45.2, "mm", timestamp=now)
    assert valid is True
    assert flags["status"] == "VALID"

    # Implausible negative precipitation
    invalid_neg, flags_neg = monitoring.validate_observation("precipitation", -5.0, "mm", timestamp=now)
    assert invalid_neg is False
    assert flags_neg["status"] == "OUT_OF_RANGE"

    # Implausible extreme precipitation
    invalid_ext, flags_ext = monitoring.validate_observation("precipitation", 9999.0, "mm", timestamp=now)
    assert invalid_ext is False
    assert flags_ext["status"] == "OUT_OF_RANGE"

    # Missing timestamp
    invalid_ts, flags_ts = monitoring.validate_observation("precipitation", 10.0, "mm", timestamp=None)
    assert invalid_ts is False
    assert flags_ts["status"] == "REJECTED"


def test_observation_storage_and_idempotent_deduplication(db_session: Session):
    """Verifies that duplicate ingestion updates rather than inserting duplicates."""
    monitoring = MonitoringService(db_session)
    now = datetime.now(timezone.utc)
    valid_time = now + timedelta(hours=3)

    # First ingestion
    obs1, outcome1 = monitoring.record_observation(
        source_id="open_meteo_forecast",
        variable_name="precipitation",
        value=15.5,
        unit="mm",
        observed_at=None,
        issued_at=now,
        valid_at=valid_time,
        retrieved_at=now,
        locality_name="Kurla",
        latitude=19.07,
        longitude=72.88
    )
    assert outcome1 in ["ACCEPTED", "DEDUPLICATED"]
    assert obs1 is not None
    assert obs1.valid_at is not None
    assert obs1.retrieved_at is not None

    # Re-ingest same timestamp with updated value (e.g. newer model run)
    obs2, outcome2 = monitoring.record_observation(
        source_id="open_meteo_forecast",
        variable_name="precipitation",
        value=18.0,
        unit="mm",
        observed_at=None,
        issued_at=now + timedelta(minutes=15),
        valid_at=valid_time,
        retrieved_at=now + timedelta(minutes=15),
        locality_name="Kurla",
        latitude=19.07,
        longitude=72.88
    )
    assert outcome2 == "DEDUPLICATED"
    assert obs2.observation_id == obs1.observation_id
    assert float(obs2.value) == 18.0


def test_alert_lifecycle_and_official_warning_segregation(db_session: Session):
    """Verifies alert state machine, deduplication, and distinction between official notices and EIDT advisories."""
    orchestrator = AlertOrchestrator(db_session)
    now = datetime.now(timezone.utc)
    unique_scope = f"Kurla / BKC Test {datetime.now().microsecond}"

    # 1. Create EIDT decision support alert
    alert_eidt, outcome = orchestrator.create_or_update_alert(
        hazard_type="FLOOD",
        geographic_scope=unique_scope,
        severity_level="ORANGE",
        headline="EIDT Decision Support: Heavy Inundation Forecast",
        description="NWP indicates 85mm accumulation over 24h.",
        issuing_authority="EIDT Multi-Hazard Intelligence Engine",
        is_official_warning=False,
        onset_timestamp=now,
        expiry_timestamp=now + timedelta(hours=6)
    )
    assert outcome == "CREATED"
    assert alert_eidt.lifecycle_status == "ACTIVE"
    assert alert_eidt.is_official_warning is False

    # Check event audit trail
    events = db_session.query(AlertLifecycleEvent).filter_by(alert_id=alert_eidt.alert_id).all()
    assert len(events) >= 1
    assert events[0].new_state == "ACTIVE"

    # 2. Update alert with changed severity -> state transitions to UPDATED
    alert_updated, outcome_up = orchestrator.create_or_update_alert(
        hazard_type="FLOOD",
        geographic_scope=unique_scope,
        severity_level="RED",
        headline="EIDT Decision Support: Severe Inundation Forecast",
        description="NWP accumulation revised upward to 125mm.",
        issuing_authority="EIDT Multi-Hazard Intelligence Engine",
        is_official_warning=False,
        onset_timestamp=now,
        expiry_timestamp=now + timedelta(hours=6)
    )
    assert outcome_up == "UPDATED"
    assert alert_updated.lifecycle_status == "UPDATED"
    assert alert_updated.severity_level == "RED"

    # 3. Simulate expiry
    alert_updated.expiry_timestamp = now - timedelta(minutes=10)
    db_session.commit()
    expired_ids = orchestrator.evaluate_expiry_cycle()
    assert alert_updated.alert_id in expired_ids
    assert alert_updated.lifecycle_status == "EXPIRED"


def test_notification_service_safe_defaults(db_session: Session):
    """Verifies that external notifications are suppressed when NOTIFICATIONS_ENABLED is false."""
    import uuid
    notif_svc = NotificationService(db_session)
    now = datetime.now(timezone.utc)
    unique_alt_id = f"alt_test_safe_{uuid.uuid4().hex[:10]}"

    mock_alert = MultiHazardAlert(
        alert_id=unique_alt_id,
        hazard_type="HEATWAVE",
        geographic_scope="Vidarbha",
        severity_level="YELLOW",
        headline="High Temperature Advisory",
        description="41.5 degC expected.",
        lifecycle_status="ACTIVE",
        is_official_warning=False,
        issuing_authority="EIDT Heat Stress Module",
        onset_timestamp=now,
        created_at=now,
        updated_at=now
    )
    db_session.add(mock_alert)
    db_session.commit()

    # Dispatch to in_app and webhook
    records = notif_svc.dispatch_alert_notifications(
        mock_alert,
        channels=["in_app", "webhook"]
    )
    assert len(records) == 2

    # In-app should be DELIVERED
    in_app_rec = next(r for r in records if r.channel == "in_app")
    assert in_app_rec.status == "DELIVERED"

    # Webhook should be SUPPRESSED by default
    webhook_rec = next(r for r in records if r.channel == "webhook")
    assert webhook_rec.status == "SUPPRESSED"


def test_scheduler_overlap_prevention(db_session: Session):
    """Verifies that concurrent calls to the same job prevent duplicate overlapping execution."""
    scheduler = OrchestrationScheduler()
    # Acquire lock manually to simulate active run
    lock = scheduler._active_jobs["weather_forecast_refresh"]
    lock.acquire()

    try:
        # Second invocation while lock is held must return SKIPPED
        res = scheduler.job_weather_forecast_refresh()
        assert res.get("status") == "SKIPPED"
        assert "overlap" in res.get("reason", "").lower()
    finally:
        lock.release()


def test_monitoring_api_endpoints():
    """Tests /api/monitoring REST endpoints."""
    # 1. System status
    resp = client.get("/api/monitoring/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OPERATIONAL"
    assert "source_counts" in data

    # 2. Source health
    resp_sources = client.get("/api/monitoring/sources")
    assert resp_sources.status_code == 200
    src_data = resp_sources.json()
    assert src_data["count"] >= 5
    assert any(s["source_id"] == "open_meteo_forecast" for s in src_data["sources"])

    # 3. Observations endpoint
    resp_obs = client.get("/api/monitoring/observations?limit=5")
    assert resp_obs.status_code == 200

    # 4. Forecasts endpoint
    resp_fc = client.get("/api/monitoring/forecasts?hours=24")
    assert resp_fc.status_code == 200
    assert "spatial_resolution" in resp_fc.json()

    # 5. Data quality endpoint
    resp_q = client.get("/api/monitoring/quality")
    assert resp_q.status_code == 200
    assert "quality_rules" in resp_q.json()


def test_alerts_api_endpoints():
    """Tests /api/alerts REST endpoints."""
    # Active alerts
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "active_count" in data

    # History
    resp_hist = client.get("/api/alerts/history")
    assert resp_hist.status_code == 200
    assert "history" in resp_hist.json()


def test_manual_job_execution_api():
    """Tests triggering a manual job via POST /api/monitoring/jobs/{job_name}/run."""
    resp = client.post("/api/monitoring/jobs/weather_forecast_refresh/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "weather_forecast_refresh" in data["message"]
    assert data["result"]["status"] in ["SUCCESS", "SKIPPED"]
