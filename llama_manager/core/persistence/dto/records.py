from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str
    attempt_id: str | None = None
    kind: str
    uri: str
    meta: dict[str, Any] | None = None
    created_at: str


class JobEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str
    attempt_id: str | None = None
    event_type: str
    event_json: dict[str, Any]
    created_at: str


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    payload: dict[str, Any]
    requested_by: str | None = None
    priority: int
    status: str
    target_selector: str
    created_at: str
    updated_at: str
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_detail: str | None = None
    cancellation_requested: bool = False
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ClaimedJobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: JobRecord
    attempt_id: str
    lease_expires_at: str


class ApiKeyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    role: str
    key_hint: str | None = None
    revoked: bool = False
    created_at: str


class AuditEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    actor: str
    event_type: str
    dry_run: bool
    target: str | None = None
    route: str | None = None
    payload: dict[str, Any]
    created_at: str


class ChatSessionSummaryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    model: str
    target_selector: str
    created_at: str
    updated_at: str


class ChatSessionRecord(ChatSessionSummaryRecord):
    messages: list[dict[str, Any]]
    request_defaults: dict[str, Any]
