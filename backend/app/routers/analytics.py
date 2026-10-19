from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from app.database import get_db
from app.models.schema import Scenario, SimulationResult, StudyArea
from app.schemas.api_schemas import (
    ExposureSummary, RouteAccessibilityRequest, RouteAccessibilityResponse
)
from app.services.network_analysis import network_analyzer

router = APIRouter(tags=["Analytics & Risk Intelligence"])

@router.get("/analytics/exposure")
def get_exposure_analytics(
    scenario_id: Optional[str] = Query("SCEN_HEAVY_200MM", description="Target scenario ID"),
    db: Session = Depends(get_db)
):
    sc = db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
    if not sc:
        sc = db.query(Scenario).first()

    sim = db.query(SimulationResult).filter(SimulationResult.scenario_id == sc.scenario_id).first()
    summary = sim.summary_metrics if sim else {}
    ward_breakdown = sim.ward_breakdown if sim else {}

    ward_exposure_list = []
    if ward_breakdown:
        for wid, wdata in ward_breakdown.items():
            ward_exposure_list.append({
                "ward_id": wid,
                "ward_name": wdata.get("name", wid),
                "exposed_population": wdata.get("exposed_pop", 0),
                "high_risk_area_km2": wdata.get("high_risk_area_km2", 0),
                "risk_category": wdata.get("risk_category", "MODERATE")
            })
    else:
        # Fallback list
        wards = db.query(StudyArea).limit(4).all()
        for w in wards:
            ward_exposure_list.append({
                "ward_id": w.study_area_id,
                "ward_name": w.name,
                "exposed_population": int(w.population * 0.25 if w.population else 120000),
                "high_risk_area_km2": round(float(w.area_sq_km or 10.0) * 0.3, 2),
                "risk_category": "HIGH"
            })

    # Multi-scenario comparison
    all_scenarios = db.query(Scenario).order_by(Scenario.rainfall_total_mm.asc()).all()
    scenario_comparisons = []
    for s in all_scenarios:
        s_sim = db.query(SimulationResult).filter(SimulationResult.scenario_id == s.scenario_id).first()
        m = s_sim.summary_metrics if s_sim else {}
        scenario_comparisons.append({
            "scenario_id": s.scenario_id,
            "scenario_name": s.scenario_name,
            "rainfall_mm": float(s.rainfall_total_mm),
            "high_risk_area_sqkm": m.get("high_risk_area_sqkm", 0),
            "exposed_population": m.get("estimated_exposed_population", 0),
            "affected_roads_count": m.get("affected_road_segments_count", 0),
            "exposed_hospitals_count": m.get("exposed_hospitals_count", 0)
        })

    return {
        "selected_scenario": {
            "scenario_id": sc.scenario_id,
            "scenario_name": sc.scenario_name,
            "rainfall_total_mm": float(sc.rainfall_total_mm),
            "duration_hours": float(sc.duration_hours)
        },
        "summary": summary,
        "ward_exposure": ward_exposure_list,
        "scenario_comparisons": scenario_comparisons,
        "limitations": [
            "Coarse gridded census resolution does not reflect diurnal population mobility (office hours vs night).",
            "Geometric intersection does not equate to physical structural failure of buildings or hospital power plants."
        ]
    }

@router.post("/analytics/accessibility", response_model=RouteAccessibilityResponse)
def analyze_route_accessibility(
    payload: RouteAccessibilityRequest,
    db: Session = Depends(get_db)
):
    rainfall = 200.0
    if payload.scenario_id:
        sc = db.query(Scenario).filter(Scenario.scenario_id == payload.scenario_id).first()
        if sc:
            rainfall = float(sc.rainfall_total_mm)

    res = network_analyzer.analyze_accessibility(
        origin_coords=payload.origin,
        dest_facility_id=payload.destination_facility_id,
        rainfall_mm=rainfall,
        avoid_flooded=payload.avoid_high_risk_roads
    )
    return res

@router.get("/risk-map")
@router.get("/analytics/risk-map")
def get_risk_map_geojson(
    scenario_id: Optional[str] = Query("SCEN_HEAVY_200MM"),
    db: Session = Depends(get_db)
):
    """
    Generates dynamic spatial flood risk zone polygons centered along Mithi River,
    Kurla, Sion, and low-lying coastal flood basins.
    """
    sc = db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
    rainfall = float(sc.rainfall_total_mm) if sc else 200.0

    # Risk polygons geometry around known flood hotspots
    # Expanding buffers and severity based on rainfall
    features = []

    # Hotspot 1: Mithi River Corridor & Kurla West (Highest Risk)
    features.append({
        "type": "Feature",
        "properties": {
            "zone_id": "ZONE_MITHI_KURLA",
            "name": "Mithi River Basin & Kurla Basin",
            "risk_score": min(0.98, 0.40 + rainfall * 0.002),
            "risk_category": "CRITICAL" if rainfall >= 180 else "HIGH",
            "estimated_depth_m": round(0.4 + (rainfall / 300.0) * 1.6, 2),
            "primary_driver": "River overflow & tidal lock"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.862, 19.060], [72.888, 19.062], [72.895, 19.085],
                [72.880, 19.100], [72.860, 19.080], [72.862, 19.060]
            ]]
        }
    })

    # Hotspot 2: Sion - Hindmata Depression (Chronic Urban Waterlogging)
    features.append({
        "type": "Feature",
        "properties": {
            "zone_id": "ZONE_SION_HINDMATA",
            "name": "Sion - Matunga East Lowland",
            "risk_score": min(0.92, 0.35 + rainfall * 0.0019),
            "risk_category": "CRITICAL" if rainfall >= 200 else "HIGH",
            "estimated_depth_m": round(0.3 + (rainfall / 300.0) * 1.2, 2),
            "primary_driver": "Topographic saucer basin & storm drain surcharge"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.852, 19.028], [72.872, 19.028], [72.875, 19.052],
                [72.855, 19.052], [72.852, 19.028]
            ]]
        }
    })

    # Hotspot 3: Dharavi - Mahim Creek Confluence
    features.append({
        "type": "Feature",
        "properties": {
            "zone_id": "ZONE_DHARAVI_MAHIM",
            "name": "Mahim Creek Tidal Transition Zone",
            "risk_score": min(0.88, 0.30 + rainfall * 0.0018),
            "risk_category": "HIGH" if rainfall >= 120 else "MODERATE",
            "estimated_depth_m": round(0.25 + (rainfall / 300.0) * 0.95, 2),
            "primary_driver": "High-tide backwater & high population density"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [72.836, 19.034], [72.858, 19.034], [72.858, 19.052],
                [72.836, 19.052], [72.836, 19.034]
            ]]
        }
    })

    # Hotspot 4: Andheri Subway & Irla Nullah Depression (if rainfall >= 150)
    if rainfall >= 150:
        features.append({
            "type": "Feature",
            "properties": {
                "zone_id": "ZONE_ANDHERI_IRLA",
                "name": "Andheri Subway & Irla Catchment",
                "risk_score": min(0.95, 0.45 + rainfall * 0.0016),
                "risk_category": "CRITICAL",
                "estimated_depth_m": round(0.6 + (rainfall / 300.0) * 1.4, 2),
                "primary_driver": "Railway underpass depression"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [72.835, 19.112], [72.852, 19.112], [72.852, 19.124],
                    [72.835, 19.124], [72.835, 19.112]
                ]]
            }
        })

    return {
        "type": "FeatureCollection",
        "scenario_id": scenario_id,
        "rainfall_mm": rainfall,
        "features": features
    }
