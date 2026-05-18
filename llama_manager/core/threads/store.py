from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


class ThreadStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def create_thread(
        self,
        title: str | None,
        default_model: str | None,
        metadata: dict[str, Any],
        created_by: str | None,
    ) -> dict[str, Any]:
        now = _utc_now()
        record = {
            "id": str(uuid4()),
            "title": title,
            "default_model": default_model,
            "metadata": metadata,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO threads (id, title, default_model, metadata, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["title"],
                        record["default_model"],
                        json.dumps(record["metadata"]),
                        record["created_by"],
                        record["created_at"],
                        record["updated_at"],
                    ),
                )
        return record

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            raise KeyError(thread_id)
        return _thread_from_row(row)

    def append_event(
        self,
        thread_id: str,
        event_type: str,
        role: str | None,
        content: dict[str, Any],
        public: bool,
        route: dict[str, Any] | None = None,
        agent_node: str | None = None,
        model: str | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            with conn:
                thread_row = conn.execute("SELECT updated_at FROM threads WHERE id = ?", (thread_id,)).fetchone()
                if thread_row is None:
                    raise KeyError(thread_id)

                timestamp = _monotonic_timestamp(_utc_now(), thread_row["updated_at"])
                record = {
                    "id": str(uuid4()),
                    "thread_id": thread_id,
                    "event_type": event_type,
                    "role": role,
                    "content": content,
                    "public": public,
                    "route": route,
                    "agent_node": agent_node,
                    "model": model,
                    "error_code": error_code,
                    "error_detail": error_detail,
                    "created_at": timestamp,
                }
                conn.execute(
                    """
                    INSERT INTO thread_events (
                        id, thread_id, event_type, role, content, public, route,
                        agent_node, model, error_code, error_detail, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["thread_id"],
                        record["event_type"],
                        record["role"],
                        json.dumps(record["content"]),
                        1 if record["public"] else 0,
                        json.dumps(record["route"]) if record["route"] is not None else None,
                        record["agent_node"],
                        record["model"],
                        record["error_code"],
                        record["error_detail"],
                        record["created_at"],
                    ),
                )
                conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (timestamp, thread_id))
        return record

    def list_events(self, thread_id: str, include_internal: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM thread_events WHERE thread_id = ?"
        params: tuple[Any, ...] = (thread_id,)
        if not include_internal:
            query += " AND public = ?"
            params = (thread_id, 1)
        query += " ORDER BY sequence ASC"

        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [_event_from_row(row) for row in rows]

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS threads (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        default_model TEXT,
                        metadata TEXT NOT NULL,
                        created_by TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS thread_events (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        id TEXT NOT NULL UNIQUE,
                        thread_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        role TEXT,
                        content TEXT NOT NULL,
                        public INTEGER NOT NULL,
                        route TEXT,
                        agent_node TEXT,
                        model TEXT,
                        error_code TEXT,
                        error_detail TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (thread_id) REFERENCES threads(id)
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _monotonic_timestamp(now: str, previous: str) -> str:
    now_datetime = datetime.fromisoformat(now)
    previous_datetime = datetime.fromisoformat(previous)
    if now_datetime <= previous_datetime:
        return (previous_datetime + timedelta(microseconds=1)).isoformat()
    return now


def _thread_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "default_model": row["default_model"],
        "metadata": json.loads(row["metadata"]),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "event_type": row["event_type"],
        "role": row["role"],
        "content": json.loads(row["content"]),
        "public": bool(row["public"]),
        "route": json.loads(row["route"]) if row["route"] is not None else None,
        "agent_node": row["agent_node"],
        "model": row["model"],
        "error_code": row["error_code"],
        "error_detail": row["error_detail"],
        "created_at": row["created_at"],
    }
