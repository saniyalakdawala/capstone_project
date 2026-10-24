"""
Multi-Hazard Alert Lifecycle & Deduplication Manager (Phase 3)
Implements candidate -> verified -> issued -> updated -> expired lifecycle.
Enforces deduplication, official authority attribution, and automatic expiry.
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.schema import MultiHazardAlert

logger = logging.getLogger(__name__)


class AlertLifecycleManager:
    """
    Governs alert generation, verification, deduplication, and expiration.
    Ensures that official warnings (IMD/INCOIS) are clearly distinguished
    from EIDT model diagnostic advisories.
    """

    LIFECYCLE_STATES = ["CANDIDATE", "VERIFIED", "ISSUED", "UPDATED", "EXPIRED", "WITHDRAWN"]
    SEVERITY_LEVELS = ["ADVISORY", "WATCH", "WARNING", "SEVERE"]

    @staticmethod
    def compute_deduplication_hash(
        hazard_type: str,
        geographic_scope: str,
        severity_level: str,
        validity_date: str
    ) -> str:
        """Computes deterministic hash to prevent alert spam across polling cycles."""
        raw = f"{hazard_type}:{geographic_scope.strip().upper()}:{severity_level.upper()}:{validity_date}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def register_or_update_alert(
        self,
        db: Session,
        hazard_type: str,
        geographic_scope: str,
        severity_level: str,
        headline: str,
        description: str,
        issuing_authority: str,
        is_official_warning: bool,
        recommended_action: str,
        rationale: Optional[str] = None,
        study_area_id: Optional[str] = None,
        duration_hours: int = 24,
        evidence_data: Optional[Dict[str, Any]] = None,
        model_version: Optional[str] = None
    ) -> MultiHazardAlert:
        """
        Idempotently inserts a new alert or updates an existing active alert for the same scope.
        """
        now = datetime.now(timezone.utc)
        validity_date = now.strftime("%Y-%m-%d")
        dedup_hash = self.compute_deduplication_hash(
            hazard_type=hazard_type,
            geographic_scope=geographic_scope,
            severity_level=severity_level,
            validity_date=validity_date
        )

        existing = db.query(MultiHazardAlert).filter(
            MultiHazardAlert.deduplication_hash == dedup_hash
        ).first()

        if existing:
            # Update expiry and evidence
            existing.updated_at = now
            existing.expiry_timestamp = now + timedelta(hours=duration_hours)
            existing.evidence_data = evidence_data or existing.evidence_data
            existing.headline = headline
            existing.description = description
            existing.severity_level = severity_level
            existing.recommended_action = recommended_action
            existing.lifecycle_status = "ISSUED" if existing.lifecycle_status == "EXPIRED" else "UPDATED"
            db.commit()
            return existing

        # Create new verified alert
        import uuid
        alert_id = f"ALT_{hazard_type[:3].upper()}_{uuid.uuid4().hex[:8].upper()}"
        alert = MultiHazardAlert(
            alert_id=alert_id,
            hazard_type=hazard_type,
            geographic_scope=geographic_scope,
            study_area_id=study_area_id,
            severity_level=severity_level,
            headline=headline,
            description=description,
            rationale=rationale,
            lifecycle_status="ISSUED",
            is_official_warning=is_official_warning,
            issuing_authority=issuing_authority,
            onset_timestamp=now,
            expiry_timestamp=now + timedelta(hours=duration_hours),
            recommended_action=recommended_action,
            evidence_data=evidence_data,
            model_version=model_version,
            deduplication_hash=dedup_hash,
            created_at=now,
            updated_at=now
        )
        db.add(alert)
        db.commit()
        return alert

    def expire_stale_alerts(self, db: Session) -> int:
        """Transitions alerts past their expiry timestamp to EXPIRED status."""
        now = datetime.now(timezone.utc)
        stale = db.query(MultiHazardAlert).filter(
            MultiHazardAlert.lifecycle_status.in_(["ISSUED", "UPDATED", "VERIFIED"]),
            MultiHazardAlert.expiry_timestamp < now
        ).all()

        for a in stale:
            a.lifecycle_status = "EXPIRED"
            a.updated_at = now

        if stale:
            db.commit()
        return len(stale)

    def get_active_alerts(
        self,
        db: Session,
        hazard_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves non-expired alerts, enforcing lifecycle check."""
        self.expire_stale_alerts(db)
        now = datetime.now(timezone.utc)

        query = db.query(MultiHazardAlert).filter(
            MultiHazardAlert.lifecycle_status.in_(["ISSUED", "UPDATED", "VERIFIED"]),
            MultiHazardAlert.expiry_timestamp >= now
        )
        if hazard_type:
            query = query.filter(MultiHazardAlert.hazard_type == hazard_type)

        alerts = query.order_by(MultiHazardAlert.created_at.desc()).all()
        return [self._format_alert(a) for a in alerts]

    def _format_alert(self, a: MultiHazardAlert) -> Dict[str, Any]:
        return {
            "alert_id": a.alert_id,
            "hazard_type": a.hazard_type,
            "geographic_scope": a.geographic_scope,
            "study_area_id": a.study_area_id,
            "severity_level": a.severity_level,
            "headline": a.headline,
            "description": a.description,
            "rationale": a.rationale,
            "lifecycle_status": a.lifecycle_status,
            "is_official_warning": bool(a.is_official_warning),
            "issuing_authority": a.issuing_authority,
            "onset_timestamp_utc": a.onset_timestamp.isoformat() if a.onset_timestamp else None,
            "expiry_timestamp_utc": a.expiry_timestamp.isoformat() if a.expiry_timestamp else None,
            "recommended_action": a.recommended_action,
            "evidence_data": a.evidence_data or {},
            "model_version": a.model_version,
            "created_at_utc": a.created_at.isoformat() if a.created_at else None
        }
