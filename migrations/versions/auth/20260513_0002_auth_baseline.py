"""auth baseline schema

Revision ID: 20260513_0002
Revises:
Create Date: 2026-05-13 00:01:00.000000
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260513_0002"
down_revision = None
branch_labels = ("auth",)
depends_on = None


def _target() -> str:
    return context.get_x_argument(as_dictionary=True).get("db", "controller")


def upgrade() -> None:
    if _target() != "auth":
        return

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.Text(), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )


def downgrade() -> None:
    if _target() != "auth":
        return

    op.drop_table("api_keys")
