from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MarketAsset(Base):
    __tablename__ = "market_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange_id: Mapped[int | None] = mapped_column(ForeignKey("exchanges.id", ondelete="SET NULL"), nullable=True, index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_market_asset_symbol_exchange"),
    )
