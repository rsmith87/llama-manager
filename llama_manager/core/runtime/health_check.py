from __future__ import annotations

from llama_manager.core.config import AppConfig
from llama_manager.providers.system_metrics import get_system_metrics


def health_payload(config: AppConfig) -> dict[str, object]:
    return {
        "ok": True,
        "mode": config.mode,
        "config_source": config.config_source,
        "models_configured": len(config.models),
        "nodes_configured": len(config.nodes),
        "system": get_system_metrics(),
    }
