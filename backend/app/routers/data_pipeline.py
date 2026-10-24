from fastapi import APIRouter, Query, BackgroundTasks, Depends
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.schema import DataProvenanceLog
from app.schemas.api_schemas import DataProvenanceLogResponse
from app.ingestion.pipeline_runner import pipeline_runner
from app.ingestion.registry import get_registry_summary

router = APIRouter(prefix="/data-pipeline", tags=["Automated Data Acquisition & Extraction"])

@router.get("/status")
def get_pipeline_status():
    """
    Returns real-time status of all 8 data source connectors, authentication state,
    provenance timestamps, and records ingested.
    """
    return pipeline_runner.get_pipeline_status()

@router.get("/registry")
def get_data_registry():
    """
    Returns the formal documentation registry for all geospatial and environmental datasets.
    """
    return {
        "title": "Earth Intelligence Digital Twin - Data Source Registry",
        "study_area": "Mumbai Metropolitan Region, Maharashtra, India",
        "datasets": get_registry_summary()
    }

@router.post("/trigger")
def trigger_ingestion(
    source_id: Optional[str] = Query(None, description="Specific connector ID or None for all"),
    background_tasks: BackgroundTasks = None
):
    """
    Triggers an automated acquisition run across connectors.
    """
    if source_id:
        result = pipeline_runner.run_connector(source_id)
        return {
            "message": f"Ingestion completed for connector '{source_id}'.",
            "result": result
        }
    else:
        # Run all connectors
        results = pipeline_runner.run_all()
        return {
            "message": "Full automated data acquisition pipeline completed successfully.",
            "results": results
        }


@router.get("/provenance", response_model=List[DataProvenanceLogResponse])
def get_provenance_logs(
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    limit: Optional[int] = Query(100, description="Max logs to return"),
    db: Session = Depends(get_db)
):
    """
    Returns automated data pipeline provenance audit logs.
    """
    query = db.query(DataProvenanceLog)
    if source_id:
        query = query.filter(DataProvenanceLog.source_id == source_id)
    return query.order_by(DataProvenanceLog.retrieval_timestamp.desc()).limit(limit).all()

