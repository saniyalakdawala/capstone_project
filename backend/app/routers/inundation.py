"""
Flood Inundation & Impact Modelling Router (Phase 2C)
Provides RESTful endpoints for physically defensible flood-inundation extent,
water-depth estimation, asset exposure, road access disruption, and independent validation.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.services.inundation_service import FloodInundationService
from app.schemas.api_schemas import (
    InundationSimulateRequest, InundationSimulationResponse, RoadDisruptionRequest
)

router = APIRouter(prefix="/inundation", tags=["Flood Inundation, Depth & Impact Module (Phase 2C)"])
service = FloodInundationService()


@router.get("/status")
def get_inundation_status():
    """
    Returns operational status, model versions, solver prerequisites, and scientific disclaimers.
    """
    return {
        "module_name": "EIDT Flood Inundation & Impact Module",
        "status": "OPERATIONAL",
        "model_version": service.MODEL_VERSION,
        "selected_active_approach": "COUPLED_HYDRO_TOPOGRAPHIC_INUNDATION",
        "product_classifications_supported": [
            "TERRAIN_SCREENING",
            "RAINFALL_RUNOFF",
            "HYDRO_TOPOGRAPHIC_INUNDATION",
            "OBSERVATION"
        ],
        "external_solver_status": {
            "solver": "HEC-RAS 2D / 2D Saint-Venant Shallow Water",
            "installed": False,
            "status": "UNAVAILABLE_EXTERNAL_SOLVER_NOT_INSTALLED",
            "blocking_prerequisites": [
                "Sub-5m bare-earth LiDAR DEM",
                "Sub-surface storm sewer GIS with pipe diameters/inverts",
                "Mithi River channel bathymetry cross-sections"
            ]
        },
        "spatial_resolution": "30 metres (Copernicus GLO-30 DEM base)",
        "geographic_coverage": "Mumbai Metropolitan Region (MMR Pilot - 10 Municipal Wards & Mithi Basin)",
        "depth_unit": "metres (m)",
        "scientific_disclaimer": (
            "Water-depth estimates are generated via coupled SCS-CN runoff generation and topographic depression ponding. "
            "They do not represent full 2D Navier-Stokes hydrodynamic propagation or building-level doorstep ingress. "
            "Asset exposure indicates geographic intersection, not structural failure."
        )
    }


@router.get("/model-options")
def get_model_options_evaluation():
    """
    Returns comparative evaluation of Option A (Terrain screening), Option B (SCS-CN Runoff),
    and Option C (HEC-RAS 2D hydraulic solver).
    """
    return service.evaluate_model_options()


@router.get("/provenance")
def get_input_dataset_provenance():
    """
    Returns comprehensive dataset provenance, CRS, licences, resolutions, and missing input blockers.
    """
    return service.pipeline.get_provenance_ledger()


@router.post("/simulate", response_model=InundationSimulationResponse)
def execute_inundation_simulation(
    request: InundationSimulateRequest,
    db: Session = Depends(get_db)
):
    """
    Executes a reproducible flood inundation simulation and persists results.
    Validates physical parameter boundaries and records dataset provenance.
    """
    try:
        result = service.run_simulation(
            db=db,
            study_area_id=request.study_area_id,
            rainfall_scenario_mm=request.rainfall_scenario_mm,
            duration_hours=request.duration_hours,
            tide_level_m=request.tide_level_m,
            soil_saturation_pct=request.soil_saturation_pct,
            run_name=request.run_name,
            force_rerun=request.force_rerun
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inundation simulation failed: {str(e)}"
        )


@router.get("/runs")
def list_simulation_runs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Returns list of completed inundation simulations and metadata.
    """
    return service.list_simulation_runs(db=db, limit=limit)


