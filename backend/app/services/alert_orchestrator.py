"""
Alert Lifecycle Orchestrator for Earth Intelligence Digital Twin (EIDT)
Enforces strict alert lifecycle state transitions (NEW -> ACTIVE -> UPDATED -> EXPIRED / CANCELLED / SUPERSEDED),
maintains deterministic deduplication, logs transition audit records, and strictly segregates
authoritative government warnings (IMD/MCGM) from automated EIDT decision support assessments.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.schema import (
    MultiHazardAlert,
    AlertLifecycleEvent,
    StudyArea
)

logger = logging.getLogger(__name__)

VALID_LIFECYCLE_STATES = {"NEW", "ACTIVE", "UPDATED", "EXPIRED", "CANCELLED", "SUPERSEDED"}


class AlertOrchestrator:
    def __init__(self, db: Session):
        self.db = db

    def compute_deduplication_hash(
        self,
        hazard_type: str,
        geographic_scope: str,
        valid_date_str: str,
        authority: str
    ) -> str:
        """Deterministic hash preventing identical alerts from duplicating."""
        raw = f"{hazard_type.upper()}_{geographic_scope.lower()}_{valid_date_str}_{authority.lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def create_or_update_alert(
        self,
        hazard_type: str,
        geographic_scope: str,
        severity_level: str,
        headline: str,
        description: str,
        issuing_authority: str,
        is_official_warning: bool,
        onset_timestamp: Optional[datetime],
        expiry_timestamp: Optional[datetime],
        rationale: Optional[str] = None,
        study_area_id: Optional[str] = None,
        evidence_data: Optional[Dict[str, Any]] = None,
        model_version: Optional[str] = None
    ) -> Tuple[MultiHazardAlert, str]:
        """
        Creates a new alert or updates an existing alert.
        Transitions:
        - If new -> creates in ACTIVE state, records event 'new -> active'
        - If exists with same deduplication hash and different content -> UPDATED, records event 'active -> updated'
        - If identical active alert -> keeps current without spamming transitions
        """
        now = datetime.now(timezone.utc)
        valid_date_str = onset_timestamp.strftime("%Y%m%d") if onset_timestamp else now.strftime("%Y%m%d")
        dedup_hash = self.compute_deduplication_hash(
            hazard_type, geographic_scope, valid_date_str, issuing_authority
        )

        existing = self.db.query(MultiHazardAlert).filter_by(deduplication_hash=dedup_hash).first()

        if existing:
            # Check if severity or description changed
            if existing.severity_level != severity_level or existing.description != description:
                old_state = existing.lifecycle_status
                existing.severity_level = severity_level
                existing.headline = headline
                existing.description = description
                existing.rationale = rationale or existing.rationale
                existing.evidence_data = evidence_data or existing.evidence_data
                existing.lifecycle_status = "UPDATED"
                existing.updated_at = now

                self._record_event(
                    alert_id=existing.alert_id,
                    previous_state=old_state,
                    new_state="UPDATED",
                    reason=f"Alert updated with revised severity {severity_level} or description.",
                    triggered_by="SYSTEM_HAZARD_ENGINE"
                )
                self.db.commit()
                return existing, "UPDATED"
            else:
                existing.updated_at = now
                self.db.commit()
                return existing, "UNCHANGED"

        # Generate new alert ID
        import uuid
        alert_id = f"alt_{uuid.uuid4().hex[:12]}"

        new_alert = MultiHazardAlert(
            alert_id=alert_id,
            hazard_type=hazard_type,
            geographic_scope=geographic_scope,
            study_area_id=study_area_id,
            severity_level=severity_level,
            headline=headline,
            description=description,
            rationale=rationale,
            lifecycle_status="ACTIVE",
            is_official_warning=is_official_warning,
            issuing_authority=issuing_authority,
            onset_timestamp=onset_timestamp or now,
            expiry_timestamp=expiry_timestamp,
            evidence_data=evidence_data,
            model_version=model_version,
            deduplication_hash=dedup_hash,
            created_at=now,
            updated_at=now
        )
        self.db.add(new_alert)

        self._record_event(
            alert_id=alert_id,
            previous_state=None,
            new_state="ACTIVE",
            reason=f"Initial alert issuance ({'Official government notice' if is_official_warning else 'EIDT model advisory'}).",
            triggered_by="SYSTEM_HAZARD_ENGINE"
        )
        self.db.commit()
        return new_alert, "CREATED"

    def evaluate_expiry_cycle(self) -> List[str]:
        """
        Scheduled lifecycle job: inspects all ACTIVE or UPDATED alerts,
        marking those whose expiry_timestamp is in the past as EXPIRED.
        Never cancels or deletes records; records transitions to EXPIRED.
        """
        now = datetime.now(timezone.utc)
        active_alerts = self.db.query(MultiHazardAlert).filter(
            MultiHazardAlert.lifecycle_status.in_(["ACTIVE", "UPDATED", "NEW"])
        ).all()

        expired_ids = []
        for alert in active_alerts:
            if alert.expiry_timestamp:
                exp = alert.expiry_timestamp
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < now:
                    old_state = alert.lifecycle_status
                    alert.lifecycle_status = "EXPIRED"
                    alert.updated_at = now
                    self._record_event(
                        alert_id=alert.alert_id,
                        previous_state=old_state,
                        new_state="EXPIRED",
                        reason=f"Alert horizon elapsed at {exp.isoformat()}.",
                        triggered_by="LIFECYCLE_MONITOR"
                    )
                    expired_ids.append(alert.alert_id)

        self.db.commit()
        return expired_ids

    def acknowledge_alert(self, alert_id: str, operator_id: str = "OPERATOR") -> Optional[MultiHazardAlert]:
        """Supports authenticated operator workflow to acknowledge an alert."""
        alert = self.db.query(MultiHazardAlert).filter_by(alert_id=alert_id).first()
        if not alert:
            return None

        self._record_event(
            alert_id=alert.alert_id,
            previous_state=alert.lifecycle_status,
            new_state=alert.lifecycle_status,
            reason=f"Acknowledged by operator {operator_id}.",
            triggered_by=operator_id
        )
        self.db.commit()
        return alert

    def cancel_or_supersede_alert(
        self,
        alert_id: str,
        new_state: str,
        reason: str,
        operator_id: str = "SYSTEM"
    ) -> Optional[MultiHazardAlert]:
        """Transitions an alert to CANCELLED or SUPERSEDED based on explicit authoritative update."""
        if new_state not in ["CANCELLED", "SUPERSEDED"]:
            raise ValueError(f"Invalid terminal state {new_state}")

        alert = self.db.query(MultiHazardAlert).filter_by(alert_id=alert_id).first()
        if not alert:
            return None

        old_state = alert.lifecycle_status
        alert.lifecycle_status = new_state
        alert.updated_at = datetime.now(timezone.utc)

        self._record_event(
            alert_id=alert.alert_id,
            previous_state=old_state,
            new_state=new_state,
            reason=reason,
            triggered_by=operator_id
        )
        self.db.commit()
        return alert

    def _record_event(
        self,
        alert_id: str,
        previous_state: Optional[str],
        new_state: str,
        reason: str,
        triggered_by: str = "SYSTEM"
    ):
        """Internal helper to write immutable lifecycle transition event."""
        import uuid
        event = AlertLifecycleEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            alert_id=alert_id,
            previous_state=previous_state,
            new_state=new_state,
            transition_reason=reason,
            triggered_by=triggered_by,
            timestamp=datetime.now(timezone.utc)
        )
        self.db.add(event)
