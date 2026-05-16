import importlib.util
from pathlib import Path

import pytest

from llama_manager.core.config import load_config


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "linux_agent_smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("linux_agent_smoke", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validate_linux_agent_config_accepts_linux_2080ti_config():
    smoke = load_smoke_module()
    config = load_config(
        {
            "mode": "agent",
            "controller_url": "http://controller:9137",
            "node_name": "linux-2080ti",
            "agent_url": "http://linux:9137",
            "agent_api_key": "agent-key",
            "controller_registration_key_outbound": "join-key",
        }
    )

    smoke.validate_linux_agent_config(config, expected_node="linux-2080ti")


def test_validate_linux_agent_config_reports_actionable_errors():
    smoke = load_smoke_module()
    config = load_config({"mode": "controller", "node_name": "wrong"})

    with pytest.raises(SystemExit) as exc:
        smoke.validate_linux_agent_config(config, expected_node="linux-2080ti")

    message = str(exc.value)
    assert "mode must be 'agent'" in message
    assert "node_name must be 'linux-2080ti'" in message
    assert "controller_url is required" in message


def test_validate_linux_agent_config_rejects_unexpanded_secret_placeholders():
    smoke = load_smoke_module()
    config = load_config(
        {
            "mode": "agent",
            "controller_url": "http://controller:9137",
            "node_name": "linux-2080ti",
            "agent_url": "http://linux:9137",
            "agent_api_key": "${LLAMA_MANAGER_AGENT_API_KEY}",
            "controller_registration_key_outbound": "${JOIN_KEY}",
        }
    )

    with pytest.raises(SystemExit) as exc:
        smoke.validate_linux_agent_config(config, expected_node="linux-2080ti")

    message = str(exc.value)
    assert "agent_api_key has an unresolved environment placeholder" in message
    assert "controller_registration_key_outbound has an unresolved environment placeholder" in message


def test_find_registered_node_requires_fresh_heartbeat_and_matching_url():
    smoke = load_smoke_module()
    nodes = [
        {
            "name": "linux-2080ti",
            "url": "http://linux:9137",
            "heartbeat_fresh": True,
            "last_heartbeat": "2026-05-15T12:00:00+00:00",
        }
    ]

    found = smoke.find_registered_node(nodes, "linux-2080ti", "http://linux:9137")

    assert found["name"] == "linux-2080ti"


def test_find_registered_node_rejects_stale_heartbeat():
    smoke = load_smoke_module()
    nodes = [
        {
            "name": "linux-2080ti",
            "url": "http://linux:9137",
            "heartbeat_fresh": False,
            "last_heartbeat": "2026-05-15T12:00:00+00:00",
        }
    ]

    with pytest.raises(smoke.SmokeCheckError, match="heartbeat is not fresh"):
        smoke.find_registered_node(nodes, "linux-2080ti", "http://linux:9137")
