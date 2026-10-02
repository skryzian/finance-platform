from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DataQualityRecord(Base):
    __tablename__ = "data_quality_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    data_state: Mapped[str] = mapped_column(String(24), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
