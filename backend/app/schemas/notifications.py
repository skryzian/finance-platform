from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationPreferences(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    budget_alerts_enabled: bool
    mpesa_events_enabled: bool
    sync_events_enabled: bool
    security_events_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class PushDeviceCreate(BaseModel):
    push_token: str = Field(..., min_length=16, max_length=255)
    platform: Literal["ios", "android"]

    @field_validator("push_token")
    @classmethod
    def validate_token_format(cls, value: str) -> str:
        if not value.startswith(("ExponentPushToken[", "ExpoPushToken[")) or not value.endswith("]"):
            raise ValueError("A valid Expo push token is required")
        return value


class PushDeviceOut(BaseModel):
    id: int
    platform: str
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: int
    event_type: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryOut(BaseModel):
    id: int
    notification_id: int
    channel: str
    status: str
    attempts: int
    provider_receipt: str | None
    last_error: str | None
    next_attempt_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
