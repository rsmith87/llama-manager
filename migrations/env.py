from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from llama_manager.core.config import load_config
from llama_manager.core.persistence.alembic_config import parse_alembic_target, resolve_target_url_from_config, target_metadata_for
from llama_manager.core.persistence import models as _models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _selected_target() -> str:
    x_args = context.get_x_argument(as_dictionary=False)
    return parse_alembic_target(x_args)


def _selected_url() -> str:
    source = os.getenv("LLAMA_MANAGER_CONFIG")
    app_config = load_config(source)
    return resolve_target_url_from_config(config=app_config, target=_selected_target())


def run_migrations_offline() -> None:
    url = _selected_url()
    config.set_main_option("sqlalchemy.url", url)
    context.configure(
        url=url,
        target_metadata=target_metadata_for(_selected_target()),
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _selected_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata_for(_selected_target()),
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
