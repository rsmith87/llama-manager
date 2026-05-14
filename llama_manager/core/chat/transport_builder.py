from __future__ import annotations

from urllib.parse import quote

from llama_manager.core.chat.target_resolver import ModelNotRunningError
from llama_manager.core.nodes.registry import NodeRegistry


class TransportBuilder:
    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry

    def chat_transport_for_target(self, target: dict[str, str], model_name: str, stream: bool) -> tuple[str, dict[str, str], bool, dict[str, str]]:
        if target["kind"] == "local":
            return target["url"], {}, True, {"route": "local"}
        suffix = "/stream" if stream else ""
        return self.node_transport(target["node_name"], f"/chat/{quote(model_name, safe='')}{suffix}")

    def slot_transport_for_target(self, target: dict[str, str], suffix: str) -> tuple[str, dict[str, str], bool, dict[str, str]]:
        if target["kind"] == "local":
            return target["url"].replace("/v1/chat/completions", f"/slots{suffix}"), {}, True, {"route": "local"}
        return self.node_transport(target["node_name"], f"/slots{suffix}")

    def embedding_transport_for_target(self, target: dict[str, str]) -> tuple[str, dict[str, str], bool, dict[str, str]]:
        if target["kind"] == "local":
            return target["url"].replace("/v1/chat/completions", "/v1/embeddings"), {}, True, {"route": "local"}
        return self.node_transport(target["node_name"], "/v1/embeddings")

    def node_transport(self, node_name: str, path: str) -> tuple[str, dict[str, str], bool, dict[str, str]]:
        node = next((item for item in self.node_registry.list_nodes() if item["name"] == node_name), None)
        if node is None:
            raise ModelNotRunningError(f"Unknown controller node: {node_name}")
        node_config = self.node_registry.get_node_config(node_name)
        headers: dict[str, str] = {}
        if node_config.api_key:
            headers["X-Llama-Manager-Key"] = node_config.api_key
        return f"{node['url'].rstrip('/')}/{path.lstrip('/')}", headers, bool(node_config.verify_tls), {"route": f"node:{node_name}"}
