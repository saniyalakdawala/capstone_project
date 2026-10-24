"""
Phase 3 Multi-Hazard Intelligence and Early-Warning Test Suite
Verifies:
1. Reusable hazard architecture across all 6 hazard categories:
   - Flooding (pluvial/fluvial & inundation)
   - Heatwaves & urban heat stress
   - Landslide susceptibility & rainfall triggers
   - Drought & water scarcity (meteorological vs hydrological)
   - Coastal inundation & astronomical tide gate lockage
   - Severe thunderstorms, wind squalls & nowcasts
2. Scientific integrity & absence of synthetic or fabricated data:
   - Operational vs screening vs declared data-gap statuses
   - Distinct separation of official warnings (IMD/INCOIS) from EIDT diagnostic advisories
   - Explicit declaration of uninstrumented sensor gaps
3. Alert lifecycle management:
   - Candidate -> Verified -> Issued -> Updated -> Expired/Withdrawn
   - Deduplication hashing across repeated ingestions
   - Automated expiration handling
4. Schema migration 004 & non-destructive database preservation
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db, SessionLocal
from app.models.schema import SchemaMigration, MultiHazardAlert, HazardAssessment
from app.services.hazards.hazard_registry import hazard_registry
from app.services.hazards.alert_manager import AlertLifecycleManager

client = TestClient(app)

SUPPORTED_HAZARDS = [
    "flood",
    "heatwave",
    "landslide",
    "drought",
    "coastal",
    "thunderstorm"
]


# -------------------------------------------------------------------------
# 1. Platform Catalog & Architectural Consistency
# -------------------------------------------------------------------------

def test_hazards_catalog_endpoint():
    """Verify GET /api/hazards returns all 6 categories with documented metadata."""
    res = client.get("/api/hazards")
    assert res.status_code == 200
    data = res.json()
    assert data["hazard_count"] == 6
    assert "supported_hazards" in data

    catalog = data["supported_hazards"]
    for h in SUPPORTED_HAZARDS:
        assert h in catalog
        info = catalog[h]
        assert info["hazard_id"] == h
        assert "name" in info
        assert "version" in info
        assert "status" in info
        assert "prediction_horizon" in info
        assert "target_definition" in info
        assert "responsible_authority" in info
        assert "coverage" in info
        assert isinstance(info["verified_data_sources"], list)
        assert len(info["verified_data_sources"]) >= 1


def test_unsupported_hazard_returns_404():
    """Verify that querying an unsupported hazard returns structured 404 with supported options."""
    res = client.get("/api/hazards/volcano/status")
    assert res.status_code == 404
    data = res.json()
    assert "unsupported" in str(data["detail"]).lower()


# -------------------------------------------------------------------------
# 2. Individual Module Status & Scientific Rigour Checks
# -------------------------------------------------------------------------

@pytest.mark.parametrize("hazard_id", SUPPORTED_HAZARDS)
def test_hazard_status_endpoint(hazard_id):
    """Verify status endpoint returns required architectural fields without superficial claims."""
    res = client.get(f"/api/hazards/{hazard_id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["hazard_id"] == hazard_id
    assert "operational_status" in data
    assert "geographic_coverage" in data
    assert "limitations" in data
    assert isinstance(data["limitations"], list)
    assert len(data["limitations"]) >= 1


def test_scientific_status_distinction():
    """Verify that models are not superficially claimed to be fully calibrated when data is missing."""
    # Flood is operational with ML Platt calibration from Phase 2B
    res_flood = client.get("/api/hazards/flood/status").json()
    assert res_flood["operational_status"] == "OPERATIONAL"

    # Heatwave is operational with Open-Meteo NWP + Rothfusz Heat Index
    res_heat = client.get("/api/hazards/heatwave/status").json()
    assert res_heat["operational_status"] == "OPERATIONAL"

    # Landslide is terrain screening + empirical trigger, NOT dynamic subsurface 3D simulation
    res_ls = client.get("/api/hazards/landslide/status").json()
    assert "SCREENING" in res_ls["operational_status"]

    # Drought has meteorological rainfall operational, but hydrological SCADA telemetry is flagged
    res_dr = client.get("/api/hazards/drought/status").json()
    assert "HYDROLOGICAL_GAPS" in res_dr["operational_status"]

    # Coastal has tide harmonics operational, but offshore storm surge wave simulation is flagged
    res_cs = client.get("/api/hazards/coastal/status").json()
    assert "SURGE_GAPS" in res_cs["operational_status"]


# -------------------------------------------------------------------------
# 3. Forecast Products & Spatial Layers
# -------------------------------------------------------------------------

@pytest.mark.parametrize("hazard_id", SUPPORTED_HAZARDS)
def test_hazard_forecast_products(hazard_id):
    """Verify GET /api/hazards/{hazard}/forecast returns timestamps and valid indicators."""
    res = client.get(f"/api/hazards/{hazard_id}/forecast")
    assert res.status_code == 200
    data = res.json()
    assert data["hazard_id"] == hazard_id
    assert "issue_time_utc" in data
    assert "valid_time_start_utc" in data
    assert "valid_time_end_utc" in data


@pytest.mark.parametrize("hazard_id", SUPPORTED_HAZARDS)
def test_hazard_map_layers(hazard_id):
    """Verify GET /api/hazards/{hazard}/layers returns valid GeoJSON FeatureCollection."""
    res = client.get(f"/api/hazards/{hazard_id}/layers")
    assert res.status_code == 200
    geo = res.json()
    assert geo["type"] == "FeatureCollection"
    assert "features" in geo
    assert len(geo["features"]) >= 1

    feature = geo["features"][0]
    assert "properties" in feature
    assert "risk_category" in feature["properties"]
    assert "geometry" in feature


# -------------------------------------------------------------------------
# 4. Locality Aggregation & Contributing Factors
# -------------------------------------------------------------------------

@pytest.mark.parametrize("hazard_id", SUPPORTED_HAZARDS)
def test_hazard_localities_endpoint(hazard_id):
    """Verify GET /api/hazards/{hazard}/localities returns multi-ward assessments with contributing factors."""
    res = client.get(f"/api/hazards/{hazard_id}/localities")
    assert res.status_code == 200
    data = res.json()
    assert data["hazard_id"] == hazard_id
    assert "localities" in data
    assert len(data["localities"]) >= 10

    loc = data["localities"][0]
    assert "locality_id" in loc
    assert "locality_name" in loc
    assert "risk_category" in loc
    assert "contributing_factors" in loc
    assert isinstance(loc["contributing_factors"], list)


def test_single_locality_lookup():
    """Verify GET /api/hazards/{hazard}/localities/{locality_id} returns detailed assessment."""
    res = client.get("/api/hazards/heatwave/localities/MUM_WARD_L_KURLA")
    assert res.status_code == 200
    data = res.json()
    assert data["locality_id"] == "MUM_WARD_L_KURLA"
    assert "forecast_max_temp_c" in data
    assert "peak_heat_index_c" in data
    assert "urban_heat_island_anomaly_c" in data

    # Test not found
    res_404 = client.get("/api/hazards/heatwave/localities/INVALID_WARD_999")
    assert res_404.status_code == 404


# -------------------------------------------------------------------------
# 5. Provenance & Declared Uninstrumented Gaps
# -------------------------------------------------------------------------

@pytest.mark.parametrize("hazard_id", SUPPORTED_HAZARDS)
def test_hazard_provenance(hazard_id):
    """Verify GET /api/hazards/{hazard}/provenance documents data sources, licenses, and missing inputs."""
    res = client.get(f"/api/hazards/{hazard_id}/provenance")
    assert res.status_code == 200
    data = res.json()
    assert data["hazard_id"] == hazard_id
    assert "sources" in data
    assert len(data["sources"]) >= 1

    for src in data["sources"]:
        assert "dataset" in src
        assert "authority" in src
        assert "resolution" in src
        assert "license" in src

    # Verify declared missing inputs (no silent imputation)
    assert "missing_inputs" in data
    assert isinstance(data["missing_inputs"], list)
    assert len(data["missing_inputs"]) >= 1


# -------------------------------------------------------------------------
# 6. Empirical Validation & Non-Fabrication
# -------------------------------------------------------------------------

@pytest.mark.parametrize("hazard_id", SUPPORTED_HAZARDS)
def test_hazard_validation(hazard_id):
    """Verify GET /api/hazards/{hazard}/validation reports honest metrics without fabricated values."""
    res = client.get(f"/api/hazards/{hazard_id}/validation")
    assert res.status_code == 200
    data = res.json()
    assert data["hazard_id"] == hazard_id
    assert "validation_status" in data
    assert "benchmark_events" in data
    assert "scientific_limitations" in data
    assert isinstance(data["scientific_limitations"], list)
    assert len(data["scientific_limitations"]) >= 1


# -------------------------------------------------------------------------
# 7. Common Alert Lifecycle, Deduplication & Official Warning Separation
# -------------------------------------------------------------------------

def test_alert_lifecycle_and_deduplication():
    """Verify candidate -> verified -> issued lifecycle, deduplication hashing, and auto-expiry."""
    db: Session = SessionLocal()
    mgr = AlertLifecycleManager()
    try:
        now = datetime.now(timezone.utc)

        # 1. Register alert
        first_record = mgr.register_or_update_alert(
            db=db,
            hazard_type="thunderstorm",
            geographic_scope="MMR_KURLA_GHATKOPAR",
            severity_level="HIGH",
            headline="Severe Convective Gust Test Alert",
            description="NWP indicates localized wind gusts exceeding 65 km/h.",
            issuing_authority="EIDT Model Diagnostic",
            is_official_warning=False,
            recommended_action="Avoid parking under hoarding structures.",
            duration_hours=6
        )
        assert first_record.lifecycle_status in ["VERIFIED", "ISSUED", "UPDATED"]
        assert first_record.hazard_type == "thunderstorm"
        assert first_record.deduplication_hash is not None

        # 2. Polling again with identical candidate returns existing alert (deduplication)
        second_record = mgr.register_or_update_alert(
            db=db,
            hazard_type="thunderstorm",
            geographic_scope="MMR_KURLA_GHATKOPAR",
            severity_level="HIGH",
            headline="Severe Convective Gust Test Alert",
            description="NWP indicates localized wind gusts exceeding 65 km/h.",
            issuing_authority="EIDT Model Diagnostic",
            is_official_warning=False,
            recommended_action="Avoid parking under hoarding structures.",
            duration_hours=6
        )
        assert second_record.alert_id == first_record.alert_id

        # 3. Check active alerts query returns this alert
        active_alerts = mgr.get_active_alerts(db=db, hazard_type="thunderstorm")
        found = any(a["alert_id"] == first_record.alert_id for a in active_alerts)
        assert found is True

        # 4. Official warning distinction test
        official_rec = mgr.register_or_update_alert(
            db=db,
            hazard_type="thunderstorm",
            geographic_scope="MUMBAI_METROPOLITAN_REGION",
            severity_level="SEVERE",
            headline="IMD Yellow Bulletin Nowcast",
            description="Thunderstorm accompanied with lightning and gusty winds (40-50 kmph).",
            issuing_authority="India Meteorological Department (IMD)",
            is_official_warning=True,
            recommended_action="Take shelter in sturdy buildings. Unplug electronic appliances.",
            duration_hours=6
        )
        assert official_rec.is_official_warning is True
        assert official_rec.issuing_authority == "India Meteorological Department (IMD)"

        # 5. Auto-expiration test: set expiry_timestamp to past
        official_rec.expiry_timestamp = now - timedelta(minutes=5)
        db.commit()

        # Re-query triggers auto-expiry
        active_after = mgr.get_active_alerts(db=db, hazard_type="thunderstorm")
        active_ids = [a["alert_id"] for a in active_after]
        assert official_rec.alert_id not in active_ids

        # In DB, state transitioned to EXPIRED
        db.refresh(official_rec)
        assert official_rec.lifecycle_status == "EXPIRED"

    finally:
        db.close()


def test_api_active_alerts_endpoint():
    """Verify GET /api/hazards/alerts/active returns filtered active alerts across hazards."""
    res = client.get("/api/hazards/alerts/active")
    assert res.status_code == 200
    data = res.json()
    assert "active_alert_count" in data or "count" in data
    assert "alerts" in data
    assert isinstance(data["alerts"], list)


# -------------------------------------------------------------------------
# 8. Schema Migration Ledger & Non-Destructive Storage
# -------------------------------------------------------------------------

def test_migration_004_applied_and_tables_exist():
    """Verify migration 004 is recorded in schema_migrations ledger and multi-hazard tables exist."""
    db: Session = SessionLocal()
    try:
        m004 = db.query(SchemaMigration).filter(SchemaMigration.version.like("004%")).first()
        assert m004 is not None

        # Verify tables accept records
        sample_assessment = HazardAssessment(
            assessment_id="TEST_ASSESS_HEAT_001",
            study_area_id="MUM_WARD_L_KURLA",
            locality_name="Ward L (Kurla - Sakinaka)",
            hazard_type="heatwave",
            risk_category="MODERATE",
            risk_score=5.5,
            horizon_hours=24,
            assessment_time=datetime.now(timezone.utc),
            valid_start_time=datetime.now(timezone.utc),
            valid_end_time=datetime.now(timezone.utc) + timedelta(hours=24),
            model_version="EIDT-Heat-v1.0",
            confidence_status="OPERATIONAL",
            contributing_factors={"max_temp": 36.5, "heat_index": 44.2}
        )
        db.add(sample_assessment)
        db.commit()
        db.refresh(sample_assessment)
        assert sample_assessment.assessment_id is not None

        # Clean up test row
        db.delete(sample_assessment)
        db.commit()
    finally:
        db.close()
