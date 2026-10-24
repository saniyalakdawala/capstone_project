import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal, get_db
from app.models.schema import (
    StudyArea, Infrastructure, RoadSegment, Building, LocalityAlert,
    DataProvenanceLog, SchemaMigration, Scenario
)
from database.migrate import run_migrations

client = TestClient(app)

def test_migration_tracking_and_idempotence():
    """Verify that migration ledger tracks 001_regional_mmr_foundation and rerun is idempotent."""
    db = SessionLocal()
    try:
        mig = db.query(SchemaMigration).filter(SchemaMigration.version == "001_regional_mmr_foundation").first()
        assert mig is not None, "Migration 001_regional_mmr_foundation must be recorded in schema_migrations"
        
        # Test running migrations again returns 0 new migrations
        new_applied = run_migrations()
        assert new_applied == 0, "Re-running migrations should be idempotent and apply 0 new migrations"
    finally:
        db.close()

def test_study_areas_hierarchy_fields():
    """Verify that StudyArea model and API responses include regional hierarchy fields."""
    res = client.get("/api/study-areas")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 10, "Existing study areas must be preserved"
    
    first = data[0]
    assert "parent_region_id" in first
    assert "region_type" in first
    assert "hierarchy_path" in first

    # Check GeoJSON endpoint
    res_geo = client.get("/api/study-areas/geojson")
    assert res_geo.status_code == 200
    props = res_geo.json()["features"][0]["properties"]
    assert "region_type" in props
    assert "parent_region_id" in props

def test_infrastructure_locality_fields():
    """Verify that Infrastructure records contain locality_name and sub_ward fields."""
    res = client.get("/api/infrastructure")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 30, "Existing infrastructure records must be preserved"
    
    first = data[0]
    assert "locality_name" in first
    assert "sub_ward" in first

def test_road_segments_locality_fields():
    """Verify that RoadSegment records contain locality_name and elevation_m fields."""
    res = client.get("/api/infrastructure/roads?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    
    first = data[0]
    assert "locality_name" in first
    assert "elevation_m" in first

def test_buildings_endpoints():
    """Verify that Building query and GeoJSON endpoints are operational."""
    res = client.get("/api/infrastructure/buildings")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res_geo = client.get("/api/infrastructure/buildings/geojson")
    assert res_geo.status_code == 200
    data = res_geo.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)

def test_locality_alerts_endpoint():
    """Verify that LocalityAlert query endpoint is operational."""
    res = client.get("/api/infrastructure/alerts")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_data_provenance_logs_endpoint():
    """Verify that DataProvenanceLog query endpoint is operational."""
    res = client.get("/api/data-pipeline/provenance")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_existing_records_preserved():
    """Verify that user records in existing tables remain intact after schema modifications."""
    db = SessionLocal()
    try:
        sa_count = db.query(StudyArea).count()
        infra_count = db.query(Infrastructure).count()
        roads_count = db.query(RoadSegment).count()
        scenarios_count = db.query(Scenario).count()
        
        assert sa_count >= 10, f"Expected >= 10 study areas, found {sa_count}"
        assert infra_count >= 35, f"Expected >= 35 infrastructure items, found {infra_count}"
        assert roads_count >= 6700, f"Expected >= 6700 road segments, found {roads_count}"
        assert scenarios_count >= 9, f"Expected >= 9 scenarios, found {scenarios_count}"
    finally:
        db.close()

def test_no_hardcoded_google_key_in_frontend():
    """Verify frontend/app.js does not contain hardcoded Google Maps API key fallback."""
    frontend_app_js = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "app.js"))
    with open(frontend_app_js, "r", encoding="utf-8") as f:
        content = f.read()
    
    import re
    # Check for hardcoded API key pattern in frontend code
    matches = re.findall(r"AIza[0-9A-Za-z_-]{35}", content)
    assert len(matches) == 0, "No hardcoded Google API key should exist in frontend/app.js"
