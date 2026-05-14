from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table, delete

from llama_manager.core.persistence.alembic_config import Base
from llama_manager.core.persistence.db_infra import create_persistence_engine, create_session_factory, session_scope, sqlite_url_for_path
from llama_manager.core.persistence.models.app_state import ApiKeyOrm, AuditEventOrm, ChatSessionOrm
from llama_manager.core.persistence.models.orchestration import (
    ArtifactOrm,
    ControllerLeaseOrm,
    JobAttemptOrm,
    JobEventOrm,
    JobOrm,
    NodeLeaseOrm,
    SchemaMetaOrm,
)


TARGET_REVISIONS = {
    "controller": "20260513_0001",
    "auth": "20260513_0002",
    "audit": "20260513_0003",
    "chat_sessions": "20260513_0004",
}
LATEST_REVISION = TARGET_REVISIONS["chat_sessions"]

ALEMBIC_VERSION = Table(
    "alembic_version",
    MetaData(),
    Column("version_num", String(32), primary_key=True),
)


def _write_schema(db_path: Path, tables: list, revision: str = LATEST_REVISION) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_persistence_engine(sqlite_url_for_path(db_path))
    Base.metadata.create_all(engine, tables=tables)
    ALEMBIC_VERSION.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        session.execute(delete(ALEMBIC_VERSION))
        session.execute(ALEMBIC_VERSION.insert().values(version_num=revision))
    engine.dispose()


def prepare_auth_db(db_path: Path, revision: str = TARGET_REVISIONS["auth"]) -> None:
    _write_schema(db_path, [ApiKeyOrm.__table__], revision)


def prepare_audit_db(db_path: Path, revision: str = TARGET_REVISIONS["audit"]) -> None:
    _write_schema(db_path, [AuditEventOrm.__table__], revision)


def prepare_chat_sessions_db(db_path: Path, revision: str = TARGET_REVISIONS["chat_sessions"]) -> None:
    _write_schema(db_path, [ChatSessionOrm.__table__], revision)


def prepare_controller_db(db_path: Path, revision: str = TARGET_REVISIONS["controller"]) -> None:
    _write_schema(
        db_path,
        [
            JobOrm.__table__,
            JobAttemptOrm.__table__,
            NodeLeaseOrm.__table__,
            JobEventOrm.__table__,
            ArtifactOrm.__table__,
            SchemaMetaOrm.__table__,
            ControllerLeaseOrm.__table__,
        ],
        revision,
    )


def prepare_all_persistence_dbs(log_dir: Path, revision: str | None = None) -> None:
    prepare_controller_db(log_dir / "controller_state.db", revision=revision or TARGET_REVISIONS["controller"])
    prepare_auth_db(log_dir / "auth_store.db", revision=revision or TARGET_REVISIONS["auth"])
    prepare_audit_db(log_dir / "audit_events.db", revision=revision or TARGET_REVISIONS["audit"])
    prepare_chat_sessions_db(log_dir / "chat_sessions.db", revision=revision or TARGET_REVISIONS["chat_sessions"])
