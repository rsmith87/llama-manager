from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from llama_manager.core.persistence.alembic_config import Base

from llama_manager.core.persistence.db_infra import (
    create_persistence_engine,
    create_session_factory,
    require_sqlite_tables,
    session_scope,
    sqlite_path_from_url,
    sqlite_url_for_path,
)
from llama_manager.core.persistence.models.app_state import ModelDownloadOrm


TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
VALID_STATUSES = {"queued", "running", "succeeded", "failed", "canceled"}


class ModelDownloadStoreOrm:
    def __init__(self, db_path: Path | None = None, db_url: str | None = None):
        if db_url is None:
            if db_path is None:
                raise ValueError("db_path or db_url is required")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = sqlite_url_for_path(db_path)
        sqlite_path = sqlite_path_from_url(db_url)
        self.engine = create_persistence_engine(db_url)
        Base.metadata.create_all(self.engine, tables=[ModelDownloadOrm.__table__])
        if sqlite_path is not None:
            require_sqlite_tables(
                db_path=sqlite_path,
                required_tables={"model_downloads", "alembic_version"},
                target_name="chat_sessions",
            )
        self.session_factory = create_session_factory(self.engine)

    def create_download(self, *, repo_id: str, revision: str | None, local_path: str, command: str, log_path: str, triggered_by: str) -> dict[str, object]:
        now = datetime.now(UTC).isoformat()
        download_id = str(uuid.uuid4())
        with session_scope(self.session_factory) as session:
            row = ModelDownloadOrm(
                id=download_id,
                repo_id=repo_id,
                revision=revision,
                local_path=local_path,
                status="queued",
                command=command,
                log_path=log_path,
                triggered_by=triggered_by or "unknown",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        return self.get_download(download_id)

    def update_status(self, download_id: str, *, status: str, pid: int | None = None, returncode: int | None = None, error_detail: str | None = None) -> dict[str, object]:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        now = datetime.now(UTC).isoformat()
        with session_scope(self.session_factory) as session:
            row = session.execute(select(ModelDownloadOrm).where(ModelDownloadOrm.id == download_id)).scalar_one_or_none()
            if row is None:
                raise KeyError(f"Unknown download id: {download_id}")
            if row.status in TERMINAL_STATUSES and row.status != status:
                raise ValueError(f"Cannot transition terminal status {row.status} -> {status}")
            row.status = status
            row.updated_at = now
            if status == "running" and row.started_at is None:
                row.started_at = now
            if status in TERMINAL_STATUSES:
                row.finished_at = now
            if pid is not None:
                row.pid = pid
            if returncode is not None:
                row.returncode = returncode
            if error_detail is not None:
                row.error_detail = error_detail
        return self.get_download(download_id)

    def get_download(self, download_id: str) -> dict[str, object]:
        with session_scope(self.session_factory) as session:
            row = session.execute(select(ModelDownloadOrm).where(ModelDownloadOrm.id == download_id)).scalar_one_or_none()
        if row is None:
            raise KeyError(f"Unknown download id: {download_id}")
        return self._row_to_dict(row)

    def list_downloads(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        query = select(ModelDownloadOrm)
        if status:
            query = query.where(ModelDownloadOrm.status == status)
        query = query.order_by(ModelDownloadOrm.created_at.desc()).limit(max(1, min(limit, 500)))
        with session_scope(self.session_factory) as session:
            rows = session.execute(query).scalars().all()
        return [self._row_to_dict(row) for row in rows]

    def delete_download(self, download_id: str) -> None:
        with session_scope(self.session_factory) as session:
            row = session.execute(select(ModelDownloadOrm).where(ModelDownloadOrm.id == download_id)).scalar_one_or_none()
            if row is None:
                raise KeyError(f"Unknown download id: {download_id}")
            session.delete(row)

    def _row_to_dict(self, row: ModelDownloadOrm) -> dict[str, object]:
        return {
            "id": row.id,
            "repo_id": row.repo_id,
            "revision": row.revision,
            "local_path": row.local_path,
            "status": row.status,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "bytes_downloaded": row.bytes_downloaded,
            "bytes_total": row.bytes_total,
            "pid": row.pid,
            "returncode": row.returncode,
            "command": row.command,
            "log_path": row.log_path,
            "error_detail": row.error_detail,
            "triggered_by": row.triggered_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
