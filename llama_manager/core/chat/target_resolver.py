from __future__ import annotations

from typing import Any

import httpx

from llama_manager.core.config import AppConfig
from llama_manager.core.nodes.registry import NodeRegistry
from llama_manager.core.runtime.process_manager import ProcessManager


class ModelNotRunningError(RuntimeError):
    pass


class TargetResolver:
    def __init__(self, process_manager: ProcessManager, node_registry: NodeRegistry, config: AppConfig):
        self.process_manager = process_manager
        self.node_registry = node_registry
        self.config = config

    async def resolve_controller_target(self, model_name: str, target_selector: str) -> dict[str, str]:
        selector = target_selector.strip().lower()
        if selector == "local":
            return self.resolve_local_target(model_name)
        if selector.startswith("node:"):
            node_name = selector.split(":", 1)[1].strip()
            if not node_name:
                raise ModelNotRunningError("Invalid target selector: node name is required")
            return await self.resolve_named_node_target(model_name, node_name)
        if selector not in {"", "auto"}:
            raise ModelNotRunningError("Invalid target selector. Use 'auto', 'local', or 'node:<name>'")

        try:
            return self.resolve_local_target(model_name)
        except ModelNotRunningError:
            pass

        for node in self.node_registry.list_nodes():
            if await self.is_model_running_on_node(node["name"], model_name):
                return {"kind": "remote", "url": node["url"], "node_name": node["name"]}
        raise ModelNotRunningError(f"Model is not running locally or on any controller node: {model_name}")

    def resolve_local_target(self, model_name: str) -> dict[str, str]:
        try:
            local_status = self.process_manager.status(model_name)
            local_data: Any = local_status.to_dict() if hasattr(local_status, "to_dict") else local_status
            if bool(local_data.get("running")):
                return {"kind": "local", "url": f"http://127.0.0.1:{local_data['port']}/v1/chat/completions"}
        except KeyError:
            raise ModelNotRunningError(f"Model is not running locally on controller host: {model_name}") from None
        raise ModelNotRunningError(f"Model is not running locally on controller host: {model_name}")

    async def resolve_named_node_target(self, model_name: str, node_name: str) -> dict[str, str]:
        node = next((item for item in self.node_registry.list_nodes() if item["name"] == node_name), None)
        if node is None:
            raise ModelNotRunningError(f"Unknown controller node: {node_name}")
        if not await self.is_model_running_on_node(node_name, model_name):
            raise ModelNotRunningError(f"Model is not running on controller node '{node_name}': {model_name}")
        return {"kind": "remote", "url": node["url"], "node_name": node_name}

    async def is_model_running_on_node(self, node_name: str, model_name: str) -> bool:
        try:
            statuses = await self.node_registry.request_node(node_name, "GET", "/models")
        except httpx.HTTPError:
            return False
        if not isinstance(statuses, list):
            return False
        for status in statuses:
            if isinstance(status, dict) and status.get("name") == model_name and bool(status.get("running")):
                return True
        return False
