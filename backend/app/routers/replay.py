"""
Historical Disaster Replay API Router (Phase 6G)
EIDT Maharashtra — Historical Hazard Timeline Reconstruction

Endpoints:
- POST /api/replay/runs (Execute isolated historical disaster replay)
- GET /api/replay/runs (List completed replay runs)
- GET /api/replay/runs/{run_id} (Full details and concordance of a replay run)
- GET /api/replay/runs/{run_id}/timeline (Hourly scrubbable progression timeline)
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.schema import HistoricalReplayRun, HistoricalHazardEvent
from app.services.replay_service import HistoricalReplayEngine

router = APIRouter(prefix="/replay", tags=["Historical Disaster Replay (Phase 6)"])


class ReplayExecutionRequest(BaseModel):
    event_id: str = Field(..., description="ID of historical event from catalogue (e.g., 'MUM_EVENT_20050726')")
    replay_mode: str = Field("RETROSPECTIVE_RECONSTRUCTION", description="Mode: 'RETROSPECTIVE_RECONSTRUCTION', 'GENUINE_ARCHIVED_VINTAGE'")
    model_version: str = Field("flood_rf_v2_1", description="Model version to evaluate")


@router.post("/runs")
def trigger_replay_run(
    req: ReplayExecutionRequest,
    db: Session = Depends(get_db)
):
    """
    Executes a historical disaster replay run.
    Guarantees strict isolation: Never modifies live alerts, current observations, or active road restrictions.
    """
    engine = HistoricalReplayEngine(db)
    result = engine.execute_replay(
        event_id=req.event_id,
        replay_mode=req.replay_mode,
        model_version=req.model_version
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("message", "Replay execution failed"))

    return result


@router.get("/runs")
def list_replay_runs(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Lists completed historical replay runs."""
    engine = HistoricalReplayEngine(db)
    runs = engine.list_replay_runs(limit=limit)
    return {
        "total": len(runs),
        "runs": runs
    }


@router.get("/runs/{run_id}")
def get_replay_run_detail(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves full details, input snapshots, predicted outcomes, and observed benchmarks."""
    engine = HistoricalReplayEngine(db)
    run_detail = engine.get_replay_run(run_id)
    if not run_detail:
        raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
    return run_detail


@router.get("/runs/{run_id}/timeline")
def get_replay_run_timeline(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves the scrubbable chronological timeline for the historical disaster replay."""
    engine = HistoricalReplayEngine(db)
    run_detail = engine.get_replay_run(run_id)
    if not run_detail:
        raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
    return {
        "replay_id": run_id,
        "event_id": run_detail["event_id"],
        "replay_name": run_detail["replay_name"],
        "timeline": run_detail["timeline"]
    }
