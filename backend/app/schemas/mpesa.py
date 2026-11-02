from datetime import datetime
from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MpesaAccountMappingInput(BaseModel):
    account_id: int = Field(..., gt=0)
    income_category_id: int = Field(..., gt=0)
    account_reference: str = Field(..., min_length=4, max_length=20)

    @field_validator("account_reference")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{4,20}", normalized):
            raise ValueError("Reference must contain 4–20 letters, digits, underscores, or hyphens")
        return normalized


class MpesaAccountMappingOut(BaseModel):
    account_id: int
    income_category_id: int
    account_reference: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class MpesaStkRequestInput(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=120)
    account_id: int = Field(..., gt=0)
    category_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=0)
    phone_number: str = Field(..., min_length=12, max_length=13)
    description: str = Field(..., min_length=1, max_length=120)

    @field_validator("idempotency_key", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be blank")
        return normalized

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"\+?254[17]\d{8}", normalized):
            raise ValueError("Use a Kenyan Safaricom mobile number in 254XXXXXXXXX format")
        return normalized.removeprefix("+")


class MpesaStkRequestOut(BaseModel):
    id: int
    amount: Decimal
    phone_number: str
    description: str
    status: str
    result_description: str | None
    mpesa_receipt_number: str | None
    transaction_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
