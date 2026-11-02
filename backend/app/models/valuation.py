from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ExchangeRateObservation(Base):
    __tablename__ = "exchange_rate_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False)
    data_state: Mapped[str] = mapped_column(String(16), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint("base_currency <> quote_currency", name="ck_fx_observation_distinct_pair"),
        CheckConstraint("rate > 0", name="ck_fx_observation_positive_rate"),
        UniqueConstraint(
            "base_currency",
            "quote_currency",
            "effective_date",
            "provider_key",
            name="uq_fx_observation_pair_date_provider",
        ),
    )


class MarketPriceHistory(Base):
    __tablename__ = "market_price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_source: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False)
    data_state: Mapped[str] = mapped_column(String(16), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint("price > 0", name="ck_market_price_positive"),
        CheckConstraint("asset_type IN ('EQUITY', 'ETF', 'CRYPTO')", name="ck_market_price_asset_type"),
        CheckConstraint("currency_source IN ('PROVIDER', 'USER_ENTERED')", name="ck_market_price_currency_source"),
        UniqueConstraint(
            "symbol",
            "asset_type",
            "exchange",
            "effective_date",
            "provider_key",
            name="uq_market_price_symbol_date_provider",
        ),
    )
