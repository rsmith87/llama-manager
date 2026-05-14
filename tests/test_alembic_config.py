from pathlib import Path

import pytest

from llama_manager.core.config import load_config
from llama_manager.core.persistence.alembic_config import (
    Base,
    NAMING_CONVENTION,
    head_revision_for,
    parse_alembic_target,
    resolve_target_url_from_config,
    target_metadata_for,
    version_locations,
)
from llama_manager.core.persistence import models as _models  # noqa: F401


def test_parse_alembic_target_defaults_to_controller():
    assert parse_alembic_target(None) == "controller"
    assert parse_alembic_target([]) == "controller"


def test_parse_alembic_target_reads_x_argument():
    assert parse_alembic_target(["db=auth"]) == "auth"


def test_parse_alembic_target_rejects_unknown_target():
    with pytest.raises(ValueError):
        parse_alembic_target(["db=unknown"])


def test_resolve_target_url_from_config_uses_overrides(tmp_path):
    config = load_config(
        {
            "log_dir": str(tmp_path),
            "controller_db_url": "sqlite+pysqlite:///tmp/controller.db",
            "auth_db_url": "sqlite+pysqlite:///tmp/auth.db",
            "audit_db_url": "sqlite+pysqlite:///tmp/audit.db",
            "chat_sessions_db_url": "sqlite+pysqlite:///tmp/chat.db",
        }
    )

    assert resolve_target_url_from_config(config, "controller") == "sqlite+pysqlite:///tmp/controller.db"
    assert resolve_target_url_from_config(config, "auth") == "sqlite+pysqlite:///tmp/auth.db"
    assert resolve_target_url_from_config(config, "audit") == "sqlite+pysqlite:///tmp/audit.db"
    assert resolve_target_url_from_config(config, "chat_sessions") == "sqlite+pysqlite:///tmp/chat.db"


def test_base_metadata_uses_locked_naming_convention():
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    assert NAMING_CONVENTION["pk"] == "pk_%(table_name)s"


def test_version_locations_include_all_targets(tmp_path):
    locations = version_locations(tmp_path)
    rendered = [str(path) for path in locations]

    assert str(Path(tmp_path) / "migrations" / "versions" / "controller") in rendered
    assert str(Path(tmp_path) / "migrations" / "versions" / "auth") in rendered
    assert str(Path(tmp_path) / "migrations" / "versions" / "audit") in rendered
    assert str(Path(tmp_path) / "migrations" / "versions" / "chat_sessions") in rendered


def test_target_metadata_for_returns_only_selected_target_tables():
    assert set(target_metadata_for("auth").tables) == {"api_keys"}
    assert set(target_metadata_for("audit").tables) == {"audit_events"}
    assert set(target_metadata_for("chat_sessions").tables) == {"chat_sessions"}
    assert set(target_metadata_for("controller").tables) == {
        "artifacts",
        "controller_leases",
        "job_attempts",
        "job_events",
        "jobs",
        "node_leases",
        "schema_meta",
    }


def test_head_revision_for_returns_target_branch_head():
    assert head_revision_for("controller") == "controller@head"
    assert head_revision_for("auth") == "auth@head"
    assert head_revision_for("audit") == "audit@head"
    assert head_revision_for("chat_sessions") == "chat_sessions@head"
