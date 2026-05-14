from llama_manager.core.persistence.audit_store_orm import AuditStoreOrm
from tests.persistence_db_setup import prepare_audit_db


def _exercise_store(store):
    created_a = store.create_event(
        actor="alice",
        event_type="auth_login",
        dry_run=False,
        target="alice",
        route="auth",
        payload={"ok": True},
    )
    created_b = store.create_event(
        actor="bob",
        event_type="chat_request",
        dry_run=True,
        target="node-a",
        route="chat",
        payload={"tokens": 42},
    )

    assert created_a["actor"] == "alice"
    assert created_b["dry_run"] is True

    all_events = store.list_events(limit=10)
    assert len(all_events) == 2

    by_type = store.list_events(event_type="auth", limit=10)
    assert len(by_type) == 1
    assert by_type[0]["event_type"] == "auth_login"

    by_target = store.list_events(target="node", limit=10)
    assert len(by_target) == 1
    assert by_target[0]["target"] == "node-a"

    dry_only = store.list_events(dry_run=True, limit=10)
    assert len(dry_only) == 1
    assert dry_only[0]["dry_run"] is True


def test_audit_store_orm_behavior(tmp_path):
    prepare_audit_db(tmp_path / "orm-audit.db")
    store = AuditStoreOrm(db_path=tmp_path / "orm-audit.db")
    _exercise_store(store)
