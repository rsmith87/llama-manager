from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from llama_manager.core.persistence.db_infra import (
    create_persistence_engine,
    create_session_factory,
    require_sqlite_tables,
    session_scope,
    sqlite_path_from_url,
    sqlite_url_for_path,
)


class OrchestrationStoreOrm:
    SCHEMA_VERSION = 3

    def __init__(self, db_path: Path | None = None, db_url: str | None = None):
        if db_url and db_url.startswith("postgres"):
            raise RuntimeError("Postgres orchestration backend is not supported for the execution substrate milestone")
        if db_url is None:
            if db_path is None:
                raise ValueError("db_path is required for sqlite backend")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = sqlite_url_for_path(db_path)

        self.db_url = db_url
        self.engine = create_persistence_engine(db_url)
        self.session_factory = create_session_factory(self.engine)
        sqlite_path = sqlite_path_from_url(db_url)
        if sqlite_path is not None:
            require_sqlite_tables(
                db_path=sqlite_path,
                required_tables={
                    "jobs",
                    "job_attempts",
                    "node_leases",
                    "job_events",
                    "artifacts",
                    "schema_meta",
                    "controller_leases",
                    "alembic_version",
                },
                target_name="controller",
            )

    @contextmanager
    def tx(self) -> Iterator[Session]:
        with session_scope(self.session_factory) as session:
            yield session
