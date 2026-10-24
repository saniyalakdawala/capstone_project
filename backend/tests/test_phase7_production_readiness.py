"""
Unit and Integration Test Suite — Phase 7: Production Readiness & Maharashtra Scaling
Earth Intelligence Digital Twin (EIDT) — Maharashtra

Validates:
  1. Migration 008 ledger & performance index integrity.
  2. Maharashtra administrative hierarchy (State -> 6 Divisions -> 36 Districts -> Pilot Wards).
  3. Alias resolution for multilingual and alternate district spellings.
  4. OGC polygon topology validation and multi-scale Douglas-Peucker simplification.
  5. Server-side viewport bounding-box spatial query filtering.
  6. Regional spatial tiling (0.25°), checkpointing, and deduplication hashing.
  7. Statewide coverage gap reporting.
  8. Liveness, Readiness, and Data-Readiness health probes.
  9. Observability middleware: X-Correlation-ID header propagation & API metric logging.
  10. Security audit: zero committed credentials in Git repository files.
  11. Disaster recovery: automated backup creation and isolated restore verification.
"""

import os
import sys
import json
import uuid
import pytest
from datetime import datetime, timezone

# Ensure backend and repo root are in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.schema import StudyArea, RegionalIngestionTile, ApiMetricLog
from app.services.geo_hierarchy import (
    MAHARASHTRA_STATE, MAHARASHTRA_DIVISIONS, MAHARASHTRA_DISTRICTS,
    PILOT_WARD_DISTRICT_MAP, seed_maharashtra_hierarchy,
    resolve_locality_by_alias, validate_polygon_topology,
    simplify_geometry_for_zoom
)
from app.services.spatial_tiling import (
    generate_district_tiles, ingest_tile, get_regional_ingestion_summary
)
import scripts.security_audit as security_audit
import scripts.backup_db as backup_db
import scripts.restore_db as restore_db

client = TestClient(app)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    # Ensure hierarchy is seeded before tests
    seed_maharashtra_hierarchy(session)
    yield session
    session.close()


# -------------------------------------------------------------------------
# 1. Database Schema & Migration 008 Integrity
# -------------------------------------------------------------------------
def test_migration_008_ledger(db):
    """Verify Migration 008 is recorded in schema_migrations."""
    from sqlalchemy import text
    try:
        res = db.execute(text("SELECT version, description FROM schema_migrations WHERE version='008_maharashtra_wide_scaling';"))
        row = res.fetchone()
        assert row is not None, "Migration 008 not found in schema_migrations ledger."
    except Exception:
        # SQLite ledger fallback
        res = db.execute(text("SELECT version FROM schema_migrations;"))
        versions = [r[0] for r in res.fetchall()]
        assert any("008" in v for v in versions)


# -------------------------------------------------------------------------
# 2. Maharashtra Geographic Hierarchy & Administrative Architecture
# -------------------------------------------------------------------------
def test_maharashtra_state_hierarchy(db):
    """Verify State, all 6 Divisions, and all 36 Districts exist."""
    state = db.query(StudyArea).filter(StudyArea.study_area_id == "MAH_STATE").first()
    assert state is not None
    assert state.name == "Maharashtra"
    assert state.region_type == "State"
    assert state.population > 100_000_000

    divisions = db.query(StudyArea).filter(StudyArea.region_type == "Division").all()
    assert len(divisions) == 6
    div_ids = {d.study_area_id for d in divisions}
    assert {"DIV_KONKAN", "DIV_PUNE", "DIV_NASHIK", "DIV_CSN", "DIV_AMRAVATI", "DIV_NAGPUR"}.issubset(div_ids)

    districts = db.query(StudyArea).filter(StudyArea.region_type == "District").all()
    assert len(districts) == 36
    for dist in districts:
        assert dist.parent_region_id in div_ids
        assert dist.bounding_box is not None
        assert len(dist.bounding_box) == 4


