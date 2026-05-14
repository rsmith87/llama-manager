from llama_manager.core.config import NodeConfig, load_config
from llama_manager.core.nodes.registry import NodeRegistry
from llama_manager.storage.db import InMemoryStore


def test_dynamic_nodes_and_heartbeats_persist_via_store():
    config = load_config({"mode": "controller", "nodes": {}})
    store = InMemoryStore()

    registry = NodeRegistry(config=config, store=store)
    registry.register_node("win", NodeConfig(url="http://win-agent:9000", api_key="k", verify_tls=False))

    first_nodes = registry.list_nodes()
    assert first_nodes[0]["name"] == "win"
    assert first_nodes[0]["registration"] == "dynamic"
    assert first_nodes[0]["last_heartbeat"] is not None

    restored = NodeRegistry(config=config, store=store)
    restored_nodes = restored.list_nodes()
    assert restored_nodes[0]["name"] == "win"
    assert restored_nodes[0]["registration"] == "dynamic"
    assert restored_nodes[0]["last_heartbeat"] is not None