@router.get("/runs/{simulation_id}")
def get_simulation_run_details(
    simulation_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves full simulation diagnostic summary by simulation ID.
    """
    sim = service.get_simulation_by_id(db=db, simulation_id=simulation_id)
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation '{simulation_id}' not found."
        )
    return sim


@router.get("/layers/extent")
def get_inundation_extent_layer(
    simulation_id: Optional[str] = Query(None, description="Simulation run ID"),
    rainfall_scenario_mm: float = Query(200.0, ge=1.0, le=1500.0),
    study_area_id: str = Query("MUM_WARD_L_KURLA"),
    db: Session = Depends(get_db)
):
    """
    Returns GeoJSON FeatureCollection of inundation extent polygons.
    """
    if simulation_id:
        geojson = service.get_simulation_extent_geojson(db=db, simulation_id=simulation_id)
        if not geojson:
            raise HTTPException(status_code=404, detail="Simulation extent not found")
        return geojson

    # Run or retrieve default simulation
    sim = service.run_simulation(
        db=db,
        study_area_id=study_area_id,
        rainfall_scenario_mm=rainfall_scenario_mm,
        force_rerun=False
    )
    geojson = service.get_simulation_extent_geojson(db=db, simulation_id=sim["simulation_id"])
    return geojson


@router.get("/layers/depth")
def get_water_depth_layer(
    simulation_id: Optional[str] = Query(None),
    rainfall_scenario_mm: float = Query(200.0, ge=1.0, le=1500.0),
    study_area_id: str = Query("MUM_WARD_L_KURLA"),
    db: Session = Depends(get_db)
):
    """
    Returns GeoJSON FeatureCollection with depth properties, color classification, and depth bins.
    """
    extent = get_inundation_extent_layer(
        simulation_id=simulation_id,
        rainfall_scenario_mm=rainfall_scenario_mm,
        study_area_id=study_area_id,
        db=db
    )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "depth_legend": {
                "VERY_SHALLOW": {"range": "< 0.15m", "color": "#60a5fa", "label": "Nuisance ponding"},
                "MODERATE": {"range": "0.15m - 0.30m", "color": "#facc15", "label": "Pedestrian disruption"},
                "HIGH": {"range": "0.30m - 0.60m", "color": "#f97316", "label": "Passenger car stall"},
                "SEVERE": {"range": "> 0.60m", "color": "#ef4444", "label": "Emergency vehicle hazard"}
            },
            "depth_unit": "metres",
            "model_version": service.MODEL_VERSION,
            "product_classification": "HYDRO_TOPOGRAPHIC_INUNDATION"
        },
        "features": extent.get("features", [])
    }


@router.get("/impact-summary")
def get_locality_impact_summary(
    rainfall_scenario_mm: float = Query(200.0, ge=1.0, le=1500.0),
    study_area_id: str = Query("MUM_WARD_L_KURLA"),
    db: Session = Depends(get_db)
):
    """
    Returns asset exposure and population estimates for the given flood scenario.
    """
    sim = service.run_simulation(
        db=db,
        study_area_id=study_area_id,
        rainfall_scenario_mm=rainfall_scenario_mm,
        force_rerun=False
    )
    return {
        "study_area_id": study_area_id,
        "rainfall_scenario_mm": rainfall_scenario_mm,
        "product_classification": "HYDRO_TOPOGRAPHIC_INUNDATION",
        "model_version": service.MODEL_VERSION,
        "summary_metrics": sim["summary_metrics"],
        "asset_exposure": sim["asset_exposure"],
        "depth_distribution": sim["depth_distribution"],
        "damage_disclaimer": "Asset exposure counts represent physical intersection with the inundation polygon. They do NOT denote structural destruction."
    }


@router.post("/road-disruption")
def analyze_emergency_road_disruption(
    request: RoadDisruptionRequest
):
    """
    Evaluates road impassability and recalculates emergency Dijkstra route based on
    documented vehicle depth thresholds (0.3m passenger, 0.5m emergency).
    """
    return service.analyze_road_access_disruption(
        origin_coords=request.origin_coords,
        dest_facility_id=request.dest_facility_id,
        rainfall_scenario_mm=request.rainfall_scenario_mm,
        tide_level_m=request.tide_level_m
    )


@router.get("/validation-benchmark")
def get_historical_validation_benchmark(
    event_id: str = Query("DFO_4512_2017", description="Historical flood event benchmark ID")
):
    """
    Returns validation metrics (IoU, CSI, precision, recall) comparing model outputs
    against independent satellite-observed flood extents.
    """
    return service.evaluate_historical_benchmark(event_id=event_id)