def test_pilot_wards_linked_to_parents(db):
    """Verify that existing MMR pilot wards are linked to parent districts without data loss."""
    kurla = db.query(StudyArea).filter(StudyArea.study_area_id == "MUM_WARD_L_KURLA").first()
    assert kurla is not None
    assert kurla.parent_region_id == "DIST_MUMBAI_SUB"
    assert kurla.division_id == "DIV_KONKAN"
    assert "DIST_MUMBAI_SUB" in kurla.hierarchy_path

    sion = db.query(StudyArea).filter(StudyArea.study_area_id == "MUM_WARD_FN_SION").first()
    assert sion is not None
    assert sion.parent_region_id == "DIST_MUMBAI_CITY"


def test_multilingual_alias_resolution(db):
    """Verify resolution of alternate spellings, historical names, and Marathi aliases."""
    aurangabad = resolve_locality_by_alias("Aurangabad", db)
    assert aurangabad is not None
    assert aurangabad.study_area_id == "DIST_CSN"

    poona = resolve_locality_by_alias("Poona", db)
    assert poona is not None
    assert poona.study_area_id == "DIST_PUNE"

    ahilyanagar = resolve_locality_by_alias("Ahilyanagar", db)
    assert ahilyanagar is not None
    assert ahilyanagar.study_area_id == "DIST_AHMEDNAGAR"


# -------------------------------------------------------------------------
# 3. Geometry Validation & Multi-Scale Simplification
# -------------------------------------------------------------------------
def test_polygon_topology_validation(db):
    """Verify OGC polygon topology validation correctly accepts valid and flags invalid geometries."""
    pune = db.query(StudyArea).filter(StudyArea.study_area_id == "DIST_PUNE").first()
    is_valid, msg = validate_polygon_topology(pune.geometry)
    assert is_valid is True
    assert "Valid" in msg

    # Invalid geometry (self-intersecting bow-tie polygon)
    invalid_geom = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]
    }
    is_valid, msg = validate_polygon_topology(invalid_geom)
    assert is_valid is False
    assert "Invalid" in msg or "Self-intersection" in msg


def test_douglas_peucker_multi_scale_simplification(db):
    """Verify Level-of-Detail geometry generation for low zoom levels."""
    state = db.query(StudyArea).filter(StudyArea.study_area_id == "MAH_STATE").first()
    raw_geom = state.geometry

    # Zoom 5 (Statewide overview) -> Simplified
    simplified_z5 = simplify_geometry_for_zoom(raw_geom, zoom_level=5)
    assert simplified_z5 is not None
    assert simplified_z5["type"] == "Polygon"

    # Zoom 14 (Detailed view) -> Original geometry preserved
    detailed_z14 = simplify_geometry_for_zoom(raw_geom, zoom_level=14)
    assert detailed_z14 == raw_geom


# -------------------------------------------------------------------------
# 4. Viewport Bounding-Box Spatial Query Filtering
# -------------------------------------------------------------------------
def test_viewport_bounding_box_filtering():
    """Verify server-side spatial clipping to current map viewport."""
    # MMR Bounding Box
    resp = client.get("/api/study-areas?min_lat=18.9&min_lon=72.8&max_lat=19.3&max_lon=73.0")
    assert resp.status_code == 200
    areas = resp.json()
    area_ids = [a["study_area_id"] for a in areas]

    # Should include Mumbai City / Suburban and MMR pilot wards
    assert any("MUM" in aid or "MUMBAI" in aid for aid in area_ids)
    # Should NOT include Eastern Vidarbha (Nagpur / Gadchiroli)
    assert "DIST_GADCHIROLI" not in area_ids
    assert "DIST_NAGPUR" not in area_ids


# -------------------------------------------------------------------------
# 5. Regional Ingestion & Checkpointed Spatial Tiling
# -------------------------------------------------------------------------
def test_spatial_tiling_generation(db):
    """Verify 0.25° spatial tiling decomposes district bounding boxes."""
    tiles = generate_district_tiles("DIST_THANE", db, tile_size_deg=0.25)
    assert len(tiles) >= 2
    for t in tiles:
        assert t.district_id == "DIST_THANE"
        assert t.status in ["IDLE", "COMPLETED", "IN_PROGRESS"]


