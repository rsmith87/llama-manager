from __future__ import annotations

from pathlib import Path
from typing import Sequence

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from llama_manager.core.config.models import AppConfig
from llama_manager.core.persistence.db_infra import PersistenceUrls, resolve_persistence_urls


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


DB_TARGETS: tuple[str, ...] = ("controller", "auth", "audit", "chat_sessions")

TARGET_TABLES: dict[str, tuple[str, ...]] = {
    "controller": (
        "artifacts",
        "controller_leases",
        "job_attempts",
        "job_events",
        "jobs",
        "node_leases",
        "schema_meta",
    ),
    "auth": ("api_keys",),
    "audit": ("audit_events",),
    "chat_sessions": ("chat_sessions", "model_downloads"),
}


def parse_alembic_target(x_args: Sequence[str] | None) -> str:
    if not x_args:
        return "controller"
    pairs = dict(item.split("=", 1) for item in x_args if "=" in item)
    target = pairs.get("db", "controller")
    if target not in DB_TARGETS:
        expected = ", ".join(DB_TARGETS)
        raise ValueError(f"Unknown Alembic target '{target}'. Expected one of: {expected}")
    return target


def resolve_target_url(target: str, urls: PersistenceUrls) -> str:
    if target == "controller":
        return urls.controller
    if target == "auth":
        return urls.auth
    if target == "audit":
        return urls.audit
    if target == "chat_sessions":
        return urls.chat_sessions
    expected = ", ".join(DB_TARGETS)
    raise ValueError(f"Unknown Alembic target '{target}'. Expected one of: {expected}")


def resolve_target_url_from_config(config: AppConfig, target: str) -> str:
    return resolve_target_url(target=target, urls=resolve_persistence_urls(config))


def head_revision_for(target: str) -> str:
    if target not in DB_TARGETS:
        expected = ", ".join(DB_TARGETS)
        raise ValueError(f"Unknown Alembic target '{target}'. Expected one of: {expected}")
    return f"{target}@head"


def target_metadata_for(target: str) -> MetaData:
    if target not in TARGET_TABLES:
        expected = ", ".join(DB_TARGETS)
        raise ValueError(f"Unknown Alembic target '{target}'. Expected one of: {expected}")

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    for table_name in TARGET_TABLES[target]:
        source = Base.metadata.tables[table_name]
        source.to_metadata(metadata, name=table_name)
    return metadata


def version_locations(project_root: Path) -> list[Path]:
    return [
        project_root / "migrations" / "versions" / "controller",
        project_root / "migrations" / "versions" / "auth",
        project_root / "migrations" / "versions" / "audit",
        project_root / "migrations" / "versions" / "chat_sessions",
    ]
