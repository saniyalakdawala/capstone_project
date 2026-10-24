"""
Multi-Hazard API Router (Phase 3)
Standardized REST endpoints for Maharashtra Multi-Hazard Intelligence:
- GET /api/hazards
- GET /api/hazards/{hazard}/status
- GET /api/hazards/{hazard}/forecast
- GET /api/hazards/{hazard}/localities
- GET /api/hazards/{hazard}/localities/{locality_id}
- GET /api/hazards/{hazard}/layers
- GET /api/hazards/{hazard}/alerts
- GET /api/hazards/{hazard}/provenance
- GET /api/hazards/{hazard}/validation
- GET /api/hazards/alerts/active
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.services.hazards.hazard_registry import hazard_registry

router = APIRouter(prefix="/hazards", tags=["Multi-Hazard Platform (Phase 3)"])


def _get_module_or_404(hazard: str):
    mod = hazard_registry.get_module(hazard)
    if not mod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "Unsupported Hazard Category",
                "requested_hazard": hazard,
                "supported_hazards": list(hazard_registry.modules.keys()),
                "message": f"Hazard '{hazard}' is not recognized in the EIDT Multi-Hazard platform."
            }
        )
    return mod


@router.get("")
def list_available_hazards():
    """
    Returns the comprehensive status of all 6 hazard categories supported
    in the Maharashtra Multi-Hazard Platform.
    """
    hazards_list = hazard_registry.list_hazards()
    hazards_dict = {h["hazard_id"]: h for h in hazards_list}
    return {
        "platform": "EIDT Maharashtra Multi-Hazard Intelligence",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "hazard_count": len(hazard_registry.modules),
        "total_hazards_configured": len(hazard_registry.modules),
        "hazards": hazards_list,
        "supported_hazards": hazards_dict
    }


@router.get("/alerts/active")
def get_cross_hazard_active_alerts(db: Session = Depends(get_db)):
    """
    Aggregates active alerts across all 6 disaster categories, enforcing
    lifecycle state transitions, deduplication, and authority attribution.
    """
    alerts = hazard_registry.get_all_active_alerts(db=db)
    return {
        "status": "SUCCESS",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "active_alert_count": len(alerts),
        "alerts": alerts
    }


@router.get("/{hazard}/status")
def get_hazard_module_status(hazard: str):
    """
    Returns detailed source availability, spatial coverage, operational readiness,
    and scientific limitations for a specific hazard category.
    """
    mod = _get_module_or_404(hazard)
    return mod.get_status()


@router.get("/{hazard}/forecast")
def get_hazard_forecast(
    hazard: str,
    hours: int = Query(24, ge=1, le=168, description="Forecast horizon in hours")
):
    """
    Returns forecast series, triggers, or diurnal curves for the specified hazard.
    """
    mod = _get_module_or_404(hazard)
    return mod.get_forecast(hours=hours)


@router.get("/{hazard}/localities")
def list_hazard_locality_assessments(hazard: str):
    """
    Returns locality-level risk diagnostic assessments across all supported wards/districts.
    """
    mod = _get_module_or_404(hazard)
    localities = mod.assess_localities()

    # Risk category summary distribution
    dist = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "VERY_HIGH": 0}
    for loc in localities:
        cat = loc.get("risk_category", "LOW")
        dist[cat] = dist.get(cat, 0) + 1

    return {
        "hazard_id": mod.hazard_id,
        "hazard_name": mod.name,
        "model_version": mod.version,
        "responsible_authority": mod.responsible_authority,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_localities_assessed": len(localities),
        "risk_distribution": dist,
        "localities": localities
    }


@router.get("/{hazard}/localities/{locality_id}")
def get_hazard_locality_diagnostic(hazard: str, locality_id: str):
    """
    Retrieves detailed diagnostic assessment for a specific locality or ward.
    """
    mod = _get_module_or_404(hazard)
    assessment = mod.get_locality_assessment(locality_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Locality '{locality_id}' not found in active {mod.name} coverage area."
        )
    return assessment


@router.get("/{hazard}/layers")
def get_hazard_map_layers(hazard: str):
    """
    Returns valid GeoJSON FeatureCollection of spatial risk polygons or susceptibility zones.
    """
    mod = _get_module_or_404(hazard)
    return mod.get_map_layers()


@router.get("/{hazard}/alerts")
def get_hazard_alerts(hazard: str, db: Session = Depends(get_db)):
    """
    Returns active alerts for the specified hazard category.
    """
    mod = _get_module_or_404(hazard)
    # Ensure active alerts are populated in db
    alerts = hazard_registry.alert_manager.get_active_alerts(db=db, hazard_type=mod.hazard_id)
    if not alerts:
        # Fallback to module direct alerts if db empty
        alerts = mod.get_alerts()
    return {
        "hazard_id": mod.hazard_id,
        "count": len(alerts),
        "alerts": alerts
    }


@router.get("/{hazard}/provenance")
def get_hazard_provenance(hazard: str):
    """
    Returns traceable datasets, native resolutions, coordinate reference systems, and missing input blockers.
    """
    mod = _get_module_or_404(hazard)
    return mod.get_provenance()


@router.get("/{hazard}/validation")
def get_hazard_validation_metrics(hazard: str):
    """
    Returns empirical validation metrics, benchmark events, and scientific limitations.
    """
    mod = _get_module_or_404(hazard)
    return mod.get_validation_results()
