from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update

from llama_manager.core.persistence.db_infra import (
    create_persistence_engine,
    create_session_factory,
    require_sqlite_tables,
    session_scope,
    sqlite_path_from_url,
    sqlite_url_for_path,
)
from llama_manager.core.persistence.models.app_state import ApiKeyOrm


class AuthStoreOrm:
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
                required_tables={"api_keys", "alembic_version"},
                target_name="auth",
            )
        self.engine = create_persistence_engine(db_url)
        self.session_factory = create_session_factory(self.engine)

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_key(self, username: str, role: str) -> dict[str, object]:
        raw = f"lm_{secrets.token_urlsafe(24)}"
        key_id = str(uuid.uuid4())
        key_hash = self.hash_key(raw)
        hint = f"{raw[:6]}...{raw[-4:]}"
        created_at = datetime.now(UTC).isoformat()
        row = ApiKeyOrm(
            id=key_id,
            username=username,
            role=role,
            key_hash=key_hash,
            key_hint=hint,
            revoked=0,
            created_at=created_at,
        )
        with session_scope(self.session_factory) as session:
            session.add(row)
        return {
            "id": key_id,
            "username": username,
            "role": role,
            "key": raw,
            "key_hint": hint,
            "created_at": created_at,
        }

    def has_active_keys(self) -> bool:
        with session_scope(self.session_factory) as session:
            row = session.execute(select(ApiKeyOrm.id).where(ApiKeyOrm.revoked == 0).limit(1)).first()
        return row is not None

    def list_keys(self) -> list[dict[str, object]]:
        with session_scope(self.session_factory) as session:
            rows = session.execute(
                select(ApiKeyOrm).order_by(ApiKeyOrm.created_at.desc())
            ).scalars().all()
        return [
            {
                "id": row.id,
                "username": row.username,
                "role": row.role,
                "key_hint": row.key_hint,
                "revoked": row.revoked,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def revoke_key(self, key_id: str) -> bool:
        with session_scope(self.session_factory) as session:
            result = session.execute(
                update(ApiKeyOrm).where(ApiKeyOrm.id == key_id).values(revoked=1)
            )
        return (result.rowcount or 0) > 0

    def resolve_key(self, raw_key: str) -> dict[str, object] | None:
        key_hash = self.hash_key(raw_key)
        with session_scope(self.session_factory) as session:
            row = session.execute(
                select(ApiKeyOrm).where(ApiKeyOrm.key_hash == key_hash)
            ).scalar_one_or_none()
        if row is None or bool(row.revoked):
            return None
        return {"id": row.id, "username": row.username, "role": row.role, "revoked": row.revoked}
