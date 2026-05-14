from sqlalchemy import Index

from llama_manager.core.persistence.models.app_state import ApiKeyOrm, AuditEventOrm, ChatSessionOrm


def _col(table, name: str):
    return table.columns[name]


def test_api_keys_orm_schema_parity():
    table = ApiKeyOrm.__table__
    assert table.name == "api_keys"
    assert _col(table, "id").primary_key is True
    assert _col(table, "username").nullable is False
    assert _col(table, "role").nullable is False
    assert _col(table, "key_hash").nullable is False
    assert _col(table, "key_hash").unique is True
    assert _col(table, "key_hint").nullable is False
    assert _col(table, "revoked").nullable is False
    assert _col(table, "created_at").nullable is False


def test_audit_events_orm_schema_parity():
    table = AuditEventOrm.__table__
    assert table.name == "audit_events"
    assert _col(table, "id").primary_key is True
    assert _col(table, "actor").nullable is False
    assert _col(table, "event_type").nullable is False
    assert _col(table, "dry_run").nullable is False
    assert _col(table, "target").nullable is True
    assert _col(table, "route").nullable is True
    assert _col(table, "payload_json").nullable is False
    assert _col(table, "created_at").nullable is False

    index_names = {idx.name for idx in table.indexes if isinstance(idx, Index)}
    assert "idx_audit_events_created_at" in index_names


def test_chat_sessions_orm_schema_parity():
    table = ChatSessionOrm.__table__
    assert table.name == "chat_sessions"
    assert _col(table, "id").primary_key is True
    assert _col(table, "name").nullable is False
    assert _col(table, "model").nullable is False
    assert _col(table, "target_selector").nullable is False
    assert _col(table, "messages_json").nullable is False
    assert _col(table, "request_defaults_json").nullable is False
    assert _col(table, "created_at").nullable is False
    assert _col(table, "updated_at").nullable is False

    index_names = {idx.name for idx in table.indexes if isinstance(idx, Index)}
    assert "idx_chat_sessions_updated_at" in index_names
