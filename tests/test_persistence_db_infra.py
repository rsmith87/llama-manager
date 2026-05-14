from sqlalchemy import text

from llama_manager.core.config import load_config
from llama_manager.core.persistence.db_infra import (
    create_persistence_engine,
    create_session_factory,
    resolve_persistence_urls,
    session_scope,
)


def test_resolve_persistence_urls_defaults_to_log_dir_paths(tmp_path):
    config = load_config({"log_dir": str(tmp_path)})

    urls = resolve_persistence_urls(config)

    assert urls.controller.endswith("/controller_state.db")
    assert urls.auth.endswith("/auth_store.db")
    assert urls.audit.endswith("/audit_events.db")
    assert urls.chat_sessions.endswith("/chat_sessions.db")


def test_resolve_persistence_urls_respects_overrides(tmp_path):
    config = load_config(
        {
            "log_dir": str(tmp_path),
            "controller_db_url": "sqlite+pysqlite:///tmp/controller.db",
            "auth_db_url": "sqlite+pysqlite:///tmp/auth.db",
            "audit_db_url": "sqlite+pysqlite:///tmp/audit.db",
            "chat_sessions_db_url": "sqlite+pysqlite:///tmp/chat.db",
        }
    )

    urls = resolve_persistence_urls(config)

    assert urls.controller == "sqlite+pysqlite:///tmp/controller.db"
    assert urls.auth == "sqlite+pysqlite:///tmp/auth.db"
    assert urls.audit == "sqlite+pysqlite:///tmp/audit.db"
    assert urls.chat_sessions == "sqlite+pysqlite:///tmp/chat.db"


def test_create_persistence_engine_enables_sqlite_foreign_keys(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'infra-test.db'}"
    engine = create_persistence_engine(db_url)

    with engine.connect() as conn:
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert foreign_keys == 1


def test_session_scope_commits_changes(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'session-scope.db'}"
    engine = create_persistence_engine(db_url)

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE entries (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"))

    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        session.execute(text("INSERT INTO entries(value) VALUES ('ok')"))

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM entries")).scalar_one()

    assert count == 1
