from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from fastapi import Request

from llama_manager.core.config import AppConfig

if TYPE_CHECKING:
    from llama_manager.core.chat.proxy import ChatProxy
    from llama_manager.core.model_assets.conversions import ConversionManager
    from llama_manager.core.model_assets.library import GgufLibrary
    from llama_manager.core.model_assets.downloads import DownloadManager
    from llama_manager.core.model_assets.quantizations import QuantizationManager
    from llama_manager.core.nodes.registry import NodeRegistry
    from llama_manager.core.orchestration.orchestrator import Orchestrator
    from llama_manager.core.runtime.process_manager import ProcessManager


def get_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_process_manager(request: Request) -> ProcessManager:
    return request.app.state.process_manager


def get_conversion_manager(request: Request) -> ConversionManager:
    return request.app.state.conversion_manager


def get_quantization_manager(request: Request) -> QuantizationManager:
    return request.app.state.quantization_manager


def get_node_registry(request: Request) -> NodeRegistry:
    return request.app.state.node_registry


def get_chat_proxy(request: Request) -> ChatProxy:
    return request.app.state.chat_proxy


def get_gguf_library(request: Request) -> GgufLibrary:
    return request.app.state.gguf_library


def get_download_manager(request: Request) -> DownloadManager:
    return request.app.state.download_manager


def get_chat_session_store(request: Request) -> Any:
    return request.app.state.chat_session_store


def get_audit_store(request: Request) -> Any:
    return request.app.state.audit_store


def get_orchestrator(request: Request) -> Orchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("Orchestrator is only available in controller mode")
    return orchestrator
