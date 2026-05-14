from __future__ import annotations

import json

from llama_manager.core.persistence.dto.commands import (
    CreateApiKeyCommand,
    CreateAuditEventCommand,
    CreateJobCommand,
    SaveChatSessionCommand,
)
from llama_manager.core.persistence.dto.records import (
    ApiKeyRecord,
    ArtifactRecord,
    AuditEventRecord,
    ChatSessionRecord,
    ChatSessionSummaryRecord,
    JobEventRecord,
    JobRecord,
)
from llama_manager.core.persistence.models.app_state import ApiKeyOrm, AuditEventOrm, ChatSessionOrm
from llama_manager.core.persistence.models.orchestration import ArtifactOrm, JobEventOrm, JobOrm


def to_artifact_record(row: ArtifactOrm) -> ArtifactRecord:
    meta = json.loads(row.meta_json) if row.meta_json else None
    return ArtifactRecord(
        id=row.id,
        job_id=row.job_id,
        attempt_id=row.attempt_id,
        kind=row.kind,
        uri=row.uri,
        meta=meta,
        created_at=row.created_at,
    )


def to_job_event_record(row: JobEventOrm) -> JobEventRecord:
    return JobEventRecord(
        id=row.id,
        job_id=row.job_id,
        attempt_id=row.attempt_id,
        event_type=row.event_type,
        event_json=json.loads(row.event_json),
        created_at=row.created_at,
    )


def to_job_record(row: JobOrm, artifacts: list[ArtifactOrm] | list[ArtifactRecord] | None = None) -> JobRecord:
    artifact_records: list[ArtifactRecord]
    if not artifacts:
        artifact_records = []
    elif isinstance(artifacts[0], ArtifactRecord):
        artifact_records = list(artifacts)  # type: ignore[assignment]
    else:
        artifact_records = [to_artifact_record(item) for item in artifacts]  # type: ignore[arg-type]

    result = json.loads(row.result_json) if row.result_json else None
    return JobRecord(
        id=row.id,
        type=row.type,
        payload=json.loads(row.payload_json),
        requested_by=row.requested_by,
        priority=row.priority,
        status=row.status,
        target_selector=row.target_selector,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        result=result,
        error_code=row.error_code,
        error_detail=row.error_detail,
        cancellation_requested=row.status == "cancel_requested",
        artifacts=artifact_records,
    )


def to_api_key_record(row: ApiKeyOrm) -> ApiKeyRecord:
    return ApiKeyRecord(
        id=row.id,
        username=row.username,
        role=row.role,
        key_hint=row.key_hint,
        revoked=bool(row.revoked),
        created_at=row.created_at,
    )


def to_audit_event_record(row: AuditEventOrm) -> AuditEventRecord:
    return AuditEventRecord(
        id=row.id,
        actor=row.actor,
        event_type=row.event_type,
        dry_run=bool(row.dry_run),
        target=row.target,
        route=row.route,
        payload=json.loads(row.payload_json),
        created_at=row.created_at,
    )


def to_chat_session_summary_record(row: ChatSessionOrm) -> ChatSessionSummaryRecord:
    return ChatSessionSummaryRecord(
        id=row.id,
        name=row.name,
        model=row.model,
        target_selector=row.target_selector,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def to_chat_session_record(row: ChatSessionOrm) -> ChatSessionRecord:
    return ChatSessionRecord(
        id=row.id,
        name=row.name,
        model=row.model,
        target_selector=row.target_selector,
        messages=json.loads(row.messages_json),
        request_defaults=json.loads(row.request_defaults_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def build_job_orm(command: CreateJobCommand, *, job_id: str, created_at: str, updated_at: str) -> JobOrm:
    return JobOrm(
        id=job_id,
        type=command.type,
        payload_json=json.dumps(command.payload),
        requested_by=command.requested_by,
        priority=command.priority,
        status="queued",
        target_selector=command.target_selector,
        created_at=created_at,
        updated_at=updated_at,
    )


def build_api_key_orm(
    command: CreateApiKeyCommand,
    *,
    key_id: str,
    key_hash: str,
    key_hint: str,
    created_at: str,
) -> ApiKeyOrm:
    return ApiKeyOrm(
        id=key_id,
        username=command.username,
        role=command.role,
        key_hash=key_hash,
        key_hint=key_hint,
        revoked=0,
        created_at=created_at,
    )


def build_audit_event_orm(command: CreateAuditEventCommand, *, event_id: str, created_at: str) -> AuditEventOrm:
    return AuditEventOrm(
        id=event_id,
        actor=command.actor,
        event_type=command.event_type,
        dry_run=1 if command.dry_run else 0,
        target=command.target,
        route=command.route,
        payload_json=json.dumps(command.payload),
        created_at=created_at,
    )


def build_chat_session_orm(
    command: SaveChatSessionCommand,
    *,
    session_id: str,
    created_at: str,
    updated_at: str,
) -> ChatSessionOrm:
    return ChatSessionOrm(
        id=session_id,
        name=command.name,
        model=command.model,
        target_selector=command.target_selector,
        messages_json=json.dumps(command.messages),
        request_defaults_json=json.dumps(command.request_defaults),
        created_at=created_at,
        updated_at=updated_at,
    )
