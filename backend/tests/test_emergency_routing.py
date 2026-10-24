import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import get_db, SessionLocal
from app.models.schema import SchemaMigration, EmergencyFacility, RoadRestriction

client = TestClient(app)

def test_migration_005_ledger():
    """Verify that migration 005_emergency_routing_platform.sql is recorded in the ledger."""
    db = SessionLocal()
    try:
        mig = db.query(SchemaMigration).filter(
            SchemaMigration.version.like("%005_emergency_routing_platform%")
        ).first()
        assert mig is not None, "Migration 005 must be registered in schema_migrations"
    finally:
        db.close()

def test_routing_status_and_network_metadata():
    """Verify routing status, coverage, and metadata endpoints return real graph metrics."""
    res = client.get("/api/routing/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"].upper() in ["READY", "OPERATIONAL"]
    assert data["node_count"] >= 5000, "Real road graph should have at least 5000 nodes"
    assert data["directed_edge_count"] >= 10000, "Real road graph should have at least 10000 directed edges"
    assert data["connectivity_ratio"] >= 0.90, "Network should have >=90% largest component connectivity"
    assert len(data["spatial_bounding_box"]) == 4

    # Coverage endpoint
    res_cov = client.get("/api/routing/network/coverage")
    assert res_cov.status_code == 200
    cov = res_cov.json()
    assert "spatial_bounding_box" in cov
    assert "total_network_length_km" in cov
    assert cov["total_network_length_km"] >= 500.0

    # Metadata endpoint
    res_meta = client.get("/api/routing/network/metadata")
    assert res_meta.status_code == 200
    meta = res_meta.json()
    assert "supported_routing_modes" in meta
    assert meta["licence_and_attribution"]["dataset"] == "OpenStreetMap Road Network"

