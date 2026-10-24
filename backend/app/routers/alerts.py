"""
Alerts and Decision Support API Router (Phase 5)
Provides query endpoints for active early-warning alerts, historical audit records,
lifecycle transition trails, and operator acknowledgement workflows.
Strictly distinguishes official government warnings from EIDT model advisory decisions.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.schema import MultiHazardAlert, AlertLifecycleEvent
from app.services.alert_orchestrator import AlertOrchestrator

router = APIRouter(prefix="/alerts", tags=["Early-Warning Alerts & Lifecycle (Phase 5)"])


@router.get("")
def list_active_alerts(
    hazard_type: Optional[str] = Query(None, description="Filter by hazard type (FLOOD, HEATWAVE, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (GREEN, YELLOW, ORANGE, RED)"),
    is_official: Optional[bool] = Query(None, description="Filter official government warnings vs EIDT advisories"),
    db: Session = Depends(get_db)
):
    """
    Returns currently ACTIVE or UPDATED alerts.
    Does not display EXPIRED or CANCELLED alerts as current.
    Clearly marks whether each alert is an Official Notice or an EIDT Model Advisory.
    """
    # Trigger expiry evaluation on active query to ensure no expired alerts linger
    orchestrator = AlertOrchestrator(db)
    orchestrator.evaluate_expiry_cycle()

    query = db.query(MultiHazardAlert).filter(
        MultiHazardAlert.lifecycle_status.in_(["ACTIVE", "UPDATED", "NEW"])
    )

    if hazard_type:
        query = query.filter(MultiHazardAlert.hazard_type == hazard_type.upper())
    if severity:
        query = query.filter(MultiHazardAlert.severity_level == severity.upper())
    if is_official is not None:
        query = query.filter(MultiHazardAlert.is_official_warning == is_official)

    alerts = query.order_by(desc(MultiHazardAlert.created_at)).all()

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "active_count": len(alerts),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "hazard_type": a.hazard_type,
                "geographic_scope": a.geographic_scope,
                "study_area_id": a.study_area_id,
                "severity_level": a.severity_level,
                "headline": a.headline,
                "description": a.description,
                "rationale": a.rationale,
                "lifecycle_status": a.lifecycle_status,
                "is_official_warning": a.is_official_warning,
                "source_classification": "OFFICIAL_GOVERNMENT_NOTICE" if a.is_official_warning else "EIDT_DECISION_SUPPORT_ADVISORY",
                "issuing_authority": a.issuing_authority,
                "onset_timestamp": a.onset_timestamp.isoformat() if a.onset_timestamp else None,
                "expiry_timestamp": a.expiry_timestamp.isoformat() if a.expiry_timestamp else None,
                "model_version": a.model_version,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None
            }
            for a in alerts
        ]
    }


@router.get("/history")
def list_alert_history(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (EXPIRED, CANCELLED, UPDATED)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Returns paginated historical record of all past and retired alerts."""
    query = db.query(MultiHazardAlert)
    if status_filter:
        query = query.filter(MultiHazardAlert.lifecycle_status == status_filter.upper())

    alerts = query.order_by(desc(MultiHazardAlert.created_at)).limit(limit).all()

    return {
        "count": len(alerts),
        "history": [
            {
                "alert_id": a.alert_id,
                "hazard_type": a.hazard_type,
                "geographic_scope": a.geographic_scope,
                "severity_level": a.severity_level,
                "headline": a.headline,
                "lifecycle_status": a.lifecycle_status,
                "is_official_warning": a.is_official_warning,
                "issuing_authority": a.issuing_authority,
                "onset_timestamp": a.onset_timestamp.isoformat() if a.onset_timestamp else None,
                "expiry_timestamp": a.expiry_timestamp.isoformat() if a.expiry_timestamp else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None
            }
            for a in alerts
        ]
    }


@router.get("/{alert_id}")
def get_alert_detail(alert_id: str, db: Session = Depends(get_db)):
    """Returns full alert metadata and its immutable lifecycle event audit trail."""
    alert = db.query(MultiHazardAlert).filter_by(alert_id=alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found."
        )

    events = db.query(AlertLifecycleEvent).filter_by(
        alert_id=alert_id
    ).order_by(desc(AlertLifecycleEvent.timestamp)).all()

    return {
        "alert": {
            "alert_id": alert.alert_id,
            "hazard_type": alert.hazard_type,
            "geographic_scope": alert.geographic_scope,
            "study_area_id": alert.study_area_id,
            "severity_level": alert.severity_level,
            "headline": alert.headline,
            "description": alert.description,
            "rationale": alert.rationale,
            "lifecycle_status": alert.lifecycle_status,
            "is_official_warning": alert.is_official_warning,
            "source_classification": "OFFICIAL_GOVERNMENT_NOTICE" if alert.is_official_warning else "EIDT_DECISION_SUPPORT_ADVISORY",
            "issuing_authority": alert.issuing_authority,
            "onset_timestamp": alert.onset_timestamp.isoformat() if alert.onset_timestamp else None,
            "expiry_timestamp": alert.expiry_timestamp.isoformat() if alert.expiry_timestamp else None,
            "evidence_data": alert.evidence_data,
            "model_version": alert.model_version,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "updated_at": alert.updated_at.isoformat() if alert.updated_at else None
        },
        "lifecycle_events": [
            {
                "event_id": e.event_id,
                "previous_state": e.previous_state,
                "new_state": e.new_state,
                "transition_reason": e.transition_reason,
                "triggered_by": e.triggered_by,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None
            }
            for e in events
        ]
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, operator_id: str = Query("DISASTER_MGMT_OPERATOR"), db: Session = Depends(get_db)):
    """Acknowledge an alert to record operator receipt and log lifecycle event."""
    orchestrator = AlertOrchestrator(db)
    alert = orchestrator.acknowledge_alert(alert_id, operator_id=operator_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found."
        )

    return {
        "message": f"Alert '{alert_id}' successfully acknowledged.",
        "alert_id": alert.alert_id,
        "acknowledged_by": operator_id,
        "acknowledged_at": datetime.now(timezone.utc).isoformat()
    }
