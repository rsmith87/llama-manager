from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from llama_manager.core.persistence.alembic_config import Base


class JobOrm(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    target_selector: Mapped[str] = mapped_column(Text, nullable=False, default="auto", server_default="auto")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_jobs_status_priority_created", "status", "priority", "created_at"),
    )


class JobAttemptOrm(Base):
    __tablename__ = "job_attempts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(Text, nullable=False)
    lease_expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    ended_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempts_job_id"),
    )


class NodeLeaseOrm(Base):
    __tablename__ = "node_leases"

    node_name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_heartbeat_at: Mapped[str] = mapped_column(Text, nullable=False)
    capacity_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class JobEventOrm(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("job_attempts.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_job_events_job_created", "job_id", "created_at"),
    )


class ArtifactOrm(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("job_attempts.id"), nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_artifacts_job_created", "job_id", "created_at"),
    )


class SchemaMetaOrm(Base):
    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class ControllerLeaseOrm(Base):
    __tablename__ = "controller_leases"

    lease_name: Mapped[str] = mapped_column(Text, primary_key=True)
    holder_id: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
