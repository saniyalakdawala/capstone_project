"""
Evacuation Decision Support & Scenario Planning API Router (Phase 4)
Supports aggregate demand-vs-capacity evaluation and hypothetical road-closure scenario testing
without modifying live municipal records.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.models.schema import StudyArea, EmergencyFacility, EvacuationScenario, RoadRestriction, RoadSegment
from app.schemas.api_schemas import EvacuationAssessRequest, EvacuationScenarioCreateRequest

router = APIRouter(prefix="/evacuation", tags=["Evacuation Decision Support (Phase 4)"])


@router.post("/assess")
def assess_ward_evacuation_demand(
    payload: EvacuationAssessRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluates ward-level aggregate evacuation demand against designated municipal shelter capacity.
    Includes explicit assumptions and transparent capacity limitations.
    """
    # Determine which wards to evaluate
    ward_id_list = []
    if payload.ward_ids:
        ward_id_list = payload.ward_ids
    elif payload.ward_id:
        ward_id_list = [payload.ward_id]
    else:
        ward_id_list = ["MUM_WARD_L_KURLA"]

    ward_assessments = []
    total_exposed_pop = 0
    total_shelters_all = 0
    total_capacity_all = 0

    for wid in ward_id_list:
        w_obj = db.query(StudyArea).filter(StudyArea.study_area_id == wid).first()
        w_name = w_obj.name if w_obj else wid
        w_pop = int(w_obj.population) if (w_obj and w_obj.population) else 600000
        w_demand = int(w_pop * (payload.evacuation_demand_pct / 100.0))

        w_shelters = db.query(EmergencyFacility).filter(
            EmergencyFacility.ward_id == wid,
            EmergencyFacility.is_officially_designated_shelter == True,
            EmergencyFacility.operating_status == "OPERATIONAL"
        ).all()

        w_cap = sum(s.capacity_total or 0 for s in w_shelters)
        w_avail = sum(s.capacity_available or 0 for s in w_shelters)
        w_gap = max(0, w_demand - w_cap)
        w_bal = w_cap - w_demand

        total_exposed_pop += w_demand
        total_shelters_all += len(w_shelters)
        total_capacity_all += w_cap

        ward_assessments.append({
            "ward_id": wid,
            "ward_code": wid,
            "ward_name": w_name,
            "ward_population": w_pop,
            "exposed_population_demand": w_demand,
            "designated_shelters_count": len(w_shelters),
            "total_shelter_capacity": w_cap,
            "available_shelter_capacity": w_avail,
            "shelter_capacity_gap_persons": w_gap,
            "capacity_deficit_or_surplus": w_bal,
            "recommended_action": (
                "Sufficient primary municipal shelter capacity available."
                if w_bal >= 0 else
                f"Shelter capacity deficit of {abs(w_bal):,} persons. Mobilize secondary civic schools or initiate inter-ward transfers."
            ),
            "shelters": [
                {
                    "facility_id": s.facility_id,
                    "name": s.name,
                    "capacity_total": s.capacity_total,
                    "capacity_available": s.capacity_available
                }
                for s in w_shelters
            ]
        })

    # Primary focus ward is the first one
    primary = ward_assessments[0] if ward_assessments else {}

    return {
        "assessment_id": f"EVAC_ASSESS_{uuid.uuid4().hex[:8].upper()}",
        "ward_id": primary.get("ward_id", "MUM_WARD_L_KURLA"),
        "ward_name": primary.get("ward_name", "Kurla"),
        "rainfall_scenario_mm": payload.rainfall_scenario_mm,
        "ward_population": primary.get("ward_population", 600000),
        "evacuation_demand_percentage": payload.evacuation_demand_pct,
        "estimated_evacuation_demand_persons": primary.get("exposed_population_demand", 0),
        "designated_shelters_count": primary.get("designated_shelters_count", 0),
        "total_designated_shelter_capacity": primary.get("total_shelter_capacity", 0),
        "available_shelter_capacity": primary.get("available_shelter_capacity", 0),
        "shelter_capacity_gap_persons": primary.get("shelter_capacity_gap_persons", 0),
        "ward_assessments": ward_assessments,
        "operational_recommendation": primary.get("recommended_action", "Assessment completed."),
        "disclaimer": (
            "⚠ DECISION SUPPORT ADVISORY: Aggregate demand is computed from baseline municipal census statistics and scenario assumption. "
            "It does NOT constitute an officially approved evacuation plan or guarantee individual shelter availability."
        ),
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


@router.post("/scenarios")
def create_evacuation_scenario(
    payload: EvacuationScenarioCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a hypothetical planning scenario with custom simulated road closures.
    Does NOT alter live real-time observation feeds.
    """
    scenario_id = f"EVAC_SCEN_{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    # Register hypothetical road restrictions linked to this scenario
    created_restrictions = []
    
    # Handle closed_corridors if provided
    for r_name in payload.closed_corridors:
        matching_road = db.query(RoadSegment).filter(RoadSegment.name.ilike(f"%{r_name}%")).first()
        r_id = f"REST_SCEN_{uuid.uuid4().hex[:8].upper()}"
        restr = RoadRestriction(
            restriction_id=r_id,
            road_segment_id=matching_road.road_segment_id if matching_road else None,
            road_name=r_name,
            restriction_type="SCENARIO_HYPOTHETICAL",
            severity="BLOCKED",
            is_hypothetical_scenario=True,
            scenario_id=scenario_id,
            cause_description=f"Simulated flood closure ({payload.flood_depth_threshold_cm}cm threshold exceeded) under planning scenario '{payload.name}'.",
            issuing_authority="EIDT Emergency Scenario Planner",
            valid_from=now,
            is_active=True,
            created_at=now
        )
        db.add(restr)
        created_restrictions.append({"restriction_id": r_id, "corridor": r_name, "severity": "BLOCKED"})

    # Handle hypothetical_restrictions if provided
    if payload.hypothetical_restrictions:
        for hr in payload.hypothetical_restrictions:
            r_name = hr.get("road_name") or hr.get("corridor") or "Simulated Road Cut"
            r_id = f"REST_SCEN_{uuid.uuid4().hex[:8].upper()}"
            req_seg_id = hr.get("road_segment_id")
            seg_exists = db.query(RoadSegment).filter(RoadSegment.road_segment_id == req_seg_id).first() if req_seg_id else None
            restr = RoadRestriction(
                restriction_id=r_id,
                road_segment_id=seg_exists.road_segment_id if seg_exists else None,
                road_name=r_name,
                restriction_type=hr.get("restriction_type", "SCENARIO_HYPOTHETICAL"),
                severity=hr.get("severity", "BLOCKED"),
                is_hypothetical_scenario=True,
                scenario_id=scenario_id,
                cause_description=hr.get("description") or f"Simulated restriction under {payload.name}",
                issuing_authority="EIDT Emergency Scenario Planner",
                valid_from=now,
                is_active=True,
                created_at=now
            )
            db.add(restr)
            created_restrictions.append({"restriction_id": r_id, "corridor": r_name, "severity": hr.get("severity", "BLOCKED")})

    scenario = EvacuationScenario(
        scenario_id=scenario_id,
        name=payload.name or "Hypothetical Scenario",
        description=payload.description or f"Hypothetical evacuation scenario for {payload.target_ward_id}",
        target_ward_id=payload.target_ward_id,
        active_restrictions=created_restrictions,
        flood_depth_threshold_cm=payload.flood_depth_threshold_cm,
        created_by="EIDT Emergency Planner",
        created_at=now
    )
    db.add(scenario)
    db.commit()

    return {
        "status": "SUCCESS",
        "scenario_id": scenario_id,
        "name": scenario.name,
        "target_ward_id": scenario.target_ward_id,
        "is_hypothetical_scenario": True,
        "simulated_closures_count": len(created_restrictions),
        "simulated_restrictions": created_restrictions,
        "notice": "Hypothetical scenario created. Live road observation feeds remain untampered."
    }


@router.get("/scenarios")
def list_evacuation_scenarios(db: Session = Depends(get_db)):
    """
    Lists saved hypothetical evacuation planning scenarios.
    """
    scenarios = db.query(EvacuationScenario).order_by(EvacuationScenario.created_at.desc()).limit(20).all()
    return {
        "count": len(scenarios),
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "name": s.name,
                "description": s.description,
                "target_ward_id": s.target_ward_id,
                "flood_depth_threshold_cm": float(s.flood_depth_threshold_cm) if s.flood_depth_threshold_cm else 30.0,
                "active_restrictions": s.active_restrictions or [],
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in scenarios
        ]
    }


@router.get("/scenarios/{scenario_id}")
def get_evacuation_scenario(scenario_id: str, db: Session = Depends(get_db)):
    """
    Retrieves full details of a specific hypothetical evacuation planning scenario.
    """
    scen = db.query(EvacuationScenario).filter(EvacuationScenario.scenario_id == scenario_id).first()
    if not scen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evacuation scenario '{scenario_id}' not found."
        )

    return {
        "scenario_id": scen.scenario_id,
        "name": scen.name,
        "description": scen.description,
        "target_ward_id": scen.target_ward_id,
        "flood_depth_threshold_cm": float(scen.flood_depth_threshold_cm) if scen.flood_depth_threshold_cm else 30.0,
        "active_restrictions": scen.active_restrictions or [],
        "created_at": scen.created_at.isoformat() if scen.created_at else None
    }
