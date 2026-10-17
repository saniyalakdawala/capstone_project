from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.schema import Scenario, SimulationResult
from app.schemas.api_schemas import (
    ScenarioCreate, ScenarioResponse, SimulationResultResponse
)
from app.services.scenario_engine import scenario_engine

router = APIRouter(tags=["Scenarios & Simulations"])

@router.get("/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.query(Scenario).order_by(Scenario.created_at.desc()).all()
    return scenarios

@router.post("/scenarios")
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)):
    """
    Submits a new rainfall scenario and automatically executes the hydrological simulation.
    """
    res = scenario_engine.run_simulation(
        db=db,
        study_area_id=payload.study_area_id,
        scenario_name=payload.scenario_name,
        rainfall_total_mm=payload.rainfall_total_mm,
        duration_hours=payload.duration_hours,
        assumptions=payload.assumptions or {},
        mitigation_features=payload.mitigation_features or {}
    )
    return res

@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: str, db: Session = Depends(get_db)):
    sc = db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")
    return sc

@router.post("/scenarios/{scenario_id}/run")
def run_scenario_simulation(scenario_id: str, db: Session = Depends(get_db)):
    sc = db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    res = scenario_engine.run_simulation(
        db=db,
        study_area_id=sc.study_area_id,
        scenario_name=sc.scenario_name,
        rainfall_total_mm=float(sc.rainfall_total_mm),
        duration_hours=float(sc.duration_hours),
        assumptions=sc.assumptions or {},
        mitigation_features=sc.mitigation_features or {}
    )
    return res

@router.get("/simulations/{simulation_id}", response_model=SimulationResultResponse)
def get_simulation(simulation_id: str, db: Session = Depends(get_db)):
    res = db.query(SimulationResult).filter(SimulationResult.result_id == simulation_id).first()
    if not res:
        # Also check if user passed scenario_id
        res = db.query(SimulationResult).filter(SimulationResult.scenario_id == simulation_id).first()
    if not res:
        raise HTTPException(status_code=404, detail=f"Simulation result '{simulation_id}' not found.")
    return res

@router.get("/simulations/{simulation_id}/results")
def get_simulation_results(simulation_id: str, db: Session = Depends(get_db)):
    res = db.query(SimulationResult).filter(SimulationResult.result_id == simulation_id).first()
    if not res:
        res = db.query(SimulationResult).filter(SimulationResult.scenario_id == simulation_id).first()
    if not res:
        raise HTTPException(status_code=404, detail=f"Simulation result '{simulation_id}' not found.")
    return {
        "result_id": res.result_id,
        "scenario_id": res.scenario_id,
        "metrics": res.summary_metrics,
        "ward_breakdown": res.ward_breakdown,
        "uncertainty_metadata": res.uncertainty_metadata,
        "generated_at": res.generated_at
    }
