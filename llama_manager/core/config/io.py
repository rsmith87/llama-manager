from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from llama_manager.core.config.models import AppConfig


def _expand_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env_vars(item) for key, item in value.items()}
    return value


def load_config(source: str | Path | dict[str, Any] | None = None) -> AppConfig:
    if source is None:
        source = os.getenv("LLAMA_MANAGER_CONFIG")
        if source is None:
            local_config = Path("config.yaml")
            if local_config.exists():
                source = local_config
            else:
                local_example = Path("config.example.yaml")
                if local_example.exists():
                    source = local_example

    data: dict[str, Any]
    config_source = "(defaults)"
    if source is None:
        data = {}
    elif isinstance(source, dict):
        data = source
        config_source = "(in-memory)"
    else:
        config_path = Path(source)
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config file must contain a YAML mapping: {config_path}")
        data = loaded
        config_source = str(config_path.resolve())

    mode_override = os.getenv("LLAMA_MANAGER_MODE")
    if mode_override:
        data = {**data, "mode": mode_override}

    data = _expand_env_vars(data)

    return AppConfig.model_validate({**data, "config_source": config_source})


def save_config(config: AppConfig) -> None:
    if config.config_source in {"(defaults)", "(in-memory)"}:
        raise ValueError("Cannot persist config without a file-backed config_source")

    config_path = Path(config.config_source)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    data.pop("config_source", None)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
