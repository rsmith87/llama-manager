"""chat sessions baseline schema

Revision ID: 20260513_0004
Revises:
Create Date: 2026-05-13 00:03:00.000000
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260513_0004"
down_revision = None
branch_labels = ("chat_sessions",)
depends_on = None


def _target() -> str:
    return context.get_x_argument(as_dictionary=True).get("db", "controller")


def upgrade() -> None:
    if _target() != "chat_sessions":
        return

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("target_selector", sa.Text(), nullable=False, server_default=sa.text("'auto'")),
        sa.Column("messages_json", sa.Text(), nullable=False),
        sa.Column("request_defaults_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
    )
    op.create_index("idx_chat_sessions_updated_at", "chat_sessions", ["updated_at"], unique=False)


def downgrade() -> None:
    if _target() != "chat_sessions":
        return

    op.drop_index("idx_chat_sessions_updated_at", table_name="chat_sessions")
    op.drop_table("chat_sessions")
