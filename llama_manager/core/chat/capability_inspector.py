from __future__ import annotations

import hashlib
import json
from typing import Any

from llama_manager.core.config import AppConfig
from llama_manager.core.runtime.process_manager import ProcessManager


class CapabilityInspector:
    def __init__(self, process_manager: ProcessManager, config: AppConfig):
        self.process_manager = process_manager
        self.config = config

    def capabilities(self, model_name: str) -> dict[str, Any]:
        model_known = True
        running = False
        status_payload: dict[str, Any] | None = None
        try:
            status = self.process_manager.status(model_name)
            status_payload = status.to_dict() if hasattr(status, "to_dict") else status
            running = bool(status_payload.get("running")) if isinstance(status_payload, dict) else False
        except KeyError:
            model_known = self.config.mode == "controller"
            if not model_known:
                raise
        model_cfg = self.config.models.get(model_name)
        model_cfg_payload = model_cfg.model_dump(mode="json") if model_cfg is not None else {"model": model_name}
        model_config_hash = hashlib.sha256(json.dumps(model_cfg_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        supports_json_schema = False
        supports_grammar = False
        structured_sources = {"json_schema": "default", "grammar": "default"}
        if model_cfg is not None:
            if model_cfg.supports_json_schema is not None:
                supports_json_schema = bool(model_cfg.supports_json_schema)
                structured_sources["json_schema"] = "config_flag"
            if model_cfg.supports_grammar is not None:
                supports_grammar = bool(model_cfg.supports_grammar)
                structured_sources["grammar"] = "config_flag"
            lowered_args = [str(item).lower() for item in model_cfg.extra_args]
            if structured_sources["json_schema"] != "config_flag" and any("json-schema" in item or "json_schema" in item for item in lowered_args):
                supports_json_schema = True
                structured_sources["json_schema"] = "extra_args"
            if structured_sources["grammar"] != "config_flag" and any("grammar" in item for item in lowered_args):
                supports_grammar = True
                structured_sources["grammar"] = "extra_args"

        return {
            "model": model_name,
            "known_model": model_known,
            "model_config_hash": model_config_hash,
            "supports": {
                "stream": True,
                "reasoning": True,
                "vision": bool(getattr(self.config.models.get(model_name), "vision", False)),
                "sampling": {
                    "temperature": True,
                    "max_tokens": True,
                    "top_p": True,
                    "top_k": True,
                    "min_p": True,
                    "repeat_penalty": True,
                    "seed": True,
                    "stop": True,
                },
                "structured_output": {"json_schema": supports_json_schema, "grammar": supports_grammar},
                "structured_output_source": structured_sources,
            },
            "runtime": {
                "running": running,
                "ctx": getattr(model_cfg, "ctx", None) if model_cfg is not None else None,
                "gpu_layers": getattr(model_cfg, "gpu_layers", None) if model_cfg is not None else None,
                "host": getattr(model_cfg, "host", None) if model_cfg is not None else None,
                "port": getattr(model_cfg, "port", None) if model_cfg is not None else None,
            },
        }
