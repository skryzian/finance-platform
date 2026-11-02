import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.integrations import Notification, NotificationDelivery, NotificationPreference, PushDevice
from app.models.user import User
from app.schemas.notifications import (
    NotificationDeliveryOut,
    NotificationOut,
    NotificationPreferences,
    PushDeviceCreate,
    PushDeviceOut,
)
from app.services.notifications import dispatch_delivery, get_or_create_preferences

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_or_create_preferences(db, current_user.id)


@router.put("/preferences", response_model=NotificationPreferences)
def update_preferences(
    payload: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.sms_enabled and (
        not current_user.phone or not re.fullmatch(r"\+[1-9]\d{7,14}", current_user.phone)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add a phone number in E.164 format before enabling SMS delivery",
        )
    if payload.push_enabled and not db.query(PushDevice).filter(
        PushDevice.user_id == current_user.id,
        PushDevice.active.is_(True),
    ).first():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Register a mobile push device before enabling push delivery",
        )
    preference = get_or_create_preferences(db, current_user.id)
    for field, value in payload.model_dump().items():
        setattr(preference, field, value)
    db.commit()
    db.refresh(preference)
    return preference


@router.post("/devices", response_model=PushDeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(
    payload: PushDeviceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(PushDevice).filter(PushDevice.push_token == payload.push_token).first()
    if existing is not None and existing.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Push token is registered to another account")
    if existing is not None:
        existing.active = True
        existing.platform = payload.platform
        db.commit()
        db.refresh(existing)
        return existing
    device = PushDevice(
        user_id=current_user.id,
        push_token=payload.push_token,
        platform=payload.platform,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/devices", response_model=list[PushDeviceOut])
def list_devices(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(PushDevice)
        .filter(PushDevice.user_id == current_user.id, PushDevice.active.is_(True))
        .order_by(PushDevice.created_at.desc(), PushDevice.id.desc())
        .all()
    )


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    device = db.query(PushDevice).filter(
        PushDevice.id == device_id,
        PushDevice.user_id == current_user.id,
    ).first()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push device not found")
    device.active = False
    pending = db.query(NotificationDelivery).filter(
        NotificationDelivery.channel == "PUSH",
        NotificationDelivery.destination == device.push_token,
        NotificationDelivery.status.in_(("PENDING", "FAILED")),
    ).all()
    for delivery in pending:
        delivery.status = "FAILED"
        delivery.attempts = settings.notification_max_attempts
        delivery.last_error = "Push device was disabled"
        delivery.next_attempt_at = None
    active_device = db.query(PushDevice.id).filter(
        PushDevice.user_id == current_user.id,
        PushDevice.active.is_(True),
        PushDevice.id != device.id,
    ).first()
    if active_device is None:
        preference = db.query(NotificationPreference).filter_by(user_id=current_user.id).first()
        if preference is not None:
            preference.push_enabled = False
    db.commit()


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


@router.get("/deliveries", response_model=list[NotificationDeliveryOut])
def list_deliveries(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(NotificationDelivery)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .filter(Notification.user_id == current_user.id)
        .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/deliveries/{delivery_id}/retry", response_model=NotificationDeliveryOut)
def retry_delivery(
    delivery_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = (
        db.query(NotificationDelivery)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .filter(
            NotificationDelivery.id == delivery_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification delivery not found")
    if delivery.status != "FAILED" or delivery.attempts >= settings.notification_max_attempts:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery cannot be retried")
    delivery.status = "PENDING"
    delivery.next_attempt_at = None
    delivery.last_error = None
    db.commit()
    db.refresh(delivery)
    background_tasks.add_task(dispatch_delivery, delivery.id)
    return delivery
