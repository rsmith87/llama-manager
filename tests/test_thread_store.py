from datetime import datetime

from llama_manager.core.threads.models import ThreadEventRecord, ThreadRecord
from llama_manager.core.threads import store as thread_store_module
from llama_manager.core.threads.store import ThreadStore


def test_thread_store_creates_thread_and_public_events(tmp_path):
    store = ThreadStore(tmp_path / "threads.db")

    thread = store.create_thread(
        title="Debug stack trace",
        default_model="qwen",
        metadata={"app": "codex", "purpose": "coding", "priority": "medium", "request_type": "coding"},
        created_by="alice",
    )
    user_event = store.append_event(
        thread_id=thread["id"],
        event_type="user_message",
        role="user",
        content={"text": "Explain this stack trace"},
        public=True,
    )
    store.append_event(
        thread_id=thread["id"],
        event_type="routing_decision",
        role=None,
        content={"strategy": "deterministic", "node": "linux-2080ti"},
        public=False,
    )

    events = store.list_events(thread["id"], include_internal=False)

    assert thread["title"] == "Debug stack trace"
    assert user_event["thread_id"] == thread["id"]
    assert [event["event_type"] for event in events] == ["user_message"]


def test_thread_store_can_include_internal_events(tmp_path):
    store = ThreadStore(tmp_path / "threads.db")
    thread = store.create_thread(title=None, default_model=None, metadata={}, created_by=None)
    store.append_event(thread["id"], "user_message", "user", {"text": "hi"}, public=True)
    store.append_event(thread["id"], "routing_decision", None, {"node": "mac-mini"}, public=False)

    events = store.list_events(thread["id"], include_internal=True)

    assert [event["event_type"] for event in events] == ["user_message", "routing_decision"]


def test_thread_store_get_thread_persists_and_round_trips_json_fields(tmp_path):
    db_path = tmp_path / "threads.db"
    store = ThreadStore(db_path)
    metadata = {
        "app": "codex",
        "purpose": "coding",
        "priority": "high",
        "request_type": "research",
        "nested": {"labels": ["routing", "debug"]},
    }
    content = {"text": "hi", "attachments": [{"name": "trace.txt", "lines": [1, 2, 3]}]}
    route = {"strategy": "deterministic", "candidates": [{"node": "mac-mini", "score": 0.92}]}

    thread = store.create_thread(
        title="Route request",
        default_model="qwen",
        metadata=metadata,
        created_by="alice",
    )
    created_updated_at = datetime.fromisoformat(thread["updated_at"])
    event = store.append_event(
        thread_id=thread["id"],
        event_type="assistant_message",
        role="assistant",
        content=content,
        public=True,
        route=route,
        agent_node="mac-mini",
        model="qwen",
    )

    reopened = ThreadStore(db_path)
    persisted_thread = reopened.get_thread(thread["id"])
    events = reopened.list_events(thread["id"], include_internal=True)

    assert persisted_thread["metadata"] == metadata
    assert persisted_thread["updated_at"] != thread["updated_at"]
    assert datetime.fromisoformat(persisted_thread["created_at"])
    assert datetime.fromisoformat(persisted_thread["updated_at"]) >= created_updated_at
    assert event["content"] == content
    assert event["route"] == route
    assert events[0]["content"] == content
    assert events[0]["route"] == route
    assert datetime.fromisoformat(events[0]["created_at"])


def test_thread_record_models_accept_store_timestamp_shape(tmp_path):
    store = ThreadStore(tmp_path / "threads.db")
    thread = store.create_thread(title="Timestamps", default_model=None, metadata={}, created_by=None)
    event = store.append_event(thread["id"], "user_message", "user", {"text": "hi"}, public=True)

    thread_record = ThreadRecord.model_validate(store.get_thread(thread["id"]))
    event_record = ThreadEventRecord.model_validate(event)

    assert isinstance(thread_record.created_at, datetime)
    assert isinstance(thread_record.updated_at, datetime)
    assert isinstance(event_record.created_at, datetime)


def test_append_event_advances_updated_at_when_clock_does_not(monkeypatch, tmp_path):
    frozen_timestamp = "2026-05-18T12:00:00+00:00"
    monkeypatch.setattr(thread_store_module, "_utc_now", lambda: frozen_timestamp)
    store = ThreadStore(tmp_path / "threads.db")
    thread = store.create_thread(title="Frozen clock", default_model=None, metadata={}, created_by=None)

    event = store.append_event(thread["id"], "user_message", "user", {"text": "hi"}, public=True)
    updated_thread = store.get_thread(thread["id"])

    assert updated_thread["updated_at"] == "2026-05-18T12:00:00.000001+00:00"
    assert event["created_at"] == updated_thread["updated_at"]
