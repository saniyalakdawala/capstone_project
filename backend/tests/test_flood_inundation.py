"""
Phase 2C Test Suite: Flood Inundation, Water-Depth and Impact Modelling
Tests:
- Inundation module status, model versions, and external solver availability
- Model options evaluation (Option A screening vs Option B runoff vs Option C hydraulic)
- Input dataset schema, CRS (EPSG:4326 / EGM96), units, resolution, and blockers
- Physical parameter validation and error bounds
- Simulation execution, peak/mean depth, and depth quantiles (<0.15m, 0.15-0.3m, 0.3-0.6m, >0.6m)
- Safe simulation reruns and idempotence
- GeoJSON spatial extents, depth layer formatting, and explicit units
- Asset exposure calculation and strict separation from damage
- Road disruption vehicular depth thresholds (0.3m passenger, 0.5m emergency)
- Independent historical validation against satellite SAR (CSI, IoU, precision, recall)
- Strict separation of product classifications (Observation vs Screening vs Hydro-Topographic)
- Migration 003 tracking in schema_migrations ledger
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.database import SessionLocal
from app.models.schema import SchemaMigration, InundationSimulation, DataProvenanceLog
from app.services.inundation_service import FloodInundationService
from app.services.hydrological_pipeline import HydrologicalInputPipeline

client = TestClient(app)


# -------------------------------------------------------------------------
# 1. Module Status & External Solver Availability
# -------------------------------------------------------------------------

def test_inundation_status_and_solver_availability():
    """Verify /api/inundation/status reports operational status, 30m resolution, and inactive HEC-RAS."""
    res = client.get("/api/inundation/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "OPERATIONAL"
    assert data["model_version"] == "EIDT-Inundation-v2.3"
    assert data["selected_active_approach"] == "COUPLED_HYDRO_TOPOGRAPHIC_INUNDATION"
    assert data["spatial_resolution"] == "30 metres (Copernicus GLO-30 DEM base)"
    assert data["depth_unit"] == "metres (m)"

    # Verify external solver is reported honestly as unavailable
    solver = data["external_solver_status"]
    assert solver["installed"] is False
    assert solver["status"] == "UNAVAILABLE_EXTERNAL_SOLVER_NOT_INSTALLED"
    assert len(solver["blocking_prerequisites"]) >= 3


# -------------------------------------------------------------------------
# 2. Model Options Evaluation
# -------------------------------------------------------------------------

def test_model_options_evaluation():
    """Verify that Option A, Option B, and Option C are evaluated against scientific criteria."""
    res = client.get("/api/inundation/model-options")
    assert res.status_code == 200
    data = res.json()
    approaches = data.get("approaches_evaluated", [])
    assert len(approaches) >= 3

    options = {a["option"].split("—")[0].strip(): a for a in approaches}
    assert "Option A" in options
    assert "Option B" in options
    assert "Option C" in options

    assert options["Option A"]["product_classification"] == "TERRAIN_SCREENING"
    assert options["Option B"]["product_classification"] == "RAINFALL_RUNOFF"
    assert options["Option C"]["product_classification"] == "HYDRAULIC_SIMULATION"
    assert options["Option C"]["solver_installed"] is False


# -------------------------------------------------------------------------
# 3. Input Dataset Provenance & Blockers
# -------------------------------------------------------------------------

def test_dataset_provenance_and_blockers():
    """Verify dataset provenance ledger records CRS, resolution, licence, and blockers."""
    res = client.get("/api/inundation/provenance")
    assert res.status_code == 200
    data = res.json()
    assert "EPSG:4326" in data["coordinate_reference_system"]
    assert "EGM96" in data["coordinate_reference_system"]

    datasets = data.get("datasets", [])
    assert len(datasets) >= 5
    d_names = [d["dataset_name"] for d in datasets]
    assert any("Copernicus GLO-30" in name for name in d_names)
    assert any("OpenStreetMap" in name for name in d_names)
    assert any("Open-Meteo" in name for name in d_names)
    assert any("Tide" in name for name in d_names)
    assert any("Sentinel-1" in name for name in d_names)

    # Check missing dataset blockers
    blockers = data.get("missing_datasets_and_blockers", [])
    assert len(blockers) >= 2
    b_names = [b["name"] for b in blockers]
    assert any("Stormwater" in name for name in b_names)
    assert any("LiDAR" in name for name in b_names)


# -------------------------------------------------------------------------
# 4. Input Boundary Validation
# -------------------------------------------------------------------------

def test_simulation_input_validation():
    """Verify physical bounds validation rejects invalid rainfall, duration, and tide values."""
    # Negative rainfall
    res_neg = client.post("/api/inundation/simulate", json={"rainfall_scenario_mm": -50.0})
    assert res_neg.status_code == 422 or res_neg.status_code == 400

    # Extreme rainfall (>1500mm)
    res_ext = client.post("/api/inundation/simulate", json={"rainfall_scenario_mm": 2000.0})
    assert res_ext.status_code == 422 or res_ext.status_code == 400

    # Invalid duration (<1h)
    res_dur = client.post("/api/inundation/simulate", json={"duration_hours": 0.0})
    assert res_dur.status_code == 422 or res_dur.status_code == 400

    # Invalid tide (>7m)
    res_tide = client.post("/api/inundation/simulate", json={"tide_level_m": 12.0})
    assert res_tide.status_code == 422 or res_tide.status_code == 400


# -------------------------------------------------------------------------
# 5. Simulation Execution & Physical Depth Metrics
# -------------------------------------------------------------------------

def test_simulation_execution_and_metrics():
    """Verify simulation calculates defensible peak depth, mean depth, and depth quantiles."""
    payload = {
        "study_area_id": "MUM_WARD_L_KURLA",
        "rainfall_scenario_mm": 250.0,
        "duration_hours": 24.0,
        "tide_level_m": 4.2,
        "soil_saturation_pct": 80.0,
        "force_rerun": True
    }
    res = client.post("/api/inundation/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["model_type"] == "COUPLED_HYDRO_TOPOGRAPHIC_INUNDATION"
    assert data["product_classification"] == "HYDRO_TOPOGRAPHIC_INUNDATION"
    assert data["spatial_resolution_m"] == 30.0

    sm = data["summary_metrics"]
    assert sm["peak_depth_m"] > 0.3, "250mm cloudburst in Kurla depression must exceed 0.3m"
    assert sm["mean_depth_m"] <= sm["peak_depth_m"]
    assert sm["inundated_area_sq_km"] > 0.0
    assert sm["depth_unit"] == "metres"

    # Depth distribution quantiles
    dd = data["depth_distribution"]
    assert "very_shallow_under_0_15m_sq_km" in dd
    assert "moderate_0_15_to_0_30m_sq_km" in dd
    assert "deep_0_30_to_0_60m_sq_km" in dd
    assert "severe_over_0_60m_sq_km" in dd

    # Asset exposure
    ae = data["asset_exposure"]
    assert ae["exposed_buildings_count"] >= 0
    assert ae["exposed_roads_count"] >= 0
    assert ae["exposed_population_est"] > 0


# -------------------------------------------------------------------------
# 6. Safe Simulation Reruns & Idempotence
# -------------------------------------------------------------------------

def test_simulation_rerun_idempotence():
    """Verify rerunning simulation with identical parameters returns existing record without duplication."""
    payload = {
        "study_area_id": "MUM_WARD_FN_SION",
        "rainfall_scenario_mm": 180.0,
        "duration_hours": 24.0,
        "tide_level_m": 3.8,
        "soil_saturation_pct": 70.0,
        "force_rerun": False
    }
    res1 = client.post("/api/inundation/simulate", json=payload)
    assert res1.status_code == 200
    sim_id_1 = res1.json()["simulation_id"]

    res2 = client.post("/api/inundation/simulate", json=payload)
    assert res2.status_code == 200
    sim_id_2 = res2.json()["simulation_id"]

    assert sim_id_1 == sim_id_2, "Non-forced simulation rerun must return existing simulation ID"


# -------------------------------------------------------------------------
# 7. Spatial Extent & Depth Layers GeoJSON
# -------------------------------------------------------------------------

def test_spatial_extent_and_depth_layers_geojson():
    """Verify extent and depth endpoints return valid GeoJSON FeatureCollections."""
    res_extent = client.get("/api/inundation/layers/extent?study_area_id=MUM_WARD_L_KURLA&rainfall_scenario_mm=200")
    assert res_extent.status_code == 200
    data_ext = res_extent.json()
    assert data_ext["type"] == "FeatureCollection"
    assert len(data_ext["features"]) > 0

    first_f = data_ext["features"][0]
    assert first_f["geometry"]["type"] == "Polygon"
    assert "peak_depth_m" in first_f["properties"]
    assert "depth_category" in first_f["properties"]
    assert first_f["properties"]["depth_unit"] == "metres"

    res_depth = client.get("/api/inundation/layers/depth?study_area_id=MUM_WARD_L_KURLA&rainfall_scenario_mm=200")
    assert res_depth.status_code == 200
    data_depth = res_depth.json()
    assert "metadata" in data_depth
    assert "depth_legend" in data_depth["metadata"]
    legend = data_depth["metadata"]["depth_legend"]
    assert "VERY_SHALLOW" in legend
    assert "MODERATE" in legend
    assert "HIGH" in legend
    assert "SEVERE" in legend


# -------------------------------------------------------------------------
# 8. Asset Exposure & Damage Separation
# -------------------------------------------------------------------------

def test_impact_summary_and_damage_disclaimer():
    """Verify impact summary reports exposure counts and explicitly disclaims structural damage."""
    res = client.get("/api/inundation/impact-summary?study_area_id=MUM_WARD_L_KURLA&rainfall_scenario_mm=200")
    assert res.status_code == 200
    data = res.json()
    assert "asset_exposure" in data
    assert "damage_disclaimer" in data
    assert "structural" in data["damage_disclaimer"].lower() or "intersection" in data["damage_disclaimer"].lower()


# -------------------------------------------------------------------------
# 9. Road Disruption & Vehicular Depth Thresholds
# -------------------------------------------------------------------------

def test_road_disruption_thresholds():
    """Verify road disruption uses 0.3m passenger and 0.5m emergency depth thresholds."""
    payload = {
        "origin_coords": [72.880, 19.065],  # Kurla West Station
        "dest_facility_id": "HOSP_BHABHA_KURLA",
        "rainfall_scenario_mm": 250.0,
        "tide_level_m": 4.5
    }
    res = client.post("/api/inundation/road-disruption", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["product_classification"] == "MODELLED_ACCESS_DISRUPTION"
    thresholds = data.get("vehicular_depth_thresholds", {})
    assert thresholds.get("passenger_vehicle_stall_depth_m") == 0.30
    assert thresholds.get("emergency_ambulance_impassable_depth_m") == 0.50
    assert "operational_warning" in data


# -------------------------------------------------------------------------
# 10. Independent Historical Validation Against Satellite SAR
# -------------------------------------------------------------------------

def test_historical_validation_benchmarks():
    """Verify comparison against 2017 Mumbai deluge Sentinel-1 SAR reference reports CSI, IoU, and limitations."""
    res = client.get("/api/inundation/validation-benchmark?event_id=DFO_4512_2017")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VALIDATED"
    metrics = data["metrics"]
    assert "Sentinel-1" in metrics["reference_sensor"]
    assert metrics["critical_success_index_csi"] >= 0.70
    assert metrics["intersection_over_union_iou"] >= 0.70
    assert metrics["precision"] >= 0.80
    assert metrics["recall"] >= 0.80
    assert "limitations" in metrics


# -------------------------------------------------------------------------
# 11. Strict Separation of Product Classifications
# -------------------------------------------------------------------------

def test_strict_separation_of_product_classifications():
    """Verify observations, screening, runoff, and hydro-topographic products are strictly demarcated."""
    # 1. Observations endpoint
    res_obs = client.get("/api/flood/observations")
    assert res_obs.status_code == 200
    obs_data = res_obs.json()
    assert obs_data["dataset_classification"] == "HISTORICAL_OBSERVATIONS_GROUND_TRUTH"

    # 2. Inundation extent endpoint
    res_inun = client.get("/api/inundation/layers/extent")
    assert res_inun.status_code == 200
    first_feat = res_inun.json()["features"][0]
    assert first_feat["properties"]["product_classification"] == "HYDRO_TOPOGRAPHIC_INUNDATION"

    # 3. Model options endpoint
    res_opts = client.get("/api/inundation/model-options")
    assert res_opts.status_code == 200
    opts = res_opts.json()["approaches_evaluated"]
    classifications = {o["product_classification"] for o in opts}
    assert "TERRAIN_SCREENING" in classifications
    assert "RAINFALL_RUNOFF" in classifications
    assert "HYDRAULIC_SIMULATION" in classifications
    assert "HYDRO_TOPOGRAPHIC_INUNDATION" in classifications


# -------------------------------------------------------------------------
# 12. Migration 003 Tracking & Database Persistence
# -------------------------------------------------------------------------

def test_migration_003_recorded_in_schema_migrations():
    """Verify migration 003_inundation_simulation_pipeline is recorded in ledger."""
    db = SessionLocal()
    try:
        mig = db.query(SchemaMigration).filter(
            SchemaMigration.version == "003_inundation_simulation_pipeline"
        ).first()
        assert mig is not None, "Migration 003 must be recorded in schema_migrations ledger"

        # Verify simulation records are persisted
        sim_count = db.query(InundationSimulation).count()
        assert sim_count >= 1, "At least one simulation record must exist in database"
    finally:
        db.close()
