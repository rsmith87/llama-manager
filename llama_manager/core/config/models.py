from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Mode = Literal["agent", "controller"]
ReasoningMode = Literal["on", "off", "auto"]


class ModelConfig(BaseModel):
    path: str
    port: int
    ctx: int = 4096
    gpu_layers: int = Field(default=0)
    host: str = "127.0.0.1"
    reasoning: ReasoningMode | None = None
    reasoning_budget: int | None = None
    vision: bool = False
    mmproj: str | None = None
    extra_args: list[str] = Field(default_factory=list)
    supports_json_schema: bool | None = None
    supports_grammar: bool | None = None
    favorite: bool = False
    prompt_template: str | None = None


class NodeConfig(BaseModel):
    url: str
    api_key: str | None = None
    verify_tls: bool = True


class AppConfig(BaseModel):
    mode: Mode = "agent"
    llama_server_bin: str = "llama-server"
    llama_cpp_dir: Path = Path("./llama.cpp")
    python_bin: str = "python3"
    hf_models_dir: Path | None = None
    hf_models_dirs: list[Path] = Field(default_factory=list)
    log_dir: Path = Path("./logs")
    models: dict[str, ModelConfig] = Field(default_factory=dict)
    nodes: dict[str, NodeConfig] = Field(default_factory=dict)
    agent_api_key: str | None = None
    controller_registration_key: str | None = None
    node_heartbeat_timeout_seconds: int = 90
    controller_url: str | None = None
    node_name: str | None = None
    agent_url: str = "http://127.0.0.1:9000"
    heartbeat_interval_seconds: int = 30
    controller_retention_days: int = 30
    controller_archive_retention_days: int = 90
    controller_archive_dir: Path = Path("./logs/archive")
    controller_registration_key_outbound: str | None = None
    auth_db_url: str | None = None
    audit_db_url: str | None = None
    chat_sessions_db_url: str | None = None
    controller_db_url: str | None = None
    controller_instance_id: str = "controller-default"
    controller_leader_lease_seconds: int = 30
    agent_worker_enabled: bool = False
    agent_worker_poll_interval_seconds: int = 2
    agent_worker_max_jobs: int = 1
    agent_worker_labels: dict[str, Any] = Field(default_factory=dict)
    agent_worker_capacity: dict[str, Any] = Field(default_factory=dict)
    config_source: str = "(defaults)"

    @model_validator(mode="before")
    @classmethod
    def normalize_model_roots(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw_single = data.get("hf_models_dir")
        if isinstance(raw_single, list) and "hf_models_dirs" not in data:
            data = {**data, "hf_models_dirs": raw_single, "hf_models_dir": None}
        return data

    @property
    def model_roots(self) -> list[Path]:
        roots = list(self.hf_models_dirs)
        if not roots and self.hf_models_dir is not None:
            roots.append(self.hf_models_dir)
        deduped = []
        seen = set()
        for root in roots:
            key = str(root)
            if key not in seen:
                deduped.append(root)
                seen.add(key)
        return deduped
