"""Add authoritative finance ledger and balance sheet records.

Revision ID: 20261102_000004
Revises: 20260926_000003
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_000004"
down_revision = "20260926_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("institution", sa.String(120), nullable=True),
        sa.Column("currency_code", sa.String(3), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("opening_balance", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(name) > 0", name="ck_accounts_name_nonempty"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_accounts_user_client_id"),
    )
    op.create_index("ix_accounts_user_created", "accounts", ["user_id", "created_at"])

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category_type", sa.String(12), nullable=False),
        sa.Column("sync_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("category_type IN ('INCOME', 'EXPENSE')", name="ck_categories_type"),
        sa.UniqueConstraint("user_id", "name", "category_type", name="uq_category_user_name_type"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_categories_user_client_id"),
    )

    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transfer_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reversal_of_id", sa.Integer(), sa.ForeignKey("finance_transactions.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("transaction_type", sa.String(12), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency_code", sa.String(3), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "transaction_type IN ('INCOME', 'EXPENSE', 'TRANSFER')",
            name="ck_transaction_type",
        ),
        sa.CheckConstraint("amount > 0", name="ck_transaction_positive_amount"),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND transfer_account_id IS NOT NULL AND "
            "transfer_account_id <> account_id AND category_id IS NULL) OR "
            "(transaction_type IN ('INCOME', 'EXPENSE') AND transfer_account_id IS NULL AND category_id IS NOT NULL)",
            name="ck_transaction_shape",
        ),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_transaction_user_idempotency"),
        sa.UniqueConstraint("reversal_of_id", name="uq_transaction_reversal"),
    )
    op.create_index(
        "ix_transaction_user_date", "finance_transactions", ["user_id", "transaction_date", "id"]
    )
    op.create_index("ix_transaction_account_date", "finance_transactions", ["account_id", "transaction_date"])
    op.create_index("ix_transaction_transfer_account", "finance_transactions", ["transfer_account_id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency_code", sa.String(3), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_budget_positive_amount"),
        sa.CheckConstraint("end_date >= start_date", name="ck_budget_date_range"),
    )
    op.create_index("ix_budget_user_dates", "budgets", ["user_id", "start_date", "end_date"])

    op.create_table(
        "financial_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("currency_code", sa.String(3), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("current_value", sa.Numeric(24, 8), nullable=False),
        sa.Column("valued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("current_value >= 0", name="ck_financial_asset_nonnegative"),
    )
    op.create_index("ix_financial_asset_user_valued", "financial_assets", ["user_id", "valued_at"])

    op.create_table(
        "liabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("liability_type", sa.String(32), nullable=False),
        sa.Column("currency_code", sa.String(3), sa.ForeignKey("currencies.code"), nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(24, 8), nullable=False),
        sa.Column("valued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("outstanding_balance >= 0", name="ck_liability_nonnegative"),
    )
    op.create_index("ix_liability_user_valued", "liabilities", ["user_id", "valued_at"])


def downgrade() -> None:
    op.drop_index("ix_liability_user_valued", table_name="liabilities")
    op.drop_table("liabilities")
    op.drop_index("ix_financial_asset_user_valued", table_name="financial_assets")
    op.drop_table("financial_assets")
    op.drop_index("ix_budget_user_dates", table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_transaction_transfer_account", table_name="finance_transactions")
    op.drop_index("ix_transaction_account_date", table_name="finance_transactions")
    op.drop_index("ix_transaction_user_date", table_name="finance_transactions")
    op.drop_table("finance_transactions")
    op.drop_table("categories")
    op.drop_index("ix_accounts_user_created", table_name="accounts")
    op.drop_table("accounts")
