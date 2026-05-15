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


def test_registering_static_node_preserves_static_credentials_and_registration():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "linux": {
                    "url": "http://old-linux:9137",
                    "api_key": "secret",
                    "verify_tls": False,
                }
            },
        }
    )
    registry = NodeRegistry(config=config)

    registry.register_node("linux", NodeConfig(url="http://new-linux:9137"))

    nodes = registry.list_nodes()
    assert nodes[0]["name"] == "linux"
    assert nodes[0]["url"] == "http://new-linux:9137"
    assert nodes[0]["verify_tls"] is False
    assert nodes[0]["registration"] == "static"
    assert registry.get_node_config("linux").api_key == "secret"
    assert registry.get_node_config("linux").verify_tls is False


def test_updates_static_node_runtime_config_without_changing_registration():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {"win": {"url": "http://old-win:9000", "api_key": "old", "verify_tls": True}},
        }
    )
    registry = NodeRegistry(config=config)

    updated = registry.update_node(
        "win",
        NodeConfig(url="http://new-win:9000", api_key="new", verify_tls=False),
    )

    assert updated["name"] == "win"
    assert updated["url"] == "http://new-win:9000"
    assert updated["verify_tls"] is False
    assert updated["registration"] == "static"
    assert registry.get_node_config("win").api_key == "new"
    assert registry.get_node_config("win").verify_tls is False