def test_spatial_tile_ingest_and_hash(db):
    """Verify tile ingestion checkpoints status and computes SHA-256 hash."""
    tiles = generate_district_tiles("DIST_THANE", db, tile_size_deg=0.25)
    target_tile = tiles[0]

    result = ingest_tile(target_tile.tile_id, "WEATHER_IMD", db, dry_run=False)
    assert result["success"] is True
    assert "data_hash" in result
    assert result["records_ingested"] >= 1

    # Verify updated database record
    db.refresh(target_tile)
    assert target_tile.status == "COMPLETED"
    assert target_tile.last_ingested_at is not None


def test_statewide_coverage_gaps_reporting():
    """Verify API reports coverage gaps for districts awaiting ingestion."""
    resp = client.get("/api/regional-ingestion/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_tiles" in data
    assert "statewide_coverage_percentage" in data
    assert "coverage_gaps" in data
    assert isinstance(data["coverage_gaps"], list)


# -------------------------------------------------------------------------
# 6. Backend Reliability & Health Probes (Phase 7F)
# -------------------------------------------------------------------------
def test_health_live_probe():
    """Verify Liveness probe for process monitoring."""
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["uptime_seconds"] >= 0
    assert data["process_id"] > 0


def test_health_ready_probe():
    """Verify Readiness probe tests database connectivity."""
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["ready", "degraded"]
    assert "database_latency_ms" in data
    assert data["database_latency_ms"] >= 0


def test_health_data_readiness_probe():
    """Verify Data Readiness probe explicitly distinguishes app status from data freshness."""
    resp = client.get("/api/health/data-readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "known_limitations" in data
    assert data["study_areas_total"] >= 43


# -------------------------------------------------------------------------
# 7. Observability Middleware & Correlation IDs (Phase 7I)
# -------------------------------------------------------------------------
def test_request_correlation_id_middleware():
    """Verify X-Correlation-ID is propagated through response headers."""
    # Case A: Generated CID
    resp1 = client.get("/api/health")
    assert "x-correlation-id" in resp1.headers
    cid1 = resp1.headers["x-correlation-id"]
    assert len(cid1) > 10

    # Case B: Client-supplied CID preserved
    test_cid = f"test-trace-{uuid.uuid4().hex[:8]}"
    resp2 = client.get("/api/health", headers={"X-Correlation-ID": test_cid})
    assert resp2.headers.get("x-correlation-id") == test_cid


def test_api_metric_logging():
    """Verify requests are logged into api_metric_logs and aggregated by /api/monitoring/metrics."""
    resp = client.get("/api/monitoring/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests_analyzed" in data
    assert "p50_latency_ms" in data
    assert "error_rate_percentage" in data


# -------------------------------------------------------------------------
# 8. Security Audit Validation (Phase 7H)
# -------------------------------------------------------------------------
def test_security_audit_clean():
    """Verify automated security audit finds 0 committed secrets in Git repository."""
    result = security_audit.run_security_audit()
    assert result["status"] == "PASS"
    assert result["violations_count"] == 0
    assert len(result["tracked_env_violations"]) == 0


# -------------------------------------------------------------------------
# 9. Backup & Disaster Recovery Verification (Phase 7J)
# -------------------------------------------------------------------------
def test_backup_and_isolated_restore_verification():
    """Verify automated backup creation and isolated restore test."""
    # 1. Create test backup
    backup_meta = backup_db.backup_database(retention_count=3)
    assert backup_meta.get("backup_file") is not None
    assert backup_meta.get("sha256_checksum") is not None

    # 2. Test restore in isolated temporary database
    backup_file = os.path.join(backup_db.BACKUP_DIR, backup_meta["backup_file"])
    restore_res = restore_db.verify_and_test_restore(backup_file)
    assert restore_res["status"] == "PASS"
    assert restore_res["study_areas_verified"] >= 10
    assert restore_res["migrations_verified"] >= 8
