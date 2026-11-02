"""Add user-consented AI retrieval, notification delivery, and M-Pesa flows.

Revision ID: 20261102_000007
Revises: 20261102_000006
Create Date: 2026-11-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_000007"
down_revision = "20261102_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("ai_data_access_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("budget_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mpesa_events_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_events_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("security_events_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("push_token", sa.String(255), nullable=False, unique=True),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("platform IN ('ios', 'android')", name="ck_push_device_platform"),
    )
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_key", sa.String(180), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("event_type IN ('BUDGET', 'MPESA', 'SYNC', 'SECURITY')", name="ck_notification_event_type"),
        sa.UniqueConstraint("user_id", "event_type", "event_key", name="uq_notification_user_event"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("provider_key", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_receipt", sa.String(160), nullable=True),
        sa.Column("last_error", sa.String(240), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("channel IN ('EMAIL', 'SMS', 'PUSH')", name="ck_notification_delivery_channel"),
        sa.CheckConstraint("status IN ('PENDING', 'SENDING', 'ACCEPTED', 'FAILED')", name="ck_notification_delivery_status"),
        sa.UniqueConstraint("notification_id", "channel", "destination", name="uq_notification_delivery_destination"),
    )
    op.create_index("ix_notification_deliveries_notification_id", "notification_deliveries", ["notification_id"])
    op.create_table(
        "mpesa_account_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("income_category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_reference", sa.String(20), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "mpesa_c2b_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("income_category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receipt_number", sa.String(24), nullable=False, unique=True),
        sa.Column("account_reference", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 0), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PROCESSING"),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_mpesa_c2b_positive_amount"),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'POSTED', 'RECONCILIATION_REQUIRED')",
            name="ck_mpesa_c2b_status",
        ),
    )
    op.create_index("ix_mpesa_c2b_payments_user_id", "mpesa_c2b_payments", ["user_id"])
    op.create_table(
        "mpesa_stk_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(14, 0), nullable=False),
        sa.Column("phone_number", sa.String(12), nullable=False),
        sa.Column("description", sa.String(120), nullable=False),
        sa.Column("account_reference", sa.String(12), nullable=False),
        sa.Column("merchant_request_id", sa.String(100), nullable=True),
        sa.Column("checkout_request_id", sa.String(100), nullable=True, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="SUBMITTING"),
        sa.Column("result_code", sa.String(20), nullable=True),
        sa.Column("result_description", sa.String(240), nullable=True),
        sa.Column("mpesa_receipt_number", sa.String(24), nullable=True, unique=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("finance_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_mpesa_stk_positive_amount"),
        sa.CheckConstraint(
            "status IN ('SUBMITTING', 'PENDING', 'SUCCEEDED', 'FAILED', 'RECONCILIATION_REQUIRED')",
            name="ck_mpesa_stk_status",
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_mpesa_stk_user_idempotency"),
    )
    op.create_index("ix_mpesa_stk_requests_user_id", "mpesa_stk_requests", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mpesa_stk_requests_user_id", table_name="mpesa_stk_requests")
    op.drop_table("mpesa_stk_requests")
    op.drop_index("ix_mpesa_c2b_payments_user_id", table_name="mpesa_c2b_payments")
    op.drop_table("mpesa_c2b_payments")
    op.drop_table("mpesa_account_mappings")
    op.drop_index("ix_notification_deliveries_notification_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_push_devices_user_id", table_name="push_devices")
    op.drop_table("push_devices")
    op.drop_table("notification_preferences")
    op.drop_column("users", "ai_data_access_enabled")
