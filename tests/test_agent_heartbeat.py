import asyncio

import pytest

from llama_manager.core.nodes.heartbeat import AgentHeartbeatClient
from llama_manager.core.config import load_config


@pytest.mark.asyncio
async def test_agent_heartbeat_registers_and_beats():
    calls = []

    async def fake_request(method, url, payload):
        calls.append((method, url, payload))
        return {"ok": True}

    config = load_config(
        {
            "mode": "agent",
            "controller_url": "http://controller:9100",
            "node_name": "win-1",
            "agent_url": "http://10.0.0.2:9000",
            "heartbeat_interval_seconds": 1,
            "controller_registration_key_outbound": "join-key",
        }
    )
    client = AgentHeartbeatClient(config, request=fake_request)
    await client.start()
    await asyncio.sleep(1.2)
    await client.stop()

    assert calls[0][0] == "POST"
    assert calls[0][1] == "http://controller:9100/nodes/register"
    assert calls[0][2]["name"] == "win-1"
    assert calls[0][2]["url"] == "http://127.0.0.1:9000" or calls[0][2]["url"] == "http://10.0.0.2:9000"
    assert any(url.endswith("/nodes/win-1/heartbeat") for _, url, _ in calls[1:])


@pytest.mark.asyncio
async def test_agent_heartbeat_disabled_without_controller_info():
    calls = []

    async def fake_request(method, url, payload):
        calls.append((method, url, payload))
        return {"ok": True}

    config = load_config({"mode": "agent"})
    client = AgentHeartbeatClient(config, request=fake_request)
    await client.start()
    await asyncio.sleep(0.1)
    await client.stop()

    assert calls == []


@pytest.mark.asyncio
async def test_agent_heartbeat_loop_survives_failed_heartbeat_send():
    calls = []

    async def flaky_request(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/heartbeat"):
            raise RuntimeError("temporary failure")
        return {"ok": True}

    config = load_config(
        {
            "mode": "agent",
            "controller_url": "http://controller:9100",
            "node_name": "linux-1",
            "agent_url": "http://10.0.0.3:9000",
            "heartbeat_interval_seconds": 1,
            "controller_registration_key_outbound": "join-key",
        }
    )
    client = AgentHeartbeatClient(config, request=flaky_request)
    await client.start()
    await asyncio.sleep(0.2)

    assert client._task is not None
    assert not client._task.done()
    assert any(url.endswith("/nodes/linux-1/heartbeat") for _, url, _ in calls)

    await client.stop()


@pytest.mark.asyncio
async def test_agent_heartbeat_loop_starts_after_failed_registration():
    calls = []

    async def flaky_request(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/nodes/register"):
            raise RuntimeError("registration failed")
        return {"ok": True}

    config = load_config(
        {
            "mode": "agent",
            "controller_url": "http://controller:9100",
            "node_name": "linux-1",
            "agent_url": "http://10.0.0.3:9000",
            "heartbeat_interval_seconds": 1,
            "controller_registration_key_outbound": "join-key",
        }
    )
    client = AgentHeartbeatClient(config, request=flaky_request)
    await client.start()
    await asyncio.sleep(0.2)

    assert client._task is not None
    assert not client._task.done()
    assert any(url.endswith("/nodes/linux-1/heartbeat") for _, url, _ in calls)

    await client.stop()
