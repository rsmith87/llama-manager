from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreateJobCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    payload: dict[str, Any]
    priority: int = 0
    target_selector: str = "auto"
    requested_by: str | None = None


class CreateApiKeyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    role: str = "operator"


class CreateAuditEventCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str
    event_type: str
    dry_run: bool = False
    target: str | None = None
    route: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SaveChatSessionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str
    model: str
    target_selector: str = "auto"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    request_defaults: dict[str, Any] = Field(default_factory=dict)


class AddArtifactCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    attempt_id: str | None = None
    kind: str
    uri: str
    meta: dict[str, Any] | None = None
