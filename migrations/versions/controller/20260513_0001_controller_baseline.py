"""controller baseline schema

Revision ID: 20260513_0001
Revises:
Create Date: 2026-05-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260513_0001"
down_revision = None
branch_labels = ("controller",)
depends_on = None


def _target() -> str:
    return context.get_x_argument(as_dictionary=True).get("db", "controller")


def upgrade() -> None:
    if _target() != "controller":
        return

    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("target_selector", sa.Text(), nullable=False, server_default=sa.text("'auto'")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
    )
    op.create_index("idx_jobs_status_priority_created", "jobs", ["status", "priority", "created_at"], unique=False)

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column("lease_expires_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("ended_at", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_job_attempts_job_id_jobs"),
        sa.PrimaryKeyConstraint("id", name="pk_job_attempts"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempts_job_id"),
    )

    op.create_table(
        "node_leases",
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column("last_heartbeat_at", sa.Text(), nullable=False),
        sa.Column("capacity_json", sa.Text(), nullable=True),
        sa.Column("labels_json", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("node_name", name="pk_node_leases"),
    )

    op.create_table(
        "job_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["job_attempts.id"], name="fk_job_events_attempt_id_job_attempts"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_job_events_job_id_jobs"),
        sa.PrimaryKeyConstraint("id", name="pk_job_events"),
    )
    op.create_index("idx_job_events_job_created", "job_events", ["job_id", "created_at"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("attempt_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["job_attempts.id"], name="fk_artifacts_attempt_id_job_attempts"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_artifacts_job_id_jobs"),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
    )
    op.create_index("idx_artifacts_job_created", "artifacts", ["job_id", "created_at"], unique=False)

    op.create_table(
        "schema_meta",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_schema_meta"),
    )

    op.create_table(
        "controller_leases",
        sa.Column("lease_name", sa.Text(), nullable=False),
        sa.Column("holder_id", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("lease_name", name="pk_controller_leases"),
    )


def downgrade() -> None:
    if _target() != "controller":
        return

    op.drop_table("controller_leases")
    op.drop_table("schema_meta")
    op.drop_index("idx_artifacts_job_created", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("idx_job_events_job_created", table_name="job_events")
    op.drop_table("job_events")
    op.drop_table("node_leases")
    op.drop_table("job_attempts")
    op.drop_index("idx_jobs_status_priority_created", table_name="jobs")
    op.drop_table("jobs")
