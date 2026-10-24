"""
Real-Time Monitoring and Data Ingestion API Router (Phase 5)
Provides system and source health observability, scheduled ingestion job history,
bounded observation feeds, data quality reports, and controlled job execution.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.schema import (
    SourceHealthRecord,
    ScheduledIngestionJob,
    IngestedObservation,
    DataProvenanceLog
)
from app.services.monitoring_service import MonitoringService, PHYSICAL_BOUNDS
from app.services.scheduler_service import get_orchestration_scheduler

router = APIRouter(prefix="/monitoring", tags=["Real-Time Monitoring & Ingestion (Phase 5)"])


@router.get("/status")
def get_monitoring_overview(db: Session = Depends(get_db)):
    """
    Returns high-level system monitoring overview:
    - Status breakdown across all registered sources (healthy, delayed, stale, unavailable, not_configured)
    - Recent scheduled job executions
    - Ingestion freshness summary
    """
    monitoring = MonitoringService(db)
    monitoring.sync_source_catalog()
    
    sources = db.query(SourceHealthRecord).all()
    status_counts = {}
    for s in sources:
        status_counts[s.health_status] = status_counts.get(s.health_status, 0) + 1

    recent_jobs = db.query(ScheduledIngestionJob).order_by(
        desc(ScheduledIngestionJob.created_at)
    ).limit(10).all()

    scheduler = get_orchestration_scheduler()

    return {
        "status": "OPERATIONAL",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler.is_running,
        "source_counts": {
            "total": len(sources),
            "by_health_status": status_counts
        },
        "recent_jobs_count": len(recent_jobs),
        "recent_jobs": [
            {
                "job_id": j.job_id,
                "job_name": j.job_name,
                "source_id": j.source_id,
                "status": j.status,
                "records_retrieved": j.records_retrieved,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "execution_log": j.execution_log
            }
            for j in recent_jobs
        ]
    }


@router.get("/sources")
def list_monitoring_sources(
    category: Optional[str] = Query(None, description="Filter by source category"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    db: Session = Depends(get_db)
):
    """
    Returns the real-time health, cadence, and freshness state for all data connectors.
    Evaluates elapsed time against individual source thresholds.
    """
    monitoring = MonitoringService(db)
    monitoring.sync_source_catalog()
    monitoring.reevaluate_all_freshness()

    query = db.query(SourceHealthRecord)
    if category:
        query = query.filter(SourceHealthRecord.category == category)
    if health_status:
        query = query.filter(SourceHealthRecord.health_status == health_status)

    sources = query.order_by(SourceHealthRecord.source_name).all()

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(sources),
        "sources": [
            {
                "source_id": s.source_id,
                "source_name": s.source_name,
                "category": s.category,
                "health_status": s.health_status,
                "freshness_threshold_minutes": s.freshness_threshold_minutes,
                "expected_cadence_minutes": s.expected_cadence_minutes,
                "last_successful_retrieval": s.last_successful_retrieval.isoformat() if s.last_successful_retrieval else None,
                "last_attempt_at": s.last_attempt_at.isoformat() if s.last_attempt_at else None,
                "consecutive_failures": s.consecutive_failures,
                "error_details": s.error_details,
                "records_count": s.records_count,
                "metrics": s.metrics,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None
            }
            for s in sources
        ]
    }


@router.get("/sources/{source_id}")
def get_source_detail(source_id: str, db: Session = Depends(get_db)):
    """Returns detailed health record, observation count, and latest readings for a source."""
    source = db.query(SourceHealthRecord).filter_by(source_id=source_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found in registry."
        )

    recent_obs = db.query(IngestedObservation).filter_by(
        source_id=source_id
    ).order_by(desc(IngestedObservation.retrieved_at)).limit(10).all()

    return {
        "source": {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "category": source.category,
            "health_status": source.health_status,
            "freshness_threshold_minutes": source.freshness_threshold_minutes,
            "expected_cadence_minutes": source.expected_cadence_minutes,
            "last_successful_retrieval": source.last_successful_retrieval.isoformat() if source.last_successful_retrieval else None,
            "last_attempt_at": source.last_attempt_at.isoformat() if source.last_attempt_at else None,
            "consecutive_failures": source.consecutive_failures,
            "error_details": source.error_details,
            "records_count": source.records_count
        },
        "recent_observations": [
            {
                "observation_id": o.observation_id,
                "variable_name": o.variable_name,
                "value": float(o.value),
                "unit": o.unit,
                "valid_at": o.valid_at.isoformat() if o.valid_at else None,
                "retrieved_at": o.retrieved_at.isoformat() if o.retrieved_at else None,
                "quality_flags": o.quality_flags
            }
            for o in recent_obs
        ]
    }


@router.get("/jobs")
def list_ingestion_jobs(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (SUCCESS, RUNNING, FAILED)"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Returns paginated ingestion job execution ledger."""
    query = db.query(ScheduledIngestionJob)
    if status_filter:
        query = query.filter(ScheduledIngestionJob.status == status_filter)
    if source_id:
        query = query.filter(ScheduledIngestionJob.source_id == source_id)

    jobs = query.order_by(desc(ScheduledIngestionJob.created_at)).limit(limit).all()

    return {
        "count": len(jobs),
        "jobs": [
            {
                "job_id": j.job_id,
                "job_name": j.job_name,
                "source_id": j.source_id,
                "schedule_interval": j.schedule_interval,
                "status": j.status,
                "records_retrieved": j.records_retrieved,
                "records_accepted": j.records_accepted,
                "records_rejected": j.records_rejected,
                "records_deduplicated": j.records_deduplicated,
                "retry_count": j.retry_count,
                "error_category": j.error_category,
                "execution_log": j.execution_log,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None
            }
            for j in jobs
        ]
    }


