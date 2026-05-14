from __future__ import annotations

from sqlalchemy import Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from llama_manager.core.persistence.alembic_config import Base


class ApiKeyOrm(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    key_hint: Mapped[str] = mapped_column(Text, nullable=False)
    revoked: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class AuditEventOrm(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    dry_run: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    route: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_audit_events_created_at", "created_at"),
    )


class ChatSessionOrm(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    target_selector: Mapped[str] = mapped_column(Text, nullable=False, default="auto", server_default="auto")
    messages_json: Mapped[str] = mapped_column(Text, nullable=False)
    request_defaults_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_chat_sessions_updated_at", "updated_at"),
    )
