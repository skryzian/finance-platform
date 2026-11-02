"""Add per-user change cursors for offline synchronization.

Revision ID: 20261102_000005
Revises: 20261102_000004
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_000005"
down_revision = "20261102_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_sync_state",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO user_sync_state (user_id, version) SELECT id, 0 FROM users")
    op.create_table(
        "sync_events",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(24), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("sync_events")
    op.drop_table("user_sync_state")