@router.get("/jobs/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db)):
    """Returns granular log and outcome for a specific job run."""
    job = db.query(ScheduledIngestionJob).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job run '{job_id}' not found."
        )

    return {
        "job_id": job.job_id,
        "job_name": job.job_name,
        "source_id": job.source_id,
        "status": job.status,
        "records_retrieved": job.records_retrieved,
        "records_accepted": job.records_accepted,
        "records_rejected": job.records_rejected,
        "records_deduplicated": job.records_deduplicated,
        "retry_count": job.retry_count,
        "error_category": job.error_category,
        "execution_log": job.execution_log,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


@router.post("/jobs/{job_name}/run")
def trigger_manual_job(job_name: str, db: Session = Depends(get_db)):
    """
    On-demand operational endpoint to trigger a scheduled ingestion job manually.
    Protected by execution mutex to prevent overlapping executions.
    """
    scheduler = get_orchestration_scheduler()
    try:
        result = scheduler.run_manual_job(job_name)
        return {
            "message": f"Job '{job_name}' executed successfully.",
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/observations")
def get_ingested_observations(
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    variable: Optional[str] = Query(None, description="Filter by variable name (precipitation, temperature)"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Retrieves normalized observations with distinct temporal semantics:
    - observed_at: sensor reading time
    - issued_at: model/bulletin release time
    - valid_at: forecast/alert horizon time
    - retrieved_at: EIDT download time
    - processed_at: EIDT assessment time
    """
    query = db.query(IngestedObservation)
    if source_id:
        query = query.filter(IngestedObservation.source_id == source_id)
    if variable:
        query = query.filter(IngestedObservation.variable_name == variable)

    obs = query.order_by(desc(IngestedObservation.retrieved_at)).limit(limit).all()

    return {
        "count": len(obs),
        "observations": [
            {
                "observation_id": o.observation_id,
                "source_id": o.source_id,
                "variable_name": o.variable_name,
                "value": float(o.value),
                "unit": o.unit,
                "locality_name": o.locality_name,
                "observed_at": o.observed_at.isoformat() if o.observed_at else None,
                "issued_at": o.issued_at.isoformat() if o.issued_at else None,
                "valid_at": o.valid_at.isoformat() if o.valid_at else None,
                "retrieved_at": o.retrieved_at.isoformat() if o.retrieved_at else None,
                "processed_at": o.processed_at.isoformat() if o.processed_at else None,
                "product_version": o.product_version,
                "quality_flags": o.quality_flags
            }
            for o in obs
        ]
    }


@router.get("/forecasts")
def get_ingested_forecasts(
    hours: int = Query(24, ge=1, le=72),
    db: Session = Depends(get_db)
):
    """Returns active forward forecast horizon parsed from ingested NWP guidance."""
    now = datetime.now(timezone.utc)
    obs = db.query(IngestedObservation).filter(
        IngestedObservation.source_id == "open_meteo_forecast",
        IngestedObservation.variable_name == "precipitation"
    ).order_by(desc(IngestedObservation.retrieved_at)).limit(hours).all()

    # Sort forward in time by valid_at
    sorted_obs = sorted(obs, key=lambda x: x.valid_at or x.retrieved_at)

    total_rain = sum(float(o.value) for o in sorted_obs)
    peak_rate = max([float(o.value) for o in sorted_obs], default=0.0)

    return {
        "source": "Open-Meteo Numerical Weather Prediction API",
        "spatial_resolution": "0.1° (~11 km)",
        "horizon_hours": len(sorted_obs),
        "total_predicted_rainfall_mm": round(total_rain, 2),
        "peak_predicted_hourly_mm": round(peak_rate, 2),
        "timeline": [
            {
                "valid_at": o.valid_at.isoformat() if o.valid_at else None,
                "precipitation_mm": float(o.value),
                "unit": o.unit,
                "retrieved_at": o.retrieved_at.isoformat() if o.retrieved_at else None
            }
            for o in sorted_obs
        ]
    }


@router.get("/provenance")
def get_monitoring_provenance(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Returns data provenance audit records."""
    logs = db.query(DataProvenanceLog).order_by(
        desc(DataProvenanceLog.retrieval_timestamp)
    ).limit(limit).all()

    return {
        "count": len(logs),
        "provenance_logs": [
            {
                "log_id": l.log_id,
                "source_id": l.source_id,
                "connector_name": l.connector_name,
                "retrieval_timestamp": l.retrieval_timestamp.isoformat() if l.retrieval_timestamp else None,
                "status": l.status,
                "records_ingested": l.records_ingested,
                "details": l.details
            }
            for l in logs
        ]
    }


@router.get("/quality")
def get_data_quality_report(db: Session = Depends(get_db)):
    """Returns data quality parameters, physics bounds, and audit checks."""
    all_obs = db.query(IngestedObservation).limit(500).all()
    obs_count = len(all_obs)
    quarantined = sum(1 for o in all_obs if (o.quality_flags or {}).get("status") == "OUT_OF_RANGE")

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_observations_recorded": obs_count,
        "quarantined_records_count": quarantined,
        "quality_rules": {
            "missing_timestamps": "REJECT_IMMEDIATELY",
            "physics_bounds": PHYSICAL_BOUNDS,
            "deduplication_policy": "IDEMPOTENT_UPSERT_BY_TIME_ANCHOR",
            "stale_data_policy": "EXPLICIT_STALE_FLAG_NEVER_ZERO_SUBSTITUTION"
        }
    }


@router.get("/metrics")
def get_api_metrics(db: Session = Depends(get_db)):
    """
    Returns empirical API performance and observability metrics:
    p50, p95, p99 latency, request counts, error rate, and slow endpoint traces.
    """
    from app.models.schema import ApiMetricLog
    import numpy as np

    logs = db.query(ApiMetricLog).order_by(ApiMetricLog.timestamp.desc()).limit(1000).all()
    if not logs:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_requests": 0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
            "error_rate_pct": 0.0,
            "endpoints": {}
        }

    durations = [float(l.duration_ms) for l in logs]
    durations.sort()

    p50 = np.percentile(durations, 50)
    p95 = np.percentile(durations, 95)
    p99 = np.percentile(durations, 99)

    error_count = sum(1 for l in logs if l.status_code >= 400)
    error_rate = round((error_count / len(logs)) * 100.0, 2)

    endpoint_stats: Dict[str, Dict[str, Any]] = {}
    for l in logs:
        ep = l.endpoint
        if ep not in endpoint_stats:
            endpoint_stats[ep] = {"count": 0, "errors": 0, "durations": []}
        endpoint_stats[ep]["count"] += 1
        if l.status_code >= 400:
            endpoint_stats[ep]["errors"] += 1
        endpoint_stats[ep]["durations"].append(float(l.duration_ms))

    summary_by_ep = {}
    for ep, data in list(endpoint_stats.items())[:10]:
        summary_by_ep[ep] = {
            "count": data["count"],
            "avg_ms": round(sum(data["durations"]) / len(data["durations"]), 2),
            "max_ms": round(max(data["durations"]), 2),
            "errors": data["errors"]
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_requests_analyzed": len(logs),
        "p50_latency_ms": round(float(p50), 2),
        "p95_latency_ms": round(float(p95), 2),
        "p99_latency_ms": round(float(p99), 2),
        "error_rate_percentage": error_rate,
        "status_distribution": {
            "2xx": sum(1 for l in logs if 200 <= l.status_code < 300),
            "4xx": sum(1 for l in logs if 400 <= l.status_code < 500),
            "5xx": sum(1 for l in logs if l.status_code >= 500)
        },
        "top_endpoints": summary_by_ep
    }

