"""
Validation & Model Calibration API Router (Phase 6)
EIDT Maharashtra — Scientific Disaster Validation & Historical Evaluation

Endpoints:
- GET /api/validation/readiness (Multi-hazard audit matrix)
- GET /api/validation/events (Documented historical disaster event catalogue)
- GET /api/validation/events/{event_id} (Specific historical disaster event details)
- GET /api/validation/datasets (Available evaluation datasets)
- POST /api/validation/runs (Trigger audited model evaluation run)
- GET /api/validation/runs (List historical evaluation runs)
- GET /api/validation/runs/{run_id} (Details of specific evaluation run)
- GET /api/validation/runs/{run_id}/metrics (Specific run contingency metrics)
- GET /api/models/{model_id}/validation (Model validation profile)
- GET /api/models/{model_id}/calibration (Model probability calibration profile)
- POST /api/models/{model_id}/calibration (Trigger model calibration run)
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.schema import (
    HistoricalHazardEvent,
    EvaluationDataset,
    EvaluationRun,
    EvaluationMetric,
    ModelCalibrationRun
)
from app.services.validation_service import HistoricalValidationService

router = APIRouter(prefix="/validation", tags=["Scientific Validation & Calibration (Phase 6)"])


class EvaluationRunRequest(BaseModel):
    model_id: str = Field("flood_rf_v2_1", description="Identifier of the model to evaluate")
    split_to_evaluate: str = Field("TEST", description="Split to evaluate: 'TEST' (held-out 2020-2023) or 'TRAIN' (2005-2019)")


class ModelCalibrationRequest(BaseModel):
    model_id: str = Field("flood_rf_v2_1", description="Identifier of the model to calibrate")


@router.get("/readiness")
def get_hazard_readiness(db: Session = Depends(get_db)):
    """
    Returns the comprehensive Phase 6A hazard readiness table across all 6 disaster hazards.
    Honest classification: Ready, Limited, or Insufficient reference data.
    """
    service = HistoricalValidationService(db)
    readiness = service.get_readiness_audit()
    return {
        "status": "success",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_hazards_audited": len(readiness),
        "hazards": readiness
    }


@router.get("/events")
def list_historical_events(
    hazard_type: Optional[str] = Query(None, description="Filter by hazard type (FLOOD, LANDSLIDE, HEATWAVE, etc.)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Lists documented historical disaster events in Maharashtra with verified source provenance.
    """
    service = HistoricalValidationService(db)
    events, total = service.list_events(hazard_type=hazard_type, limit=limit, offset=offset)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": events
    }


@router.get("/events/{event_id}")
def get_event_detail(event_id: str, db: Session = Depends(get_db)):
    """
    Retrieves complete provenance records and meteorological metrics for a specific historical disaster.
    """
    service = HistoricalValidationService(db)
    event = service.get_event_detail(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Historical event '{event_id}' not found")
    return event


@router.get("/datasets")
def list_evaluation_datasets(db: Session = Depends(get_db)):
    """
    Returns evaluation datasets with strict temporal splits, sample counts, and leakage controls.
    """
    service = HistoricalValidationService(db)
    datasets = service.list_evaluation_datasets()
    return {
        "total": len(datasets),
        "datasets": datasets
    }


@router.post("/runs")
def trigger_evaluation_run(
    req: EvaluationRunRequest,
    db: Session = Depends(get_db)
):
    """
    Executes an audited model evaluation against the historical dataset.
    Requires specifying whether to evaluate on held-out TEST or diagnostic TRAIN data.
    """
    split = req.split_to_evaluate.upper()
    if split not in ["TEST", "TRAIN"]:
        raise HTTPException(status_code=400, detail="split_to_evaluate must be 'TEST' or 'TRAIN'")
    
    service = HistoricalValidationService(db)
    result = service.execute_flood_evaluation_run(
        model_id=req.model_id,
        split_to_evaluate=split
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("reason", "Evaluation failed"))

    return result


@router.get("/runs")
def list_evaluation_runs(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Lists completed model evaluation runs."""
    runs = db.query(EvaluationRun).order_by(desc(EvaluationRun.executed_at)).limit(limit).all()
    return {
        "total": len(runs),
        "runs": [
            {
                "run_id": r.run_id,
                "model_id": r.model_id,
                "model_version": r.model_version,
                "hazard_type": r.hazard_type,
                "evaluation_type": r.evaluation_type,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
                "sample_size": r.sample_size,
                "status": r.status,
                "limitation_notes": r.limitation_notes
            }
            for r in runs
        ]
    }


@router.get("/runs/{run_id}")
def get_evaluation_run_detail(run_id: str, db: Session = Depends(get_db)):
    """Retrieves full details of a specific evaluation run."""
    run = db.query(EvaluationRun).filter_by(run_id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Evaluation run '{run_id}' not found")
    
    metrics = db.query(EvaluationMetric).filter_by(run_id=run_id).all()
    return {
        "run_id": run.run_id,
        "model_id": run.model_id,
        "model_version": run.model_version,
        "hazard_type": run.hazard_type,
        "evaluation_type": run.evaluation_type,
        "executed_at": run.executed_at.isoformat() if run.executed_at else None,
        "sample_size": run.sample_size,
        "status": run.status,
        "limitation_notes": run.limitation_notes,
        "metrics": [
            {
                "metric_name": m.metric_name,
                "metric_value": float(m.metric_value),
                "baseline_value": float(m.baseline_value) if m.baseline_value is not None else None,
                "sample_size": m.sample_size,
                "metric_definition": m.metric_definition
            }
            for m in metrics
        ]
    }


@router.get("/runs/{run_id}/metrics")
def get_evaluation_run_metrics(run_id: str, db: Session = Depends(get_db)):
    """Retrieves only the metric records for a run."""
    metrics = db.query(EvaluationMetric).filter_by(run_id=run_id).all()
    if not metrics:
        raise HTTPException(status_code=404, detail=f"No metrics found for run '{run_id}'")
    return {
        "run_id": run_id,
        "metrics": [
            {
                "metric_name": m.metric_name,
                "metric_value": float(m.metric_value),
                "baseline_value": float(m.baseline_value) if m.baseline_value is not None else None,
                "sample_size": m.sample_size,
                "metric_definition": m.metric_definition
            }
            for m in metrics
        ]
    }