def test_route_calculation_success():
    """Verify route calculation between Kurla and Sion using real road network."""
    # Origin: Kurla West [19.068, 72.879], Destination: Sion Hospital [19.034, 72.862]
    payload = {
        "origin_latitude": 19.0680,
        "origin_longitude": 72.8790,
        "destination_latitude": 19.0340,
        "destination_longitude": 72.8620,
        "routing_cost": "hazard_aware",
        "avoid_waterlogged": True,
        "avoid_closed_roads": True
    }
    res = client.post("/api/routing/route", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "SUCCESS"
    assert data["distance_km"] > 0
    assert data["distance_km"] < 25.0, "Kurla-Sion route should be reasonable urban distance"
    assert data["estimated_duration_minutes"] is not None
    assert data["route_geojson"] is not None
    assert data["route_geojson"]["type"] == "LineString"
    assert len(data["route_geojson"]["coordinates"]) >= 5

    # Safety disclaimer requirement (Rule 6)
    assert "uncertainty_and_safety_notice" in data
    assert len(data["uncertainty_and_safety_notice"]) >= 2
    safety_text = " ".join(data["uncertainty_and_safety_notice"]).lower()
    assert "not a guarantee of safety" in safety_text or "uncertainty" in safety_text

def test_route_calculation_modes():
    """Verify shortest distance and fastest travel time routing modes."""
    base_payload = {
        "origin_latitude": 19.0680,
        "origin_longitude": 72.8790,
        "destination_latitude": 19.0340,
        "destination_longitude": 72.8620
    }

    # Shortest mode
    res_short = client.post("/api/routing/route", json={**base_payload, "routing_cost": "shortest"})
    assert res_short.status_code == 200
    assert res_short.json()["status"] == "SUCCESS"

    # Fastest mode
    res_fast = client.post("/api/routing/route", json={**base_payload, "routing_cost": "fastest"})
    assert res_fast.status_code == 200
    assert res_fast.json()["status"] == "SUCCESS"

def test_alternative_routes_generation():
    """Verify alternative corridor generation using Yen's k-shortest paths."""
    payload = {
        "origin_latitude": 19.0680,
        "origin_longitude": 72.8790,
        "destination_latitude": 19.0340,
        "destination_longitude": 72.8620,
        "k_alternatives": 2,
        "routing_cost": "hazard_aware"
    }
    res = client.post("/api/routing/alternatives", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert "alternative_corridors" in data
    assert len(data["alternative_corridors"]) >= 1

def test_nearest_facility_routing():
    """Verify routing to the nearest reachable emergency facility."""
    # Find nearest hospital from Kurla
    payload_hosp = {
        "origin_latitude": 19.0680,
        "origin_longitude": 72.8790,
        "facility_type": "hospital",
        "routing_cost": "hazard_aware"
    }
    res_hosp = client.post("/api/routing/nearest-facility", json=payload_hosp)
    assert res_hosp.status_code == 200
    data_hosp = res_hosp.json()
    assert data_hosp["status"] == "SUCCESS"
    assert data_hosp["destination_facility_name"] is not None

    # Find nearest shelter from Dharavi
    payload_shelter = {
        "origin_latitude": 19.0430,
        "origin_longitude": 72.8550,
        "facility_type": "shelter",
        "routing_cost": "hazard_aware"
    }
    res_shelter = client.post("/api/routing/nearest-facility", json=payload_shelter)
    assert res_shelter.status_code == 200
    data_shelter = res_shelter.json()
    assert data_shelter["status"] == "SUCCESS"

def test_out_of_bounds_coordinates():
    """Verify out-of-bounds origins return 404 with structured coverage bounds."""
    payload = {
        "origin_latitude": 18.5204,  # Pune coordinates (outside MMR network)
        "origin_longitude": 73.8567,
        "destination_latitude": 19.0340,
        "destination_longitude": 72.8620
    }
    res = client.post("/api/routing/route", json=payload)
    assert res.status_code == 404
    data = res.json()
    assert "outside" in str(data).lower()

def test_invalid_coordinates_validation():
    """Verify coordinates out of geographic range return 422 validation errors."""
    payload = {
        "origin_lat": 190.0,  # Invalid latitude > 90
        "origin_lon": 72.8790,
        "destination_lat": 19.0340,
        "destination_lon": 72.8620
    }
    res = client.post("/api/routing/route", json=payload)
    assert res.status_code == 422

def test_emergency_facilities_list_and_filters():
    """Verify verified emergency facilities registry and category filtering."""
    # All facilities
    res_all = client.get("/api/emergency/facilities")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert data_all["total_count"] >= 40

    # Shelters only
    res_shelters = client.get("/api/emergency/facilities?shelter_only=true")
    assert res_shelters.status_code == 200
    data_shelters = res_shelters.json()
    assert data_shelters["total_count"] >= 10
    for fac in data_shelters["facilities"]:
        assert fac["is_officially_designated_shelter"] is True

    # Hospitals only
    res_hosp = client.get("/api/emergency/facilities?facility_type=hospital")
    assert res_hosp.status_code == 200
    data_hosp = res_hosp.json()
    assert data_hosp["total_count"] >= 20
    for fac in data_hosp["facilities"]:
        assert fac["facility_type"] == "hospital"
        # Hospitals must NOT be assumed to be general shelters
        assert fac["is_officially_designated_shelter"] is False

def test_nearby_facilities():
    """Verify nearby facility spatial search around Kurla."""
    res = client.get("/api/emergency/facilities/nearby?latitude=19.0680&longitude=72.8790&radius_km=3.0")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 1
    for fac in data["facilities"]:
        assert "distance_km" in fac
        assert fac["distance_km"] <= 3.0

def test_evacuation_demand_assessment():
    """Verify ward population demand vs shelter capacity evaluation."""
    payload = {
        "rainfall_scenario": "SCEN_HEAVY_200MM",
        "ward_ids": ["MUM_WARD_L_KURLA", "MUM_WARD_F_NORTH"]
    }
    res = client.post("/api/evacuation/assess", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "ward_assessments" in data
    assert len(data["ward_assessments"]) >= 1
    for w in data["ward_assessments"]:
        assert "exposed_population_demand" in w
        assert "total_shelter_capacity" in w
        assert "capacity_deficit_or_surplus" in w
        assert "recommended_action" in w

def test_hypothetical_scenario_creation_and_isolation():
    """Verify hypothetical scenarios do not alter live operational restrictions."""
    # Live restrictions count before scenario
    res_before = client.get("/api/emergency/restrictions")
    assert res_before.status_code == 200
    count_before = res_before.json()["total_count"]

    # Create hypothetical scenario
    scenario_payload = {
        "scenario_name": "Test Simulated BKC Waterlogging Closure",
        "scenario_type": "hypothetical_road_closure",
        "description": "Simulating localized underpass flooding for training exercise",
        "hypothetical_restrictions": [
            {
                "road_segment_id": "RS_OSM_4216834",
                "road_name": "BKC Connector Southbound",
                "restriction_type": "closure",
                "latitude": 19.0600,
                "longitude": 72.8550
            }
        ]
    }
    res_scen = client.post("/api/evacuation/scenarios", json=scenario_payload)
    assert res_scen.status_code == 200
    scen_data = res_scen.json()
    assert scen_data["is_hypothetical_scenario"] is True

    # Live restrictions count after scenario (must remain identical)
    res_after = client.get("/api/emergency/restrictions")
    assert res_after.status_code == 200
    count_after = res_after.json()["total_count"]
    assert count_before == count_after, "Hypothetical scenario must NOT pollute live restrictions feed"
