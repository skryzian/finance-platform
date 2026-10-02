from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MarketAssetOut(BaseModel):
    id: int
    symbol: str
    name: str
    asset_type: str
    exchange: str | None
    country_code: str | None
    currency_code: str | None
    provider: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class WatchlistOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchlistItemCreate(BaseModel):
    market_asset_id: int
    notes: str | None = Field(default=None, max_length=500)


class WatchlistItemOut(BaseModel):
    id: int
    watchlist_id: int
    market_asset_id: int
    notes: str | None
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


AlertCategory = Literal[
    "PRICE_ALERT", "DIVIDEND_ALERT", "MARKET_ALERT", "NEWS_ALERT",
    "PORTFOLIO_ALERT", "BUDGET_ALERT", "LOAN_ALERT", "CRYPTO_ALERT",
    "PROMOTION_ALERT", "ECONOMIC_EVENT_ALERT", "NET_WORTH_ALERT", "SUBSCRIPTION_ALERT",
]


class AlertRuleCreate(BaseModel):
    market_asset_id: int | None = None
    category: AlertCategory
    condition_type: str = Field(..., min_length=1, max_length=40)
    threshold: Decimal | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    channels: list[str] = Field(default_factory=lambda: ["IN_APP"])
    conditions: dict = Field(default_factory=dict)


class AlertRuleOut(BaseModel):
    id: int
    user_id: int
    market_asset_id: int | None
    category: str
    condition_type: str
    threshold: Decimal | None
    currency_code: str | None
    priority: str
    channels: list
    conditions: dict
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertOut(BaseModel):
    id: int
    category: str
    title: str
    message: str
    priority: str
    status: str
    source_url: str | None
    provider_key: str | None
    data_timestamp: datetime | None
    created_at: datetime
    viewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OpportunityOut(BaseModel):
    id: int
    opportunity_type: str
    asset_or_product: str | None
    title: str
    summary: str
    country_code: str | None
    currency_code: str | None
    source: str
    source_url: str | None
    discovered_at: datetime
    expires_at: datetime | None
    requirements: dict
    relevant_criteria: dict
    evidence: list
    risk_information: str | None
    relevance_factors: dict
    status: str
    verification_status: str
    provider_key: str | None
    retrieved_at: datetime | None
    published_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OpportunityReviewUpdate(BaseModel):
    status: Literal["UNDER_REVIEW", "USER_VIEWED", "SAVED", "DISMISSED"]
    user_notes: str | None = Field(default=None, max_length=2000)


class OpportunityReviewOut(BaseModel):
    id: int
    opportunity_id: int
    user_id: int
    status: str
    user_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
