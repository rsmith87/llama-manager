from llama_manager.core.persistence.chat_session_store_orm import ChatSessionStoreOrm
from tests.persistence_db_setup import prepare_chat_sessions_db


def _exercise_store(store):
    listed = store.list_sessions()
    assert listed == []

    saved = store.save_session(
        name="run-1",
        model="qwen",
        target_selector="auto",
        messages=[{"role": "user", "content": "hello"}],
        request_defaults={"temperature": 0.2},
    )
    sid = saved["id"]
    assert saved["name"] == "run-1"
    assert saved["messages"][0]["content"] == "hello"

    listed_after = store.list_sessions()
    assert len(listed_after) == 1
    assert listed_after[0]["id"] == sid

    loaded = store.get_session(sid)
    assert loaded is not None
    assert loaded["request_defaults"]["temperature"] == 0.2

    updated = store.save_session(
        session_id=sid,
        name="run-1-updated",
        model="qwen",
        target_selector="auto",
        messages=[{"role": "user", "content": "hello again"}],
        request_defaults={"temperature": 0.5},
    )
    assert updated["id"] == sid
    assert updated["name"] == "run-1-updated"
    assert updated["messages"][0]["content"] == "hello again"

    assert store.delete_session(sid) is True
    assert store.delete_session(sid) is False
    assert store.get_session(sid) is None


def test_chat_session_store_orm_behavior(tmp_path):
    prepare_chat_sessions_db(tmp_path / "orm-chat.db")
    store = ChatSessionStoreOrm(db_path=tmp_path / "orm-chat.db")
    _exercise_store(store)
