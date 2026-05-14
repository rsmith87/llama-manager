import json

from llama_manager.core.persistence.dto.commands import (
    CreateApiKeyCommand,
    CreateAuditEventCommand,
    CreateJobCommand,
    SaveChatSessionCommand,
)
from llama_manager.core.persistence.dto.converters import (
    build_api_key_orm,
    build_audit_event_orm,
    build_chat_session_orm,
    build_job_orm,
    to_api_key_record,
    to_artifact_record,
    to_audit_event_record,
    to_chat_session_record,
    to_chat_session_summary_record,
    to_job_event_record,
    to_job_record,
)
from llama_manager.core.persistence.models.app_state import ApiKeyOrm, AuditEventOrm, ChatSessionOrm
from llama_manager.core.persistence.models.orchestration import ArtifactOrm, JobEventOrm, JobOrm


def test_build_job_orm_and_record_conversion_roundtrip():
    cmd = CreateJobCommand(type="chat", payload={"prompt": "hello"}, priority=2, target_selector="auto", requested_by="alice")
    orm = build_job_orm(cmd, job_id="job-1", created_at="2026-05-13T00:00:00+00:00", updated_at="2026-05-13T00:00:00+00:00")

    assert isinstance(orm, JobOrm)
    assert orm.status == "queued"
    assert json.loads(orm.payload_json) == {"prompt": "hello"}

    record = to_job_record(orm)
    assert record.id == "job-1"
    assert record.type == "chat"
    assert record.payload == {"prompt": "hello"}
    assert record.priority == 2
    assert record.cancellation_requested is False


def test_to_job_record_marks_cancel_requested():
    orm = JobOrm(
        id="job-2",
        type="chat",
        payload_json=json.dumps({"prompt": "x"}),
        requested_by=None,
        priority=0,
        status="cancel_requested",
        target_selector="auto",
        created_at="2026-05-13T00:00:00+00:00",
        updated_at="2026-05-13T00:00:00+00:00",
        completed_at=None,
        result_json=None,
        error_code=None,
        error_detail=None,
    )

    record = to_job_record(orm)
    assert record.cancellation_requested is True


def test_artifact_and_event_converter_decodes_json():
    artifact = ArtifactOrm(
        id="a-1",
        job_id="job-1",
        attempt_id="attempt-1",
        kind="log",
        uri="s3://bucket/log.txt",
        meta_json=json.dumps({"size": 10}),
        created_at="2026-05-13T00:00:00+00:00",
    )
    event = JobEventOrm(
        id="e-1",
        job_id="job-1",
        attempt_id="attempt-1",
        event_type="progress",
        event_json=json.dumps({"pct": 42}),
        created_at="2026-05-13T00:00:00+00:00",
    )

    artifact_record = to_artifact_record(artifact)
    event_record = to_job_event_record(event)

    assert artifact_record.meta == {"size": 10}
    assert event_record.event_json == {"pct": 42}


def test_build_api_key_orm_and_record_conversion_roundtrip():
    cmd = CreateApiKeyCommand(username="alice", role="admin")
    orm = build_api_key_orm(
        cmd,
        key_id="k-1",
        key_hash="hash-1",
        key_hint="lm_abcd...1234",
        created_at="2026-05-13T00:00:00+00:00",
    )

    assert isinstance(orm, ApiKeyOrm)
    assert orm.username == "alice"
    assert orm.revoked == 0

    record = to_api_key_record(orm)
    assert record.id == "k-1"
    assert record.username == "alice"
    assert record.role == "admin"
    assert record.revoked is False


def test_build_audit_event_orm_and_record_conversion_roundtrip():
    cmd = CreateAuditEventCommand(
        actor="alice",
        event_type="auth_login",
        dry_run=True,
        target="alice",
        route="auth",
        payload={"ok": True},
    )
    orm = build_audit_event_orm(cmd, event_id="ev-1", created_at="2026-05-13T00:00:00+00:00")

    assert isinstance(orm, AuditEventOrm)
    assert orm.dry_run == 1
    assert json.loads(orm.payload_json) == {"ok": True}

    record = to_audit_event_record(orm)
    assert record.id == "ev-1"
    assert record.dry_run is True
    assert record.payload == {"ok": True}


def test_build_chat_session_orm_and_record_conversion_roundtrip():
    cmd = SaveChatSessionCommand(
        id="s-1",
        name="Session",
        model="qwen",
        target_selector="auto",
        messages=[{"role": "user", "content": "hello"}],
        request_defaults={"temperature": 0.5},
    )
    orm = build_chat_session_orm(
        cmd,
        session_id="s-1",
        created_at="2026-05-13T00:00:00+00:00",
        updated_at="2026-05-13T00:00:00+00:00",
    )

    assert isinstance(orm, ChatSessionOrm)
    assert json.loads(orm.messages_json) == [{"role": "user", "content": "hello"}]
    assert json.loads(orm.request_defaults_json) == {"temperature": 0.5}

    summary = to_chat_session_summary_record(orm)
    full = to_chat_session_record(orm)

    assert summary.id == "s-1"
    assert summary.model == "qwen"
    assert full.messages == [{"role": "user", "content": "hello"}]
    assert full.request_defaults == {"temperature": 0.5}
