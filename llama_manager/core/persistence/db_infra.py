from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from llama_manager.core.config.models import AppConfig


def sqlite_url_for_path(db_path: Path) -> str:
    return f"sqlite+pysqlite:///{db_path}"


def normalize_database_url(db_url_or_path: str | Path) -> str:
    value = str(db_url_or_path)
    if "://" in value:
        return value
    return sqlite_url_for_path(Path(value))


@dataclass(frozen=True)
class PersistenceUrls:
    controller: str
    auth: str
    audit: str
    chat_sessions: str


def resolve_persistence_urls(config: AppConfig) -> PersistenceUrls:
    log_dir = config.log_dir
    return PersistenceUrls(
        controller=normalize_database_url(config.controller_db_url or (log_dir / "controller_state.db")),
        auth=normalize_database_url(config.auth_db_url or (log_dir / "auth_store.db")),
        audit=normalize_database_url(config.audit_db_url or (log_dir / "audit_events.db")),
        chat_sessions=normalize_database_url(config.chat_sessions_db_url or (log_dir / "chat_sessions.db")),
    )


def create_persistence_engine(db_url: str, *, echo: bool = False) -> Engine:
    engine = create_engine(db_url, echo=echo, future=True, pool_pre_ping=True)

    if db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            try:
                dbapi_connection.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_FKEY, 1)
            except Exception:
                pass

    return engine


def create_session_factory(
    engine: Engine,
    *,
    autoflush: bool = False,
    expire_on_commit: bool = False,
) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, class_=Session, autoflush=autoflush, expire_on_commit=expire_on_commit)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sqlite_path_from_url(db_url: str) -> Path | None:
    try:
        parsed = make_url(db_url)
    except Exception:
        return None
    if parsed.drivername.startswith("sqlite") and parsed.database:
        return Path(parsed.database)
    return None


def require_sqlite_tables(
    *,
    db_path: Path,
    required_tables: set[str],
    target_name: str,
) -> None:
    if not db_path.exists():
        missing = ", ".join(sorted(required_tables))
        raise RuntimeError(
            f"Missing database for '{target_name}' at {db_path}. "
            f"Expected migrated schema tables: {missing}. "
            f"Run migrations first: alembic -x db={target_name} upgrade {target_name}@head"
        )

    try:
        engine = create_engine(sqlite_url_for_path(db_path), future=True, pool_pre_ping=True)
        try:
            found = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
    except Exception as exc:
        raise RuntimeError(
            f"Could not connect to database for '{target_name}' at {db_path}: {exc}"
        ) from exc

    missing_tables = sorted(required_tables - found)
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            f"Database schema for '{target_name}' is not migrated at {db_path}. "
            f"Missing tables: {missing}. "
            f"Run migrations first: alembic -x db={target_name} upgrade {target_name}@head"
        )
