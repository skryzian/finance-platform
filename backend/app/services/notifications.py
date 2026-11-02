import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import BackgroundTasks
from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.integrations import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    PushDevice,
)
from app.models.user import User
from app.providers.expo_push import ExpoPushProvider
from app.providers.sendgrid import SendGridNotificationProvider
from app.providers.twilio_sms import TwilioSMSProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryMessage:
    title: str
    body: str
    destination: str


def get_or_create_preferences(db: Session, user_id: int) -> NotificationPreference:
    preference = db.query(NotificationPreference).filter_by(user_id=user_id).first()
    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        db.add(preference)
        db.commit()
        db.refresh(preference)
    return preference


def enqueue_notification(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    event_key: str,
    title: str,
    body: str,
    background_tasks: BackgroundTasks | None = None,
) -> Notification | None:
    preference = get_or_create_preferences(db, user_id)
    enabled = {
        "BUDGET": preference.budget_alerts_enabled,
        "MPESA": preference.mpesa_events_enabled,
        "SYNC": preference.sync_events_enabled,
        "SECURITY": preference.security_events_enabled,
    }.get(event_type)
    if enabled is not True:
        return None

    existing = db.query(Notification).filter_by(
        user_id=user_id,
        event_type=event_type,
        event_key=event_key,
    ).first()
    if existing is not None:
        return existing

    notification = Notification(
        user_id=user_id,
        event_type=event_type,
        event_key=event_key,
        title=title[:160],
        body=body,
    )
    db.add(notification)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.query(Notification).filter_by(
            user_id=user_id,
            event_type=event_type,
            event_key=event_key,
        ).first()

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        db.rollback()
        raise ValueError("Notification recipient does not exist")

    pending: list[NotificationDelivery] = []
    if preference.email_enabled:
        pending.append(_delivery(notification.id, "EMAIL", user.email, "sendgrid"))
    if preference.sms_enabled:
        pending.append(_delivery(notification.id, "SMS", user.phone or "", "twilio"))
    if preference.push_enabled:
        devices = db.query(PushDevice).filter(
            PushDevice.user_id == user_id,
            PushDevice.active.is_(True),
        ).all()
        if devices:
            pending.extend(_delivery(notification.id, "PUSH", device.push_token, "expo") for device in devices)
        else:
            pending.append(_delivery(notification.id, "PUSH", "", "expo"))
    db.add_all(pending)
    db.commit()
    db.refresh(notification)
    if background_tasks is not None:
        for delivery in pending:
            db.refresh(delivery)
            background_tasks.add_task(dispatch_delivery, delivery.id)
    return notification


def _delivery(notification_id: int, channel: str, destination: str, provider_key: str) -> NotificationDelivery:
    return NotificationDelivery(
        notification_id=notification_id,
        channel=channel,
        destination=destination,
        provider_key=provider_key,
        status="PENDING",
    )


def _provider(provider_key: str):
    providers = {
        "sendgrid": SendGridNotificationProvider,
        "twilio": TwilioSMSProvider,
        "expo": ExpoPushProvider,
    }
    provider_class = providers.get(provider_key)
    if provider_class is None:
        raise ValueError(f"Unknown notification provider: {provider_key}")
    return provider_class()


async def dispatch_delivery(delivery_id: int) -> None:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        claim = db.execute(
            update(NotificationDelivery)
            .where(
                NotificationDelivery.id == delivery_id,
                NotificationDelivery.attempts < settings.notification_max_attempts,
                or_(
                    NotificationDelivery.status == "PENDING",
                    and_(
                        NotificationDelivery.status == "FAILED",
                        or_(
                            NotificationDelivery.next_attempt_at.is_(None),
                            NotificationDelivery.next_attempt_at <= now,
                        ),
                    ),
                ),
            )
            .values(
                status="SENDING",
                attempts=NotificationDelivery.attempts + 1,
                last_error=None,
            )
            .execution_options(synchronize_session=False)
        )
        if claim.rowcount != 1:
            db.rollback()
            return
        db.commit()
        delivery = db.query(NotificationDelivery).filter_by(id=delivery_id).first()
        if delivery is None:
            return
        notification = db.query(Notification).filter_by(id=delivery.notification_id).first()
        if notification is None:
            delivery.status = "FAILED"
            delivery.last_error = "Notification record not found"
            db.commit()
            return
        message = DeliveryMessage(
            title="Finance Platform update",
            body="Sign in to Finance Platform to view this update.",
            destination=delivery.destination,
        )
        try:
            receipt = await _provider(delivery.provider_key).send(message)
        except (RuntimeError, httpx.HTTPError, ValueError) as exc:
            _record_failure(db, delivery, str(exc))
            return
        except Exception:
            logger.exception(
                "notification_delivery_unexpected_error delivery_id=%s provider=%s",
                delivery.id,
                delivery.provider_key,
            )
            _record_failure(db, delivery, "Unexpected provider error")
            return
        delivery.status = "ACCEPTED"
        delivery.provider_receipt = receipt[:160] if receipt else None
        delivery.next_attempt_at = None
        delivery.last_error = None
        db.commit()


def _record_failure(db: Session, delivery: NotificationDelivery, error: str) -> None:
    delay_minutes = min(2 ** delivery.attempts, 60)
    delivery.status = "FAILED"
    delivery.last_error = error[:240]
    delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    db.commit()
    logger.warning(
        "notification_delivery_failed delivery_id=%s provider=%s attempt=%s",
        delivery.id,
        delivery.provider_key,
        delivery.attempts,
    )
