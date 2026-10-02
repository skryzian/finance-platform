"""Add international reference and intelligence foundation tables.

Revision ID: 20260925_000002
Revises: 20240925_000001
Create Date: 2026-09-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_000002"
down_revision = "20240925_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(10), nullable=False, server_default="en"))
    op.add_column("users", sa.Column("locale", sa.String(20), nullable=False, server_default="en_KE"))
    op.add_column("users", sa.Column("date_format", sa.String(20), nullable=False, server_default="DD/MM/YYYY"))
    op.add_column("users", sa.Column("time_format", sa.String(8), nullable=False, server_default="24h"))
    op.add_column("users", sa.Column("number_format", sa.String(32), nullable=False, server_default="#,##0.00"))

    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False, unique=True),
        sa.Column("alpha3", sa.String(3), nullable=False, unique=True),
        sa.Column("country_name", sa.String(100), nullable=False),
        sa.Column("default_currency", sa.String(3), nullable=False),
        sa.Column("default_timezone", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("phone_country_code", sa.String(8), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_countries_country_code", "countries", ["country_code"], unique=True)

    op.create_table(
        "currencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(3), nullable=False, unique=True),
        sa.Column("currency_name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_currencies_code", "currencies", ["code"], unique=True)

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_rates_base_currency", "exchange_rates", ["base_currency"])
    op.create_index("ix_exchange_rates_quote_currency", "exchange_rates", ["quote_currency"])
    op.create_index("ix_exchange_rates_effective_at", "exchange_rates", ["effective_at"])

    op.create_table(
        "exchanges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_exchanges_code", "exchanges", ["code"], unique=True)
    op.create_index("ix_exchanges_country_code", "exchanges", ["country_code"])

    op.create_table(
        "market_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("exchange", sa.String(100), nullable=True),
        sa.Column("exchange_id", sa.Integer(), sa.ForeignKey("exchanges.id", ondelete="SET NULL"), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("provider", sa.String(80), nullable=False, server_default="manual"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "exchange", name="uq_market_asset_symbol_exchange"),
    )
    op.create_index("ix_market_assets_symbol", "market_assets", ["symbol"])
    op.create_index("ix_market_assets_exchange_id", "market_assets", ["exchange_id"])
    op.create_index("ix_market_assets_id", "market_assets", ["id"])

    op.create_table(
        "data_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_key", sa.String(80), nullable=False, unique=True),
        sa.Column("provider_type", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("terms_url", sa.String(512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(30), nullable=False, server_default="UNCONFIGURED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_data_providers_provider_key", "data_providers", ["provider_key"], unique=True)
    op.create_index("ix_data_providers_provider_type", "data_providers", ["provider_type"])

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlist_user_name"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])
    op.create_index("ix_watchlists_id", "watchlists", ["id"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_asset_id", sa.Integer(), sa.ForeignKey("market_assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("watchlist_id", "market_asset_id", name="uq_watchlist_asset"),
    )
    op.create_index("ix_watchlist_items_watchlist_id", "watchlist_items", ["watchlist_id"])
    op.create_index("ix_watchlist_items_market_asset_id", "watchlist_items", ["market_asset_id"])
    op.create_index("ix_watchlist_items_id", "watchlist_items", ["id"])

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_asset_id", sa.Integer(), sa.ForeignKey("market_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("condition_type", sa.String(40), nullable=False),
        sa.Column("threshold", sa.Numeric(20, 8), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("priority", sa.String(12), nullable=False, server_default="MEDIUM"),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_alert_rules_user_id", "alert_rules", ["user_id"])
    op.create_index("ix_alert_rules_market_asset_id", "alert_rules", ["market_asset_id"])
    op.create_index("ix_alert_rules_category", "alert_rules", ["category"])
    op.create_index("ix_alert_rules_id", "alert_rules", ["id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(12), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(20), nullable=False, server_default="NEW"),
        sa.Column("dedupe_key", sa.String(160), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("provider_key", sa.String(80), nullable=True),
        sa.Column("data_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_alert_user_dedupe"),
    )
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_alerts_category", "alerts", ["category"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])
    op.create_index("ix_alerts_id", "alerts", ["id"])

    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="QUEUED"),
        sa.Column("provider_key", sa.String(80), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_alert_deliveries_alert_id", "alert_deliveries", ["alert_id"])

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("opportunity_type", sa.String(40), nullable=False),
        sa.Column("asset_or_product", sa.String(200), nullable=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("relevant_criteria", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("risk_information", sa.Text(), nullable=True),
        sa.Column("relevance_factors", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="DETECTED"),
        sa.Column("verification_status", sa.String(24), nullable=False, server_default="UNVERIFIED"),
        sa.Column("event_fingerprint", sa.String(128), nullable=True, unique=True),
        sa.Column("provider_key", sa.String(80), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_opportunities_user_id", "opportunities", ["user_id"])
    op.create_index("ix_opportunities_type", "opportunities", ["opportunity_type"])
    op.create_index("ix_opportunities_country", "opportunities", ["country_code"])
    op.create_index("ix_opportunities_status", "opportunities", ["status"])
    op.create_index("ix_opportunities_verification", "opportunities", ["verification_status"])
    op.create_index("ix_opportunities_discovered_at", "opportunities", ["discovered_at"])

    op.create_table(
        "opportunity_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("verification_status", sa.String(24), nullable=False, server_default="UNVERIFIED"),
    )
    op.create_index("ix_opportunity_sources_opportunity_id", "opportunity_sources", ["opportunity_id"])

    op.create_table(
        "opportunity_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="DETECTED"),
        sa.Column("user_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("opportunity_id", "user_id", name="uq_opportunity_review_user"),
    )
    op.create_index("ix_opportunity_reviews_opportunity_id", "opportunity_reviews", ["opportunity_id"])
    op.create_index("ix_opportunity_reviews_user_id", "opportunity_reviews", ["user_id"])

    op.create_table(
        "data_quality_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_key", sa.String(160), nullable=False),
        sa.Column("quality_status", sa.String(24), nullable=False),
        sa.Column("data_state", sa.String(24), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_data_quality_provider_key", "data_quality_records", ["provider_key"])
    op.create_index("ix_data_quality_entity_type", "data_quality_records", ["entity_type"])
    op.create_index("ix_data_quality_entity_key", "data_quality_records", ["entity_key"])
    op.create_index("ix_data_quality_status", "data_quality_records", ["quality_status"])

    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("model_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_interactions_user_id", "ai_interactions", ["user_id"])
    op.create_index("ix_ai_interactions_created_at", "ai_interactions", ["created_at"])

    op.create_table(
        "ai_tool_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interaction_id", sa.Integer(), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_tool_calls_interaction_id", "ai_tool_calls", ["interaction_id"])


def downgrade() -> None:
    op.drop_table("ai_tool_calls")
    op.drop_table("ai_interactions")
    op.drop_table("data_quality_records")
    op.drop_table("opportunity_reviews")
    op.drop_table("opportunity_sources")
    op.drop_table("opportunities")
    op.drop_table("alert_deliveries")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("data_providers")
    op.drop_table("market_assets")
    op.drop_table("exchanges")
    op.drop_table("exchange_rates")
    op.drop_table("currencies")
    op.drop_table("countries")
    op.drop_column("users", "number_format")
    op.drop_column("users", "time_format")
    op.drop_column("users", "date_format")
    op.drop_column("users", "locale")
    op.drop_column("users", "language")
