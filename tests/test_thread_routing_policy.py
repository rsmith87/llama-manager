import pytest

from llama_manager.core.config import load_config
from llama_manager.core.threads.routing import RoutingPolicy


@pytest.mark.asyncio
async def test_routing_policy_uses_request_type_priority_order():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {
                    "url": "http://mac",
                    "default_model": "gemma",
                    "request_types": {"coding": {"model": "gemma", "priority": 50}},
                },
                "linux-2080ti": {
                    "url": "http://linux",
                    "default_model": "qwen",
                    "request_types": {"coding": {"model": "qwen", "priority": 10}},
                },
            },
        }
    )
    policy = RoutingPolicy(config, model_running=lambda node, model: node == "linux-2080ti" and model == "qwen")

    decision = await policy.choose(
        request_type="coding",
        requested_model=None,
        explicit_target="auto",
        previous_route=None,
    )

    assert decision.node == "linux-2080ti"
    assert decision.model == "qwen"
    assert decision.strategy == "deterministic"


@pytest.mark.asyncio
async def test_routing_policy_preserves_thread_affinity_when_eligible():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {
                    "url": "http://mac",
                    "request_types": {"coding": {"model": "gemma", "priority": 50}},
                },
                "linux-2080ti": {
                    "url": "http://linux",
                    "request_types": {"coding": {"model": "qwen", "priority": 10}},
                },
            },
        }
    )
    policy = RoutingPolicy(config, model_running=lambda node, model: node == "mac-mini" and model == "gemma")

    decision = await policy.choose(
        request_type="coding",
        requested_model=None,
        explicit_target="auto",
        previous_route={"node": "mac-mini", "model": "gemma"},
    )

    assert decision.node == "mac-mini"
    assert decision.model == "gemma"
    assert decision.reason == "thread_affinity"


@pytest.mark.asyncio
async def test_routing_policy_honors_explicit_node_target():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {"url": "http://mac", "default_model": "gemma"},
                "linux-2080ti": {"url": "http://linux", "default_model": "qwen"},
            },
        }
    )
    policy = RoutingPolicy(config, model_running=lambda node, model: node == "mac-mini" and model == "gemma")

    decision = await policy.choose(
        request_type="general",
        requested_model="gemma",
        explicit_target="node:mac-mini",
        previous_route=None,
    )

    assert decision.node == "mac-mini"
    assert decision.model == "gemma"
    assert decision.strategy == "explicit"


@pytest.mark.asyncio
async def test_routing_policy_rejects_invalid_explicit_target():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {"url": "http://mac", "default_model": "gemma"},
            },
        }
    )
    policy = RoutingPolicy(config, model_running=lambda node, model: True)

    with pytest.raises(ValueError):
        await policy.choose(
            request_type="general",
            requested_model=None,
            explicit_target="mac-mini",
            previous_route=None,
        )


@pytest.mark.asyncio
async def test_routing_policy_supports_async_model_running():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {"url": "http://mac", "default_model": "gemma"},
            },
        }
    )

    async def model_running(node, model):
        return node == "mac-mini" and model == "gemma"

    policy = RoutingPolicy(config, model_running=model_running)

    decision = await policy.choose(
        request_type="general",
        requested_model=None,
        explicit_target="auto",
        previous_route=None,
    )

    assert decision.node == "mac-mini"
    assert decision.model == "gemma"


@pytest.mark.asyncio
async def test_routing_policy_falls_back_to_first_sorted_running_node():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "z-linux": {"url": "http://z", "default_model": "qwen"},
                "a-mac": {"url": "http://a", "default_model": "gemma"},
                "m-workstation": {"url": "http://m", "default_model": "mistral"},
            },
        }
    )
    policy = RoutingPolicy(config, model_running=lambda node, model: node == "m-workstation" and model == "mistral")

    decision = await policy.choose(
        request_type="coding",
        requested_model=None,
        explicit_target="",
        previous_route=None,
    )

    assert decision.node == "m-workstation"
    assert decision.model == "mistral"
    assert decision.reason == "fallback"


@pytest.mark.asyncio
async def test_routing_policy_raises_when_no_eligible_running_model():
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {"url": "http://mac", "default_model": "gemma"},
                "linux-2080ti": {"url": "http://linux", "default_model": "qwen"},
            },
        }
    )
    policy = RoutingPolicy(config, model_running=lambda node, model: False)

    with pytest.raises(ValueError):
        await policy.choose(
            request_type="general",
            requested_model=None,
            explicit_target="auto",
            previous_route=None,
        )
