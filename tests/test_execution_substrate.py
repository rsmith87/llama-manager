import asyncio
import json

import pytest

from llama_manager.core.nodes.worker import AgentWorker
from llama_manager.core.config import load_config
from llama_manager.main import create_app
from tests.helpers import authenticated_client as TestClient
from tests.persistence_db_setup import prepare_all_persistence_dbs

WORKER_HEADERS = {"X-Llama-Manager-Key": "node-secret"}


def worker_nodes(*names):
    return {
        name: {"url": f"http://{name}.example:9000", "api_key": "node-secret"}
        for name in names
    }


def _create_controller_app(tmp_path, nodes):
    prepare_all_persistence_dbs(tmp_path)
    return create_app(config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": nodes}))


def test_llm_generate_job_validates_required_payload(tmp_path):
    app = _create_controller_app(tmp_path, {})
    client = TestClient(app)

    missing_model = client.post(
        "/jobs",
        json={"type": "llm.generate", "payload": {"messages": [{"role": "user", "content": "hi"}]}},
    )
    assert missing_model.status_code == 422

    valid = client.post(
        "/jobs",
        json={
            "type": "llm.generate",
            "payload": {
                "model": "qwen",
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.2,
            },
        },
    )
    assert valid.status_code == 201
    assert valid.json()["type"] == "llm.generate"


def test_cancel_running_job_records_cancel_requested(tmp_path):
    app = _create_controller_app(tmp_path, worker_nodes("win"))
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "task", "payload": {"x": 1}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    client.post(
        f"/nodes/win/work/{claim[0]['attempt_id']}/progress",
        json={"progress": {"stage": "start"}},
        headers=WORKER_HEADERS,
    )

    canceled = client.post(f"/jobs/{job['id']}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "cancel_requested"
    assert canceled.json()["cancellation_requested"] is True

    events = client.get(f"/jobs/{job['id']}/events").json()
    assert any(event["event_type"] == "cancel_requested" for event in events)


def test_job_events_stream_replays_events_and_closes_on_terminal_state(tmp_path):
    app = _create_controller_app(tmp_path, worker_nodes("win"))
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "task", "payload": {"x": 1}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    client.post(
        f"/nodes/win/work/{claim[0]['attempt_id']}/complete",
        json={"result": {"ok": True}},
        headers=WORKER_HEADERS,
    )

    with client.stream("GET", f"/jobs/{job['id']}/events/stream") as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: job_created" in body
    assert "event: job_completed" in body


@pytest.mark.asyncio
async def test_agent_worker_completes_llm_generate_job():
    calls = []

    async def request(method, url, payload=None, headers=None):
        calls.append((method, url, payload))
        if url.endswith("/nodes/agent-a/work/claim"):
            return [
                {
                    "attempt_id": "attempt-1",
                    "job": {
                        "id": "job-1",
                        "type": "llm.generate",
                        "status": "assigned",
                        "target_selector": "auto",
                        "payload": {
                            "model": "qwen",
                            "messages": [{"role": "user", "content": "hi"}],
                            "target": "local",
                        },
                    },
                }
            ]
        if url.endswith("/jobs/job-1"):
            return {"id": "job-1", "status": "assigned", "cancellation_requested": False}
        if url.endswith("/nodes/agent-a/work/attempt-1/progress"):
            return {"ok": True}
        if url.endswith("/nodes/agent-a/work/attempt-1/complete"):
            return {"id": "job-1", "status": "completed"}
        raise AssertionError(f"unexpected request: {method} {url}")

    async def chat(model, payload):
        assert model == "qwen"
        assert payload["messages"][0]["content"] == "hi"
        return {"choices": [{"message": {"content": "hello"}}]}, {"route": "local"}

    worker = AgentWorker(
        config=load_config(
            {
                "mode": "agent",
                "controller_url": "http://controller",
                "node_name": "agent-a",
                "agent_worker_enabled": True,
            }
        ),
        request=request,
        chat=chat,
    )

    processed = await worker.run_once()

    assert processed == 1
    complete_payload = [call[2] for call in calls if call[1].endswith("/complete")][0]
    assert complete_payload["result"]["response"]["choices"][0]["message"]["content"] == "hello"
    assert complete_payload["result"]["worker_node"] == "agent-a"


@pytest.mark.asyncio
async def test_agent_worker_fails_unsupported_job_type_non_retryable():
    calls = []

    async def request(method, url, payload=None, headers=None):
        calls.append((method, url, payload))
        if url.endswith("/nodes/agent-a/work/claim"):
            return [{"attempt_id": "attempt-1", "job": {"id": "job-1", "type": "other", "payload": {}}}]
        if url.endswith("/nodes/agent-a/work/attempt-1/fail"):
            return {"id": "job-1", "status": "failed"}
        raise AssertionError(f"unexpected request: {method} {url}")

    worker = AgentWorker(
        config=load_config(
            {
                "mode": "agent",
                "controller_url": "http://controller",
                "node_name": "agent-a",
                "agent_worker_enabled": True,
            }
        ),
        request=request,
        chat=None,
    )

    assert await worker.run_once() == 1
    fail_payload = [call[2] for call in calls if call[1].endswith("/fail")][0]
    assert fail_payload["error_code"] == "UNSUPPORTED_JOB_TYPE"
    assert fail_payload["retryable"] is False


def test_agent_worker_config_defaults_disabled():
    config = load_config({"mode": "agent"})

    assert config.agent_worker_enabled is False
    assert config.agent_worker_poll_interval_seconds == 2
    assert config.agent_worker_max_jobs == 1
    assert config.agent_worker_labels == {}
    assert config.agent_worker_capacity == {}
