from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from llama_manager.core.persistence.db_infra import (
    create_persistence_engine,
    create_session_factory,
    require_sqlite_tables,
    session_scope,
    sqlite_path_from_url,
    sqlite_url_for_path,
)
from llama_manager.core.persistence.models.app_state import AuditEventOrm


class AuditStoreOrm:
    def __init__(self, db_path: Path | None = None, db_url: str | None = None):
        if db_url is None:
            if db_path is None:
                raise ValueError("db_path or db_url is required")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = sqlite_url_for_path(db_path)
        sqlite_path = sqlite_path_from_url(db_url)
        if sqlite_path is not None:
            require_sqlite_tables(
                db_path=sqlite_path,
                required_tables={"audit_events", "alembic_version"},
                target_name="audit",
            )
        self.engine = create_persistence_engine(db_url)
        self.session_factory = create_session_factory(self.engine)

    def create_event(
        self,
        *,
        actor: str,
        event_type: str,
        dry_run: bool,
        target: str | None,
        route: str | None,
        payload: dict[str, object],
    ) -> dict[str, object]:
        event_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        row = AuditEventOrm(
            id=event_id,
            actor=actor,
            event_type=event_type,
            dry_run=1 if dry_run else 0,
            target=target,
            route=route,
            payload_json=json.dumps(payload),
            created_at=created_at,
        )
        with session_scope(self.session_factory) as session:
            session.add(row)

        return {
            "id": event_id,
            "actor": actor,
            "event_type": event_type,
            "dry_run": dry_run,
            "target": target,
            "route": route,
            "payload": payload,
            "created_at": created_at,
        }

    def list_events(
        self,
        *,
        limit: int = 100,
        event_type: str | None = None,
        target: str | None = None,
        dry_run: bool | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict[str, object]]:
        stmt = select(AuditEventOrm)
        if event_type:
            stmt = stmt.where(func.lower(AuditEventOrm.event_type).like(f"%{event_type.lower()}%"))
        if target:
            stmt = stmt.where(func.lower(func.coalesce(AuditEventOrm.target, "")).like(f"%{target.lower()}%"))
        if dry_run is not None:
            stmt = stmt.where(AuditEventOrm.dry_run == (1 if dry_run else 0))
        if created_from:
            stmt = stmt.where(AuditEventOrm.created_at >= created_from)
        if created_to:
            stmt = stmt.where(AuditEventOrm.created_at <= created_to)

        stmt = stmt.order_by(AuditEventOrm.created_at.desc()).limit(max(1, min(limit, 1000)))

        with session_scope(self.session_factory) as session:
            rows = session.execute(stmt).scalars().all()

        out: list[dict[str, object]] = []
        for row in rows:
            out.append(
                {
                    "id": row.id,
                    "actor": row.actor,
                    "event_type": row.event_type,
                    "dry_run": bool(row.dry_run),
                    "target": row.target,
                    "route": row.route,
                    "payload": json.loads(row.payload_json),
                    "created_at": row.created_at,
                }
            )
        return out
