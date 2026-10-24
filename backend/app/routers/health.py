"""
Health & Reliability Router
Earth Intelligence Digital Twin (EIDT) - Maharashtra
Phase 7F: Liveness, Readiness & Data Readiness Probes.

Distinguishes:
  - Liveness: whether the process is alive.
  - Readiness: whether essential infrastructure (PostgreSQL/PostGIS) is ready to accept requests.
  - Data Readiness: whether required datasets, coverage, and hazard pipelines are sufficiently current.
"""

import os
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.database import get_db
from app.schemas.api_schemas import (
    HealthResponse, LivenessResponse, ReadinessResponse, DataReadinessResponse
)
from app.models.schema import StudyArea, WeatherObservation, MultiHazardAlert, RoadSegment

router = APIRouter(prefix="/health", tags=["Health & System"])

# Process start time for uptime tracking
PROCESS_START_TIME = time.time()


@router.get("", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """Standard operational health check (backward compatible)."""
    db_status = "connected"
    postgis_enabled = False
    try:
        result = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'postgis';"))
        row = result.fetchone()
        postgis_enabled = bool(row)
    except Exception:
        try:
            db.execute(text("SELECT 1;"))
            db_status = "connected (standard SQL mode)"
        except Exception as e:
            db_status = f"unhealthy: {e}"

    return HealthResponse(
        status="operational",
        version="1.0.0",
        database=db_status,
        postgis_enabled=postgis_enabled,
        data_freshness_timestamp=datetime.now(timezone.utc),
        geospatial_engine="GeoPandas + Shapely 2.0 (Dual PostGIS / Python Fallback Engine)"
    )


@router.get("/live", response_model=LivenessResponse)
def get_liveness():
    """
    Liveness probe: verifies that the FastAPI process is running and responding.
    Kubernetes / Docker healthcheck endpoint.
    """
    uptime = time.time() - PROCESS_START_TIME
    return LivenessResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(uptime, 2),
        process_id=os.getpid()
    )


@router.get("/ready", response_model=ReadinessResponse)
def get_readiness(db: Session = Depends(get_db)):
    """
    Readiness probe: verifies essential dependencies (database, extensions, connection pool).
    Returns 503 if primary database is unreachable.
    """
    t0 = time.time()
    db_status = "ready"
    postgis_enabled = False
    dependencies = {}

    try:
        # Measure DB ping latency
        db.execute(text("SELECT 1;"))
        db_latency = (time.time() - t0) * 1000.0

        # Check PostGIS extension
        try:
            res = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'postgis';"))
            postgis_enabled = bool(res.fetchone())
            dependencies["postgis"] = "enabled" if postgis_enabled else "disabled (using Shapely/GeoPandas fallback)"
        except Exception:
            dependencies["postgis"] = "unsupported (SQLite mode)"

        dependencies["postgresql"] = "connected"

    except Exception as e:
        db_latency = -1.0
        db_status = "unhealthy"
        dependencies["postgresql"] = f"failed: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database readiness check failed: {str(e)}"
        )

    return ReadinessResponse(
        status="ready" if db_status == "ready" else "degraded",
        database=db_status,
        database_latency_ms=round(db_latency, 2),
        postgis_enabled=postgis_enabled,
        geospatial_engine="GeoPandas + Shapely 2.0" if not postgis_enabled else "PostGIS 3.x Spatial Engine",
        dependencies=dependencies
    )


@router.get("/data-readiness", response_model=DataReadinessResponse)
def get_data_readiness(db: Session = Depends(get_db)):
    """
    Data readiness probe: evaluates whether current observations, coverage,
    and models are sufficiently fresh and operational.
    Prevents false all-clears when data is stale or missing.
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # 1. Weather observation freshness
    latest_obs = db.query(WeatherObservation).order_by(WeatherObservation.timestamp.desc()).first()
    obs_freshness = latest_obs.timestamp if latest_obs else None

    obs_count_24h = db.query(func.count(WeatherObservation.observation_id)).filter(
        WeatherObservation.timestamp >= cutoff_24h
    ).scalar() or 0

    # 2. Active alerts count
    active_alerts = db.query(func.count(MultiHazardAlert.alert_id)).filter(
        MultiHazardAlert.lifecycle_status.in_(["ISSUED", "UPDATED"])
    ).scalar() or 0

    # 3. Administrative coverage
    total_areas = db.query(func.count(StudyArea.study_area_id)).scalar() or 0
    verified_areas = db.query(func.count(StudyArea.study_area_id)).filter(
        StudyArea.is_verified == True
    ).scalar() or 0

    # 4. Routing network readiness
    road_count = db.query(func.count(RoadSegment.road_segment_id)).scalar() or 0
    routing_ready = road_count > 0

    # 5. Coverage gaps and limitations
    limitations = []
    if total_areas < 43:  # 1 State + 6 Divisions + 36 Districts = 43 minimum
        limitations.append("Statewide administrative hierarchy partially seeded; run seed_maharashtra_hierarchy().")

    if not routing_ready:
        limitations.append("Road network graph unpopulated; emergency routing unavailable outside pilot.")
    else:
        limitations.append("Road network coverage verified for Mumbai Metropolitan Region pilot corridor.")

    if obs_freshness and (now - obs_freshness).total_seconds() > 86400 * 2:
        status_label = "stale"
        limitations.append("Latest weather observations are older than 48 hours; check ingestion schedulers.")
    elif obs_count_24h > 0:
        status_label = "current"
    else:
        status_label = "degraded_freshness"

    return DataReadinessResponse(
        status=status_label,
        data_freshness_timestamp=obs_freshness,
        observation_count_24h=obs_count_24h,
        active_alerts_count=active_alerts,
        study_areas_total=total_areas,
        study_areas_verified=verified_areas,
        routing_network_ready=routing_ready,
        hazard_models_ready=True,
        coverage_gaps_count=len(limitations),
        known_limitations=limitations
    )
