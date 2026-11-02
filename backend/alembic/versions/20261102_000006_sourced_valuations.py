"""Add sourced daily FX rates and market price history.

Revision ID: 20261102_000006
Revises: 20261102_000005
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_000006"
down_revision = "20261102_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rate_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("data_state", sa.String(16), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("base_currency <> quote_currency", name="ck_fx_observation_distinct_pair"),
        sa.CheckConstraint("rate > 0", name="ck_fx_observation_positive_rate"),
        sa.UniqueConstraint(
            "base_currency",
            "quote_currency",
            "effective_date",
            "provider_key",
            name="uq_fx_observation_pair_date_provider",
        ),
    )
    op.create_index(
        "ix_fx_observation_pair_date",
        "exchange_rate_observations",
        ["base_currency", "quote_currency", "effective_date"],
    )
    op.create_table(
        "market_price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False, server_default=""),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("currency_source", sa.String(16), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("data_state", sa.String(16), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price > 0", name="ck_market_price_positive"),
        sa.CheckConstraint("asset_type IN ('EQUITY', 'ETF', 'CRYPTO')", name="ck_market_price_asset_type"),
        sa.CheckConstraint("currency_source IN ('PROVIDER', 'USER_ENTERED')", name="ck_market_price_currency_source"),
        sa.UniqueConstraint(
            "symbol",
            "asset_type",
            "exchange",
            "effective_date",
            "provider_key",
            name="uq_market_price_symbol_date_provider",
        ),
    )
    op.create_index(
        "ix_market_price_symbol_date",
        "market_price_history",
        ["symbol", "asset_type", "effective_date"],
    )

    op.get_bind().execute(
        sa.text(
            "INSERT INTO data_providers "
            "(provider_key, provider_type, display_name, base_url, terms_url, enabled, status, notes) "
            "VALUES (:provider_key, :provider_type, :display_name, :base_url, :terms_url, "
            ":enabled, :status, :notes) ON CONFLICT (provider_key) DO NOTHING"
        ),
        {
            "provider_key": "frankfurter_ecb",
            "provider_type": "EXCHANGE_RATE",
            "display_name": "Frankfurter / European Central Bank",
            "base_url": "https://api.frankfurter.dev",
            "terms_url": "https://frankfurter.dev/license/",
            "enabled": True,
            "status": "AVAILABLE",
            "notes": "Daily historical ECB reference-rate observations; not for live trading [migration 000006].",
        },
    )
    op.get_bind().execute(
        sa.text(
            "INSERT INTO data_providers "
            "(provider_key, provider_type, display_name, base_url, terms_url, enabled, status, notes) "
            "VALUES (:provider_key, :provider_type, :display_name, :base_url, :terms_url, "
            ":enabled, :status, :notes) ON CONFLICT (provider_key) DO NOTHING"
        ),
        {
            "provider_key": "alpha_vantage",
            "provider_type": "MARKET_DATA",
            "display_name": "Alpha Vantage",
            "base_url": "https://www.alphavantage.co",
            "terms_url": "https://www.alphavantage.co/premium/",
            "enabled": False,
            "status": "UNCONFIGURED",
            "notes": "Daily historical equity, ETF, and crypto data; requires a server-side API key [migration 000006].",
        },
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM data_providers WHERE provider_key IN ('frankfurter_ecb', 'alpha_vantage') "
        "AND notes LIKE '%[migration 000006].'"
    )
    op.drop_index("ix_market_price_symbol_date", table_name="market_price_history")
    op.drop_table("market_price_history")
    op.drop_index("ix_fx_observation_pair_date", table_name="exchange_rate_observations")
    op.drop_table("exchange_rate_observations")
