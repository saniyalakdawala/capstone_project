import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "operational"
    assert "version" in data

def test_study_areas():
    res = client.get("/api/study-areas")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    # Check GeoJSON endpoint
    res_geo = client.get("/api/study-areas/geojson")
    assert res_geo.status_code == 200
    geo_data = res_geo.json()
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) >= 1

def test_weather():
    res = client.get("/api/weather")
    assert res.status_code == 200
    data = res.json()
    assert "past_24h_rainfall_mm" in data
    assert "rainfall_trend_7d" in data

def test_infrastructure():
    res = client.get("/api/infrastructure")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

    res_roads = client.get("/api/infrastructure/roads")
    assert res_roads.status_code == 200

def test_flood_events():
    res = client.get("/api/flood-events")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

def test_scenario_creation_and_run():
    payload = {
        "study_area_id": "MUM_WARD_L_KURLA",
        "scenario_name": "Automated Pytest 250mm Simulation",
        "rainfall_total_mm": 250.0,
        "duration_hours": 24.0,
        "assumptions": {
            "soil_saturation_pct": 85,
            "drainage_efficiency_pct": 70,
            "high_tide_height_m": 4.3
        },
        "mitigation_features": {
            "mithi_river_desilting": True,
            "additional_pumping_stations": True,
            "holding_ponds_active": False
        }
    }
    res = client.post("/api/scenarios", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "scenario" in data
    assert "simulation_result" in data
    assert data["simulation_result"]["summary_metrics"]["rainfall_total_mm"] == 250.0
    assert data["simulation_result"]["summary_metrics"]["high_risk_area_sqkm"] > 0

def test_accessibility_routing():
    payload = {
        "origin": [72.845, 19.055],
        "destination_facility_id": "INFRA_HOSP_02",  # Bhabha Hospital Kurla
        "scenario_id": "SCEN_HEAVY_200MM",
        "avoid_high_risk_roads": True
    }
    res = client.post("/api/analytics/accessibility", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "baseline_distance_km" in data
    assert "route_geometry" in data

def test_model_metrics():
    res = client.get("/api/models/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["roc_auc"] > 0.80
    assert len(data["feature_importance"]) >= 5
