"""
Notification Delivery Service for Earth Intelligence Digital Twin (EIDT)
Follows strict provider abstraction pattern with in-app, webhook, email, and SMS channels.
CRITICAL SAFETY RULE: External delivery is disabled by default (NOTIFICATIONS_ENABLED=false).
Public mass warnings are never dispatched without explicit operator configuration and credentials.
"""
import os
import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.schema import AlertNotification, MultiHazardAlert
from app.config import settings

logger = logging.getLogger(__name__)


class BaseNotificationProvider(ABC):
    @abstractmethod
    def deliver(self, alert: MultiHazardAlert, target: str) -> Dict[str, Any]:
        """Dispatches notification and returns delivery outcome."""
        pass


class InAppNotificationProvider(BaseNotificationProvider):
    """Local database in-app notification provider. Always safe and local."""
    def deliver(self, alert: MultiHazardAlert, target: str) -> Dict[str, Any]:
        return {
            "success": True,
            "provider": "in_app_feed",
            "message": f"In-app notification registered for alert {alert.alert_id}",
            "delivered_at": datetime.now(timezone.utc).isoformat()
        }


class WebhookNotificationProvider(BaseNotificationProvider):
    """Protected webhook provider (e.g. for civic operations center dispatch)."""
    def __init__(self, endpoint_url: Optional[str] = None):
        self.endpoint_url = endpoint_url

    def deliver(self, alert: MultiHazardAlert, target: str) -> Dict[str, Any]:
        if not self.endpoint_url:
            return {
                "success": False,
                "provider": "webhook",
                "message": "Webhook URL not configured. Delivery suppressed.",
                "status": "UNCONFIGURED"
            }
        
        # Bounded network dispatch
        import requests
        try:
            payload = {
                "alert_id": alert.alert_id,
                "hazard_type": alert.hazard_type,
                "severity_level": alert.severity_level,
                "headline": alert.headline,
                "is_official_warning": alert.is_official_warning,
                "issuing_authority": alert.issuing_authority,
                "dispatched_at": datetime.now(timezone.utc).isoformat()
            }
            resp = requests.post(self.endpoint_url, json=payload, timeout=5)
            if resp.status_code in [200, 201, 202, 204]:
                return {
                    "success": True,
                    "provider": "webhook",
                    "status_code": resp.status_code,
                    "delivered_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "success": False,
                    "provider": "webhook",
                    "status_code": resp.status_code,
                    "message": f"Webhook returned HTTP {resp.status_code}"
                }
        except Exception as e:
            logger.warning(f"Webhook dispatch failed: {e}")
            return {
                "success": False,
                "provider": "webhook",
                "message": str(e)
            }


class EmailNotificationProviderStub(BaseNotificationProvider):
    """Email delivery provider stub. Strictly guarded by external configuration."""
    def deliver(self, alert: MultiHazardAlert, target: str) -> Dict[str, Any]:
        return {
            "success": False,
            "provider": "email_smtp",
            "message": "External SMTP not configured in development environment.",
            "status": "UNCONFIGURED"
        }


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.providers: Dict[str, BaseNotificationProvider] = {
            "in_app": InAppNotificationProvider(),
            "webhook": WebhookNotificationProvider(endpoint_url=os.getenv("ALERT_WEBHOOK_URL")),
            "email": EmailNotificationProviderStub()
        }

    def is_notifications_enabled(self) -> bool:
        """Checks if external notifications are explicitly enabled."""
        val = os.getenv("NOTIFICATIONS_ENABLED", "false").strip().lower()
        return val in ["true", "1", "yes"]

    def dispatch_alert_notifications(
        self,
        alert: MultiHazardAlert,
        channels: Optional[List[str]] = None,
        recipient_target: str = "broadcast_civic_feed"
    ) -> List[AlertNotification]:
        """
        Dispatches alert across specified or default channels.
        In-app is always recorded; external channels are suppressed unless NOTIFICATIONS_ENABLED=true.
        """
        selected_channels = channels or ["in_app"]
        dispatched_records = []
        is_external_enabled = self.is_notifications_enabled()

        for ch in selected_channels:
            # Check duplicate delivery for the same alert_id and channel
            existing = self.db.query(AlertNotification).filter_by(
                alert_id=alert.alert_id,
                channel=ch
            ).first()

            if existing and existing.status == "DELIVERED":
                logger.info(f"Notification for alert {alert.alert_id} on {ch} already delivered. Deduplicating.")
                continue

            notif_id = f"notif_{uuid.uuid4().hex[:12]}"
            provider = self.providers.get(ch)

            if not provider:
                logger.warning(f"Unregistered channel {ch}")
                continue

            # Safety enforcement: if external channel and NOTIFICATIONS_ENABLED is false, suppress
            if ch != "in_app" and not is_external_enabled:
                record = AlertNotification(
                    notification_id=notif_id,
                    alert_id=alert.alert_id,
                    channel=ch,
                    recipient_target=recipient_target,
                    status="SUPPRESSED",
                    attempt_count=0,
                    payload_summary=f"[{alert.severity_level}] {alert.headline}",
                    provider_response={"reason": "NOTIFICATIONS_ENABLED=false (Safe Mode)"},
                    error_message="External delivery disabled by default safety policy.",
                    sent_at=None,
                    created_at=datetime.now(timezone.utc)
                )
                self.db.add(record)
                dispatched_records.append(record)
                continue

            # Attempt delivery via provider
            outcome = provider.deliver(alert, recipient_target)
            status_val = "DELIVERED" if outcome.get("success") else "FAILED"
            sent_time = datetime.now(timezone.utc) if outcome.get("success") else None

            record = AlertNotification(
                notification_id=notif_id,
                alert_id=alert.alert_id,
                channel=ch,
                recipient_target=recipient_target,
                status=status_val,
                attempt_count=1,
                payload_summary=f"[{alert.severity_level}] {alert.headline}",
                provider_response=outcome,
                error_message=outcome.get("message") if not outcome.get("success") else None,
                sent_at=sent_time,
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(record)
            dispatched_records.append(record)

        self.db.commit()
        return dispatched_records
