from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MarketPriceRefreshIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    asset_type: Literal["EQUITY", "ETF", "CRYPTO"]
    currency_code: str = Field(..., min_length=3, max_length=3)
    exchange: str | None = Field(default=None, max_length=50)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None


class MarketPriceOut(BaseModel):
    id: int
    symbol: str
    asset_type: str
    exchange: str | None
    currency_code: str
    currency_source: str
    price: Decimal
    effective_date: date
    provider_key: str
    data_state: str
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExchangeRateRefreshIn(BaseModel):
    base_currency: str = Field(..., min_length=3, max_length=3)
    quote_currency: str = Field(..., min_length=3, max_length=3)
    start_date: date
    end_date: date

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_request(self):
        if self.base_currency == self.quote_currency:
            raise ValueError("Base and quote currencies must differ")
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date")
        if (self.end_date - self.start_date).days > 365:
            raise ValueError("Request a maximum of 366 calendar days at a time")
        return self


class ExchangeRateOut(BaseModel):
    id: int
    base_currency: str
    quote_currency: str
    rate: Decimal
    effective_date: date
    provider_key: str
    data_state: str
    retrieved_at: datetime

    model_config = {"from_attributes": True}
