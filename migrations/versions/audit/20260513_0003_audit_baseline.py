"""audit baseline schema

Revision ID: 20260513_0003
Revises:
Create Date: 2026-05-13 00:02:00.000000
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260513_0003"
down_revision = None
branch_labels = ("audit",)
depends_on = None


def _target() -> str:
    return context.get_x_argument(as_dictionary=True).get("db", "controller")


def upgrade() -> None:
    if _target() != "audit":
        return

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("route", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("idx_audit_events_created_at", "audit_events", ["created_at"], unique=False)


def downgrade() -> None:
    if _target() != "audit":
        return

    op.drop_index("idx_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
