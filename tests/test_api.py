from pathlib import Path
from fastapi.testclient import TestClient as RawTestClient
import httpx
import pytest
from sqlalchemy import update

import time

from tests.helpers import authenticated_client as TestClient
from llama_manager.core.persistence.audit_store_orm import AuditStoreOrm
from llama_manager.core.persistence.auth_store_orm import AuthStoreOrm
from llama_manager.core.persistence.chat_session_store_orm import ChatSessionStoreOrm
from llama_manager.core.persistence.models.orchestration import JobOrm
from llama_manager.core.orchestration.store_orm import OrchestrationStoreOrm
from tests.persistence_db_setup import prepare_all_persistence_dbs

WORKER_HEADERS = {"X-Llama-Manager-Key": "node-secret"}


def worker_nodes(*names):
    return {
        name: {"url": f"http://{name}.example:9000", "api_key": "node-secret"}
        for name in names
    }


@pytest.fixture(autouse=True)
def _prepare_migrated_persistence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prepare_all_persistence_dbs(tmp_path)
    prepare_all_persistence_dbs(tmp_path / "logs")


def test_controller_background_sweeper_requeues_expired_attempt(tmp_path):
    app = create_app(
        config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("win")})
    )
    app.state.controller_sweeper_interval_seconds = 0.05

    with TestClient(app) as client:
        job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
        claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
        attempt_id = claim[0]["attempt_id"]

        app.state.orchestrator.repo.attempt_progress("win", attempt_id, {"pct": 5}, lease_seconds=-1)

        deadline = time.time() + 2.0
        while time.time() < deadline:
            refreshed = client.get(f"/jobs/{job['id']}").json()
            if refreshed["status"] == "queued":
                break
            time.sleep(0.05)

        assert refreshed["status"] == "queued"

from llama_manager.core.config import load_config
from llama_manager.main import create_app


class StubProcessManager:
    def __init__(self, running=False):
        self.running = running

    def list_statuses(self):
        return [
            {
                "name": "qwen",
                "running": self.running,
                "pid": 123 if self.running else None,
                "port": 8081,
                "model_path": "/models/qwen.gguf",
                "log_path": "/tmp/qwen.log",
            }
        ]

    def start(self, name):
        return {
            "name": name,
            "running": True,
            "pid": 123,
            "port": 8081,
            "model_path": "/models/qwen.gguf",
            "log_path": "/tmp/qwen.log",
        }

    def stop(self, name):
        return {
            "name": name,
            "running": False,
            "pid": None,
            "port": 8081,
            "model_path": "/models/qwen.gguf",
            "log_path": "/tmp/qwen.log",
        }

    def restart(self, name):
        return self.start(name)

    def tail_logs(self, name, lines=200):
        return "hello\n"

    def status(self, name):
        return self.list_statuses()[0]


class StubConversionManager:
    def list_models(self):
        return [
            {
                "name": "hf-qwen",
                "path": "/Volumes/4TB/HFModels/hf-qwen",
                "convertible": True,
                "output_path": "/Volumes/4TB/HFModels/hf-qwen/hf-qwen.gguf",
                "gguf_exists": False,
                "gguf_files": [],
                "converter_path": "/Users/robertsmith/Apps/llama.cpp/convert_hf_to_gguf.py",
                "python_bin": "/Users/robertsmith/Apps/llama.cpp/.venv/bin/python",
                "running": False,
                "pid": None,
                "returncode": None,
                "log_path": "/tmp/hf-qwen.log",
            }
        ]

    def start(self, name):
        return {**self.list_models()[0], "running": True, "pid": 456}

    def status(self, name):
        return self.list_models()[0]

    def tail_logs(self, name, lines=200):
        return "convert log\n"


class StubGgufLibrary:
    def list_files(self):
        return [
            {
                "id": "abc",
                "name": "model",
                "filename": "model.gguf",
                "model_dir": "gemma",
                "path": "/Volumes/4TB/HFModels/gemma/model.gguf",
                "registered": False,
                "registered_as": None,
            }
        ]

    def add_model(
        self,
        file_id,
        name,
        port,
        ctx,
        gpu_layers,
        host,
        reasoning=None,
        reasoning_budget=None,
        prompt_template=None,
    ):
        return {
            "name": name,
            "path": "/Volumes/4TB/HFModels/gemma/model.gguf",
            "port": port,
            "ctx": ctx,
            "gpu_layers": gpu_layers,
            "host": host,
            "reasoning": reasoning,
            "reasoning_budget": reasoning_budget,
            "prompt_template": prompt_template,
        }

    def delete_file(self, file_id):
        return {
            "deleted": True,
            "id": file_id,
            "filename": "model.gguf",
            "path": "/Volumes/4TB/HFModels/gemma/model.gguf",
            "unregistered_models": [],
        }


class StubQuantizationManager:
    def list_files(self):
        return [
            {
                "id": "quant-abc",
                "name": "model",
                "filename": "model.gguf",
                "model_dir": "gemma",
                "path": "/Volumes/4TB/HFModels/gemma/model.gguf",
                "size_bytes": 1024,
                "size_gb": 0.0,
                "type": "Q4_K_M",
                "supported_types": ["Q4_K_M", "Q5_K_M"],
                "output_path": "/Volumes/4TB/HFModels/gemma/model-Q4_K_M.gguf",
                "existing_outputs": [],
                "quantize_bin": "/Users/robertsmith/Apps/llama.cpp/build/bin/llama-quantize",
                "running": False,
                "pid": None,
                "returncode": None,
                "log_path": "/tmp/quant-abc.log",
            }
        ]

    def start(self, file_id, quant_type):
        return {**self.list_files()[0], "id": file_id, "type": quant_type, "running": True, "pid": 789}

    def status(self, file_id):
        return {**self.list_files()[0], "id": file_id}

    def tail_logs(self, file_id, lines=200):
        return "quant log\n"


def test_agent_model_routes():
    config = load_config(
        {
            "mode": "agent",
            "models": {
                "qwen": {
                    "path": "/models/qwen.gguf",
                    "port": 8081,
                }
            },
        }
    )
    app = create_app(
        config=config,
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    health = client.get("/health").json()
    assert health["mode"] == "agent"
    assert "config_source" in health
    assert client.get("/models").json()[0]["name"] == "qwen"
    assert client.post("/models/qwen/start").json()["running"] is True
    assert client.post("/models/qwen/stop").json()["running"] is False
    assert client.get("/logs/qwen").json()["text"] == "hello\n"


def test_controller_lists_nodes_and_proxies_model_start():
    config = load_config(
        {
            "mode": "controller",
            "node_heartbeat_timeout_seconds": 999999,
            "nodes": {"win": {"url": "http://win-agent:9000"}},
        }
    )

    async def fake_request(method, url, api_key, verify_tls):
        assert method == "POST"
        assert url == "http://win-agent:9000/models/qwen/start"
        assert api_key is None
        assert verify_tls is True
        return {"running": True, "name": "qwen"}

    app = create_app(config=config, controller_request=fake_request)
    client = TestClient(app)

    nodes = client.get("/nodes").json()
    assert nodes[0]["name"] == "win"
    assert nodes[0]["url"] == "http://win-agent:9000"
    assert "controller_config_source" in nodes[0]
    response = client.post("/nodes/win/models/qwen/start")
    assert response.status_code == 200
    assert response.json()["running"] is True


def test_controller_updates_node_and_routes_to_new_url():
    config = load_config(
        {
            "mode": "controller",
            "node_heartbeat_timeout_seconds": 999999,
            "nodes": {"win": {"url": "http://old-win:9000", "api_key": "old-key"}},
        }
    )
    seen = []

    async def fake_request(method, url, api_key, verify_tls):
        seen.append((method, url, api_key, verify_tls))
        return {"running": True, "name": "qwen"}

    app = create_app(config=config, controller_request=fake_request)
    client = TestClient(app)

    response = client.put(
        "/nodes/win",
        json={"url": "http://new-win:9000", "api_key": "new-key", "verify_tls": False},
    )

    assert response.status_code == 200
    assert response.json()["url"] == "http://new-win:9000"
    assert response.json()["verify_tls"] is False
    assert response.json()["registration"] == "static"
    assert client.get("/nodes").json()[0]["url"] == "http://new-win:9000"

    proxy = client.post("/nodes/win/models/qwen/start")
    assert proxy.status_code == 200
    assert seen == [("POST", "http://new-win:9000/models/qwen/start", "new-key", False)]


def test_controller_aggregates_models_from_nodes():
    config = load_config(
        {
            "mode": "controller",
            "node_heartbeat_timeout_seconds": 999999,
            "nodes": {
                "mac": {"url": "http://mac-agent:9000"},
                "win": {"url": "http://win-agent:9000"},
            },
        }
    )

    async def fake_request(method, url, api_key, verify_tls):
        if url == "http://mac-agent:9000/models":
            return [{"name": "small", "running": True}]
        if url == "http://win-agent:9000/models":
            return [{"name": "coder", "running": False}]
        if url == "http://mac-agent:9000/health":
            return {"config_source": "C:/mac-agent-config.yaml"}
        if url == "http://win-agent:9000/health":
            return {"config_source": "D:/win-agent-config.yaml"}
        raise AssertionError(url)

    app = create_app(config=config, controller_request=fake_request)
    client = TestClient(app)

    response = client.get("/nodes/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "mac"
    assert payload[0]["reachable"] is True
    assert payload[0]["agent_config_source"] == "C:/mac-agent-config.yaml"
    assert payload[0]["models_source"] == "unknown"
    assert payload[1]["name"] == "win"
    assert payload[1]["reachable"] is True
    assert payload[1]["agent_config_source"] == "D:/win-agent-config.yaml"


def test_agent_api_key_enforcement():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "agent_api_key": "secret",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = RawTestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/models").status_code == 401
    assert client.get("/models", headers={"X-Llama-Manager-Key": "secret"}).status_code == 200


def test_controller_can_register_node_and_track_heartbeat():
    app = create_app(
        config=load_config(
            {"mode": "controller", "controller_registration_key": "join-key", "nodes": {}}
        )
    )
    client = TestClient(app)

    response = client.post(
        "/nodes/register",
        json={
            "name": "win",
            "url": "http://win-agent:9000",
            "registration_key": "join-key",
        },
    )
    assert response.status_code == 200
    nodes = client.get("/nodes").json()
    assert nodes[0]["name"] == "win"
    assert nodes[0]["registration"] == "dynamic"
    assert nodes[0]["last_heartbeat"] is not None

    beat = client.post("/nodes/win/heartbeat")
    assert beat.status_code == 200


def test_in_memory_controller_config_does_not_write_node_state_to_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(
        config=load_config(
            {"mode": "controller", "controller_registration_key": "join-key", "nodes": {}}
        )
    )
    client = TestClient(app)

    response = client.post(
        "/nodes/register",
        json={
            "name": "win",
            "url": "http://win-agent:9000",
            "registration_key": "join-key",
        },
    )

    assert response.status_code == 200
    assert not (tmp_path / "logs" / "controller_nodes_state.json").exists()


def test_nodes_status_marks_stale_heartbeat_offline():
    app = create_app(
        config=load_config(
            {"mode": "controller", "node_heartbeat_timeout_seconds": -1, "nodes": {}}
        )
    )
    client = TestClient(app)
    client.post(
        "/nodes/register",
        json={"name": "win", "url": "http://win-agent:9000"},
    )
    status = client.get("/nodes/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload[0]["reachable"] is False
    assert payload[0]["error"] == "stale heartbeat"


def test_nodes_models_marks_stale_heartbeat_offline():
    app = create_app(
        config=load_config(
            {"mode": "controller", "node_heartbeat_timeout_seconds": -1, "nodes": {}}
        )
    )
    client = TestClient(app)
    client.post(
        "/nodes/register",
        json={"name": "win", "url": "http://win-agent:9000"},
    )
    response = client.get("/nodes/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["reachable"] is False
    assert payload[0]["error"] == "stale heartbeat"
    assert payload[0]["models"] == []
    assert payload[0]["agent_config_source"] is None
    assert payload[0]["models_source"] == "unknown"


def test_nodes_status_reports_upstream_http_error_classification():
    config = load_config(
        {
            "mode": "controller",
            "node_heartbeat_timeout_seconds": 999999,
            "nodes": {"win": {"url": "http://win-agent:9000"}},
        }
    )

    async def fake_request(method, url, api_key, verify_tls):
        req = httpx.Request(method, url)
        resp = httpx.Response(503, request=req, text="agent unavailable")
        raise httpx.HTTPStatusError("upstream failure", request=req, response=resp)

    app = create_app(config=config, controller_request=fake_request)
    client = TestClient(app)
    response = client.get("/nodes/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["reachable"] is False
    assert payload[0]["error"] == "upstream http 503: agent unavailable"


def test_nodes_models_reports_upstream_transport_error_classification():
    config = load_config(
        {
            "mode": "controller",
            "node_heartbeat_timeout_seconds": 999999,
            "nodes": {"win": {"url": "http://win-agent:9000"}},
        }
    )

    async def fake_request(method, url, api_key, verify_tls):
        raise httpx.ConnectError("connection refused")

    app = create_app(config=config, controller_request=fake_request)
    client = TestClient(app)
    response = client.get("/nodes/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["reachable"] is False
    assert payload[0]["error"].startswith("upstream transport error:")
    assert payload[0]["models"] == []
    assert payload[0]["agent_config_source"] is None
    assert payload[0]["models_source"] == "unknown"


def test_ui_index_is_served():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Llama Manager" in response.text


def test_conversion_routes():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    assert client.get("/conversions/models").json()[0]["name"] == "hf-qwen"
    assert client.post("/conversions/hf-qwen/start").json()["running"] is True
    assert client.get("/conversions/hf-qwen").json()["output_path"].endswith("hf-qwen.gguf")
    assert client.get("/conversions/hf-qwen/logs").json()["text"] == "convert log\n"


def test_quantization_routes():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        quantization_manager=StubQuantizationManager(),
    )
    client = TestClient(app)

    assert client.get("/quantizations/files").json()[0]["id"] == "quant-abc"
    assert client.post("/quantizations/quant-abc/start", json={"type": "Q5_K_M"}).json()["running"] is True
    assert client.get("/quantizations/quant-abc").json()["output_path"].endswith("model-Q4_K_M.gguf")
    assert client.get("/quantizations/quant-abc/logs").json()["text"] == "quant log\n"


def test_download_log_stream_route_replays_existing_log(tmp_path, monkeypatch):
    from llama_manager.api.routes import downloads as download_routes

    log_path = tmp_path / "logs" / "downloads" / "hf-qwen.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("first\nsecond\n", encoding="utf-8")
    streamed = {}

    async def fake_stream_log_file(path, lines=200):
        streamed["path"] = path
        streamed["lines"] = lines
        yield 'event: chunk\ndata: {"text":"second\\n"}\n\n'

    monkeypatch.setattr(download_routes, "stream_log_file", fake_stream_log_file)
    app = create_app(
        config=load_config({"mode": "agent", "log_dir": str(tmp_path / "logs")}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    record = app.state.model_download_store.create_download(
        repo_id="Qwen/Qwen2.5",
        revision=None,
        local_path=str(tmp_path / "models" / "Qwen__Qwen2.5"),
        command="hf download Qwen/Qwen2.5",
        log_path=str(log_path),
        triggered_by="test",
    )
    client = TestClient(app)

    with client.stream("GET", f"/downloads/{record['id']}/logs/stream?lines=1") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        first_event = response.read().decode()

    assert streamed == {"path": log_path, "lines": 1}
    assert 'event: chunk\ndata: {"text":"second\\n"}\n\n' in first_event


def test_download_remote_quants_route(tmp_path):
    app = create_app(
        config=load_config({"mode": "agent", "log_dir": str(tmp_path / "logs")}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    app.state.download_manager.list_remote_quants = lambda repo_id, revision=None: [
        {"filename": "model-Q4_K_M.gguf", "path": "model-Q4_K_M.gguf", "size_bytes": 1024, "quant": "Q4_K_M"}
    ]
    client = TestClient(app)

    response = client.get("/downloads/quants?repo_id=owner/model&revision=main")

    assert response.status_code == 200
    assert response.json() == [
        {"filename": "model-Q4_K_M.gguf", "path": "model-Q4_K_M.gguf", "size_bytes": 1024, "quant": "Q4_K_M"}
    ]


def test_chat_route_requires_running_model():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=False),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    response = client.post("/chat/qwen", json={"messages": [{"role": "user", "content": "hi"}]})

    assert response.status_code == 409


def test_chat_route_proxies_to_llama_server():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {
            "choices": [
                {"message": {"role": "assistant", "content": "hello"}}
            ]
        }

    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.2,
            "max_tokens": 64,
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"
    assert calls == [
        (
            "http://127.0.0.1:8081/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.2,
                "max_tokens": 64,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
    ]


def test_chat_stream_route_proxies_stream_to_llama_server():
    calls = []

    async def fake_chat_stream_request(url, payload):
        calls.append((url, payload))
        yield b"data: {\"choices\":[{\"delta\":{\"content\":\"hel\"}}]}\n\n"
        yield b"data: {\"choices\":[{\"delta\":{\"content\":\"lo\"}}]}\n\n"
        yield b"data: [DONE]\n\n"

    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_stream_request=fake_chat_stream_request,
    )
    client = TestClient(app)

    with client.stream(
        "POST",
        "/chat/qwen/stream",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.2,
            "max_tokens": 64,
            "reasoning": True,
        },
    ) as response:
        body = response.read()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert body == (
        b"data: {\"choices\":[{\"delta\":{\"content\":\"hel\"}}]}\n\n"
        b"data: {\"choices\":[{\"delta\":{\"content\":\"lo\"}}]}\n\n"
        b"data: [DONE]\n\n"
    )
    assert calls == [
        (
            "http://127.0.0.1:8081/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.2,
                "max_tokens": 64,
                "stream": True,
                "chat_template_kwargs": {"enable_thinking": True},
            },
        )
    ]


def test_chat_route_applies_model_prompt_template():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}

    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081, "prompt_template": "chatml"}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post("/chat/qwen", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    assert calls[0][1]["chat_template"] == "chatml"


def test_chat_sessions_crud_routes(tmp_path):
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "log_dir": str(tmp_path),
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    listed = client.get("/chat/sessions")
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/chat/sessions",
        json={
            "name": "smoke-run",
            "model": "qwen",
            "target": "auto",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
            "request_defaults": {
                "temperature": 0.4,
                "max_tokens": 128,
                "structured_mode": "json_schema",
                "json_schema_text": "{\"type\":\"object\"}",
                "grammar_text": "",
            },
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["name"] == "smoke-run"
    assert payload["model"] == "qwen"
    assert payload["target_selector"] == "auto"
    assert len(payload["messages"]) == 2
    session_id = payload["id"]

    listed_after = client.get("/chat/sessions")
    assert listed_after.status_code == 200
    entries = listed_after.json()
    assert len(entries) == 1
    assert entries[0]["id"] == session_id
    assert entries[0]["name"] == "smoke-run"

    loaded = client.get(f"/chat/sessions/{session_id}")
    assert loaded.status_code == 200
    loaded_payload = loaded.json()
    assert loaded_payload["id"] == session_id
    assert loaded_payload["request_defaults"]["max_tokens"] == 128
    assert loaded_payload["request_defaults"]["structured_mode"] == "json_schema"
    assert loaded_payload["request_defaults"]["json_schema_text"] == "{\"type\":\"object\"}"
    assert loaded_payload["messages"][0]["content"] == "hello"

    deleted = client.delete(f"/chat/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/chat/sessions/{session_id}")
    assert missing.status_code == 404


def test_chat_sessions_post_overwrites_existing_when_id_is_provided(tmp_path):
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "log_dir": str(tmp_path),
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    created = client.post(
        "/chat/sessions",
        json={
            "name": "Obliterated-session-5-12-2026",
            "model": "qwen",
            "target": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "request_defaults": {"temperature": 0.4},
        },
    )
    assert created.status_code == 200
    session_id = created.json()["id"]

    updated = client.post(
        "/chat/sessions",
        json={
            "id": session_id,
            "name": "Obliterated-session-5-12-2026",
            "model": "qwen",
            "target": "node-a",
            "messages": [{"role": "user", "content": "hello again"}],
            "request_defaults": {"temperature": 0.1},
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["id"] == session_id
    assert updated_payload["target_selector"] == "node-a"
    assert updated_payload["messages"] == [{"role": "user", "content": "hello again"}]
    assert updated_payload["request_defaults"] == {"temperature": 0.1}

    listed = client.get("/chat/sessions")
    assert listed.status_code == 200
    entries = listed.json()
    assert len(entries) == 1
    assert entries[0]["id"] == session_id


def test_chat_sessions_post_creates_new_row_when_id_is_omitted(tmp_path):
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "log_dir": str(tmp_path),
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    first = client.post(
        "/chat/sessions",
        json={
            "name": "Obliterated-session-5-12-2026",
            "model": "qwen",
            "target": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "request_defaults": {"temperature": 0.4},
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/chat/sessions",
        json={
            "name": "Obliterated-session-5-12-2026",
            "model": "qwen",
            "target": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "request_defaults": {"temperature": 0.4},
        },
    )
    assert second.status_code == 200
    assert second.json()["id"] != first.json()["id"]

    listed = client.get("/chat/sessions")
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_chat_sessions_missing_returns_404(tmp_path):
    app = create_app(
        config=load_config({"mode": "agent", "log_dir": str(tmp_path)}),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    response = client.delete("/chat/sessions/does-not-exist")
    assert response.status_code == 404


def test_chat_embeddings_route_proxies_to_llama_server():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {
            "object": "list",
            "model": "qwen",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2], "id": "emb-0"}],
            "usage": {"prompt_tokens": 3, "total_tokens": 3},
        }

    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post("/chat/qwen/embeddings", json={"input": ["hello", "world"], "target": "auto"})
    assert response.status_code == 200
    assert response.json()["data"][0]["object"] == "embedding"
    assert calls == [
        (
            "http://127.0.0.1:8081/v1/embeddings",
            {"input": ["hello", "world"], "model": "qwen"},
        )
    ]


def test_chat_embeddings_route_validation_error():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    response = client.post("/chat/qwen/embeddings", json={"target": "auto"})
    assert response.status_code == 422


def test_controller_chat_route_proxies_to_node_chat_route():
    controller_calls = []
    chat_calls = []

    async def fake_controller_request(method, url, api_key, verify_tls):
        controller_calls.append((method, url, api_key, verify_tls))
        if url == "http://win-agent:9000/models":
            return [{"name": "qwen", "running": True}]
        raise AssertionError(url)

    async def fake_chat_request(url, payload):
        chat_calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}

    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        controller_request=fake_controller_request,
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"
    assert controller_calls == [("GET", "http://win-agent:9000/models", None, True)]
    assert chat_calls == [
        (
            "http://win-agent:9000/chat/qwen",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
                "max_tokens": 512,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
    ]


def test_controller_chat_stream_route_proxies_to_node_chat_stream_route():
    controller_calls = []
    chat_calls = []

    async def fake_controller_request(method, url, api_key, verify_tls):
        controller_calls.append((method, url, api_key, verify_tls))
        if url == "http://win-agent:9000/models":
            return [{"name": "qwen", "running": True}]
        raise AssertionError(url)

    async def fake_chat_stream_request(url, payload):
        chat_calls.append((url, payload))
        yield b"data: {\"choices\":[{\"delta\":{\"content\":\"ok\"}}]}\n\n"
        yield b"data: [DONE]\n\n"

    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        controller_request=fake_controller_request,
        chat_stream_request=fake_chat_stream_request,
    )
    client = TestClient(app)

    with client.stream(
        "POST",
        "/chat/qwen/stream",
        json={"messages": [{"role": "user", "content": "hi"}], "reasoning": True},
    ) as response:
        body = response.read()

    assert response.status_code == 200
    assert body == b"data: {\"choices\":[{\"delta\":{\"content\":\"ok\"}}]}\n\ndata: [DONE]\n\n"
    assert controller_calls == [("GET", "http://win-agent:9000/models", None, True)]
    assert chat_calls == [
        (
            "http://win-agent:9000/chat/qwen/stream",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
                "max_tokens": 512,
                "stream": True,
                "chat_template_kwargs": {"enable_thinking": True},
            },
        )
    ]


def test_controller_chat_route_uses_local_running_model_when_available():
    controller_calls = []
    chat_calls = []

    async def fake_controller_request(method, url, api_key, verify_tls):
        controller_calls.append((method, url, api_key, verify_tls))
        if url == "http://win-agent:9000/models":
            return [{"name": "qwen", "running": True}]
        raise AssertionError(url)

    async def fake_chat_request(url, payload):
        chat_calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "local"}}]}

    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8089}},
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        controller_request=fake_controller_request,
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "local"
    assert controller_calls == []
    assert chat_calls == [
        (
            "http://127.0.0.1:8081/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
                "max_tokens": 512,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
    ]


def test_chat_route_supports_advanced_sampling_and_n_predict_alias():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "n_predict": 77,
            "top_p": 0.95,
            "top_k": 50,
            "min_p": 0.05,
            "repeat_penalty": 1.15,
            "seed": 123,
            "stop": ["</s>", "User:"],
        },
    )
    assert response.status_code == 200
    forwarded = calls[0][1]
    assert forwarded["max_tokens"] == 77
    assert forwarded["top_p"] == 0.95
    assert forwarded["top_k"] == 50
    assert forwarded["min_p"] == 0.05
    assert forwarded["repeat_penalty"] == 1.15
    assert forwarded["seed"] == 123
    assert forwarded["stop"] == ["</s>", "User:"]


def test_chat_route_supports_structured_output_json_schema_and_grammar():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response_schema = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "json_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        },
    )
    assert response_schema.status_code == 200
    assert calls[-1][1]["json_schema"]["type"] == "object"
    assert "grammar" not in calls[-1][1]

    response_grammar = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "grammar": "root ::= \"yes\" | \"no\"",
        },
    )
    assert response_grammar.status_code == 200
    assert calls[-1][1]["grammar"] == "root ::= \"yes\" | \"no\""
    assert "json_schema" not in calls[-1][1]


def test_chat_route_supports_multimodal_message_content_blocks():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe this"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,AAAA"},
                        },
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    forwarded = calls[0][1]["messages"][0]["content"]
    assert isinstance(forwarded, list)
    assert forwarded[0]["type"] == "text"
    assert forwarded[1]["type"] == "image_url"


def test_chat_route_rejects_invalid_advanced_sampling_values():
    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}], "top_p": 1.5},
    )
    assert response.status_code == 422
    response_structured = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "json_schema": {"type": "object"},
            "grammar": "root ::= \"yes\"",
        },
    )
    assert response_structured.status_code == 422


def test_chat_route_normalizes_stop_string_to_list():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)
    response = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stop": "</s>, User: ,",
        },
    )
    assert response.status_code == 200
    assert calls[0][1]["stop"] == ["</s>", "User:"]


def test_chat_route_normalizes_stop_list_and_drops_empty_entries():
    calls = []

    async def fake_chat_request(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
        chat_request=fake_chat_request,
    )
    client = TestClient(app)
    response = client.post(
        "/chat/qwen",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stop": ["</s>", "", "   ", "User:"],
        },
    )
    assert response.status_code == 200
    assert calls[0][1]["stop"] == ["</s>", "User:"]


def test_chat_capabilities_route():
    app = create_app(
        config=load_config(
            {"mode": "agent", "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}}}
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    response = client.get("/chat/capabilities/qwen")
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "qwen"
    assert payload["supports"]["sampling"]["top_p"] is True
    assert payload["supports"]["structured_output"]["json_schema"] is False
    assert payload["supports"]["structured_output"]["grammar"] is False
    assert payload["supports"]["structured_output_source"]["json_schema"] == "default"
    assert payload["supports"]["structured_output_source"]["grammar"] == "default"


def test_chat_capabilities_reports_vision_support_from_model_config():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {
                    "gemma-4-e2b-it": {
                        "path": "/models/gemma.gguf",
                        "port": 8081,
                        "vision": True,
                        "mmproj": "/models/mmproj.gguf",
                    }
                },
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)
    response = client.get("/chat/capabilities/gemma-4-e2b-it")
    assert response.status_code == 200
    assert response.json()["supports"]["vision"] is True


def test_chat_capabilities_reports_structured_output_support_from_config():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {
                    "qwen": {
                        "path": "/models/qwen.gguf",
                        "port": 8081,
                        "supports_json_schema": True,
                        "supports_grammar": False,
                    }
                },
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)
    payload = client.get("/chat/capabilities/qwen").json()
    assert payload["supports"]["structured_output"]["json_schema"] is True
    assert payload["supports"]["structured_output"]["grammar"] is False
    assert payload["supports"]["structured_output_source"]["json_schema"] == "config_flag"
    assert payload["supports"]["structured_output_source"]["grammar"] == "config_flag"


def test_chat_capabilities_inferrs_structured_output_support_from_extra_args():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {
                    "qwen": {
                        "path": "/models/qwen.gguf",
                        "port": 8081,
                        "extra_args": ["--grammar-file", "/tmp/g.gbnf", "--json-schema"],
                    }
                },
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)
    payload = client.get("/chat/capabilities/qwen").json()
    assert payload["supports"]["structured_output"]["json_schema"] is True
    assert payload["supports"]["structured_output"]["grammar"] is True
    assert payload["supports"]["structured_output_source"]["json_schema"] == "extra_args"
    assert payload["supports"]["structured_output_source"]["grammar"] == "extra_args"


def test_controller_chat_route_falls_back_to_remote_when_local_not_running():
    controller_calls = []
    chat_calls = []

    async def fake_controller_request(method, url, api_key, verify_tls):
        controller_calls.append((method, url, api_key, verify_tls))
        if url == "http://win-agent:9000/models":
            return [{"name": "qwen", "running": True}]
        raise AssertionError(url)

    async def fake_chat_request(url, payload):
        chat_calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "remote"}}]}

    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8089}},
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        process_manager=StubProcessManager(running=False),
        controller_request=fake_controller_request,
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "remote"
    assert controller_calls == [("GET", "http://win-agent:9000/models", None, True)]
    assert chat_calls == [
        (
            "http://win-agent:9000/chat/qwen",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
                "max_tokens": 512,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
    ]


def test_controller_chat_route_can_force_local_target():
    controller_calls = []
    chat_calls = []

    async def fake_controller_request(method, url, api_key, verify_tls):
        controller_calls.append((method, url, api_key, verify_tls))
        return [{"name": "qwen", "running": True}]

    async def fake_chat_request(url, payload):
        chat_calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "local"}}]}

    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8089}},
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        controller_request=fake_controller_request,
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}], "target": "local"},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "local"
    assert controller_calls == []
    assert chat_calls[0][0] == "http://127.0.0.1:8081/v1/chat/completions"


def test_controller_chat_route_can_force_named_node_target():
    controller_calls = []
    chat_calls = []

    async def fake_controller_request(method, url, api_key, verify_tls):
        controller_calls.append((method, url, api_key, verify_tls))
        if url == "http://win-agent:9000/models":
            return [{"name": "qwen", "running": True}]
        raise AssertionError(url)

    async def fake_chat_request(url, payload):
        chat_calls.append((url, payload))
        return {"choices": [{"message": {"role": "assistant", "content": "remote"}}]}

    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8089}},
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        process_manager=StubProcessManager(running=False),
        controller_request=fake_controller_request,
        chat_request=fake_chat_request,
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}], "target": "node:win"},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "remote"
    assert controller_calls == [("GET", "http://win-agent:9000/models", None, True)]
    assert chat_calls[0][0] == "http://win-agent:9000/chat/qwen"


def test_controller_chat_route_rejects_unknown_target_selector():
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "nodes": {"win": {"url": "http://win-agent:9000"}},
            }
        ),
        process_manager=StubProcessManager(running=False),
    )
    client = TestClient(app)

    response = client.post(
        "/chat/qwen",
        json={"messages": [{"role": "user", "content": "hi"}], "target": "node:missing"},
    )
    assert response.status_code == 409
    assert "Unknown controller node: missing" in response.json()["detail"]

def test_gguf_library_routes():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    assert client.get("/library/ggufs").json()[0]["filename"] == "model.gguf"
    response = client.post(
        "/library/ggufs/abc/add-model",
        json={
            "name": "gemma-local",
            "port": 8088,
            "ctx": 8192,
            "gpu_layers": 999,
            "host": "0.0.0.0",
            "reasoning": "auto",
            "reasoning_budget": 2048,
            "prompt_template": "gemma",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "gemma-local"
    assert response.json()["reasoning"] == "auto"
    assert response.json()["reasoning_budget"] == 2048
    assert response.json()["prompt_template"] == "gemma"

    deleted = client.delete("/library/ggufs/abc")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["filename"] == "model.gguf"


def test_model_favorite_toggle_sorts_models_first(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
mode: agent
log_dir: {log_dir}
models:
  qwen:
    path: /models/qwen.gguf
    port: 8081
  gemma:
    path: /models/gemma.gguf
    port: 8082
""".format(log_dir=tmp_path / "logs"),
        encoding="utf-8",
    )
    app = create_app(config=load_config(config_path))
    client = TestClient(app)

    favorited = client.post("/models/gemma/favorite", json={"favorite": True})
    assert favorited.status_code == 200
    assert favorited.json()["favorite"] is True

    models = client.get("/models").json()
    assert [model["name"] for model in models] == ["gemma", "qwen"]
    assert models[0]["favorite"] is True

    reloaded = load_config(config_path)
    assert reloaded.models["gemma"].favorite is True


def test_library_remove_model_hides_it_from_models():
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        )
    )
    client = TestClient(app)

    initial_models = client.get("/models").json()
    assert any(item["name"] == "qwen" for item in initial_models)

    removed = client.delete("/library/models/qwen")
    assert removed.status_code == 200
    assert removed.json()["removed"] is True
    assert removed.json()["name"] == "qwen"

    remaining = client.get("/models").json()
    assert all(item["name"] != "qwen" for item in remaining)


def test_library_remove_model_returns_404_for_unknown():
    app = create_app(
        config=load_config({"mode": "agent"})
    )
    client = TestClient(app)

    response = client.delete("/library/models/not-a-model")
    assert response.status_code == 404


def test_controller_job_lifecycle_and_events(tmp_path):
    app = create_app(
        config=load_config({
            "mode": "controller",
            "log_dir": str(tmp_path),
            "nodes": {}
        })
    )
    client = TestClient(app)

    create = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}})
    assert create.status_code == 201


def test_controller_job_failure_and_retry(tmp_path):
    app = create_app(
        config=load_config({
            "mode": "controller",
            "log_dir": str(tmp_path),
            "nodes": worker_nodes("win")
        })
    )
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    attempt_id = claim[0]["attempt_id"]

    fail = client.post(
        f"/nodes/win/work/{attempt_id}/fail",
        json={"error_code": "E_TMP", "retryable": True},
        headers=WORKER_HEADERS,
    )
    assert fail.status_code == 200
    assert fail.json()["status"] == "queued"

    claim2 = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    assert len(claim2) == 1

    events = client.get(f"/jobs/{job['id']}/events").json()
    assert any(e["event_type"] == "retry_scheduled" for e in events)


def test_sweeper_requeues_expired_attempt(tmp_path):
    app = create_app(
        config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("win")})
    )
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    attempt_id = claim[0]["attempt_id"]

    orch = app.state.orchestrator
    orch.repo.attempt_progress("win", attempt_id, {"pct": 10}, lease_seconds=-1)
    sweep = orch.sweep_expired_leases()
    assert sweep["expired"] >= 1
    assert sweep["requeued"] >= 1

    refreshed = client.get(f"/jobs/{job['id']}").json()
    assert refreshed["status"] == "queued"


def test_sweeper_times_out_after_max_attempts(tmp_path):
    app = create_app(
        config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("win")})
    )
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
    orch = app.state.orchestrator

    for _ in range(3):
        claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
        attempt_id = claim[0]["attempt_id"]
        orch.repo.attempt_progress("win", attempt_id, {"pct": 10}, lease_seconds=-1)
        orch.sweep_expired_leases()

    refreshed = client.get(f"/jobs/{job['id']}").json()
    assert refreshed["status"] == "timed_out"


def test_sweeper_prunes_old_terminal_jobs(tmp_path):
    app = create_app(
        config=load_config({
            "mode": "controller",
            "log_dir": str(tmp_path),
            "nodes": worker_nodes("win"),
            "controller_retention_days": 0,
        })
    )
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    attempt_id = claim[0]["attempt_id"]
    client.post(f"/nodes/win/work/{attempt_id}/complete", json={"result": {"ok": True}}, headers=WORKER_HEADERS)

    app.state.orchestrator.sweep_expired_leases()

    gone = client.get(f"/jobs/{job['id']}")
    assert gone.status_code == 404


def test_controller_stats_endpoint_reports_sweep_and_counts(tmp_path):
    app = create_app(
        config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": {}})
    )
    client = TestClient(app)

    client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}})
    app.state.orchestrator.sweep_expired_leases()

    response = client.get("/controller/stats")
    assert response.status_code == 200
    payload = response.json()
    assert "job_counts" in payload
    assert "last_sweep" in payload
    assert payload["retention_days"] == 30


def test_node_work_requires_node_api_key_when_configured(tmp_path):
    app = create_app(
        config=load_config({
            "mode": "controller",
            "log_dir": str(tmp_path),
            "nodes": {"win": {"url": "http://win-agent:9000", "api_key": "node-secret"}},
        })
    )
    client = TestClient(app)

    client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}})
    unauthorized = client.post("/nodes/win/work/claim", json={"max_jobs": 1})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/nodes/win/work/claim",
        json={"max_jobs": 1},
        headers={"X-Llama-Manager-Key": "node-secret"},
    )
    assert authorized.status_code == 200


def test_node_work_rejects_unknown_node(tmp_path):
    app = create_app(
        config=load_config({
            "mode": "controller",
            "log_dir": str(tmp_path),
            "nodes": worker_nodes("win"),
        })
    )
    client = TestClient(app)

    client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}})
    response = client.post(
        "/nodes/evil/work/claim",
        json={"max_jobs": 1},
        headers=WORKER_HEADERS,
    )

    assert response.status_code == 404


def test_node_work_rejects_registered_node_without_api_key(tmp_path):
    app = create_app(
        config=load_config({
            "mode": "controller",
            "log_dir": str(tmp_path),
            "nodes": {"win": {"url": "http://win-agent:9000"}},
        })
    )
    client = TestClient(app)

    client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}})
    response = client.post(
        "/nodes/win/work/claim",
        json={"max_jobs": 1},
        headers=WORKER_HEADERS,
    )

    assert response.status_code == 401


def test_job_complete_persists_artifacts_and_lists_them(tmp_path):
    app = create_app(
        config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("win")})
    )
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    attempt_id = claim[0]["attempt_id"]

    complete = client.post(
        f"/nodes/win/work/{attempt_id}/complete",
        json={
            "result": {"text": "done"},
            "artifacts": [
                {"kind": "log", "uri": "s3://bucket/run.log", "meta": {"bytes": 123}},
                {"kind": "trace", "uri": "file:///tmp/trace.json"},
            ],
        },
        headers=WORKER_HEADERS,
    )
    assert complete.status_code == 200
    payload = complete.json()
    assert payload["status"] == "completed"
    assert len(payload["artifacts"]) == 2

    listed = client.get(f"/jobs/{job['id']}/artifacts")
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_claim_matches_node_labels_and_capacity(tmp_path):
    app = create_app(config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("win", "linux-a100")}))
    client = TestClient(app)

    client.post(
        "/jobs",
        json={
            "type": "task",
            "payload": {
                "requirements": {
                    "labels": {"platform": "linux"},
                    "capacity": {"vram_gb": 16},
                }
            },
        },
    )

    miss = client.post(
        "/nodes/win/work/claim",
        json={"max_jobs": 1, "labels": {"platform": "windows"}, "capacity": {"vram_gb": 24}},
        headers=WORKER_HEADERS,
    )
    assert miss.status_code == 200
    assert miss.json() == []

    hit = client.post(
        "/nodes/linux-a100/work/claim",
        json={"max_jobs": 1, "labels": {"platform": "linux"}, "capacity": {"vram_gb": 24}},
        headers=WORKER_HEADERS,
    )
    assert hit.status_code == 200
    assert len(hit.json()) == 1


def test_claim_respects_node_target_selector(tmp_path):
    app = create_app(config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("gpu-1", "gpu-2")}))
    client = TestClient(app)

    client.post(
        "/jobs",
        json={"type": "task", "payload": {"x": 1}, "target": "node:gpu-1"},
    )

    other = client.post("/nodes/gpu-2/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS)
    assert other.status_code == 200
    assert other.json() == []

    right = client.post("/nodes/gpu-1/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS)
    assert right.status_code == 200
    assert len(right.json()) == 1


def test_retention_policy_endpoint(tmp_path):
    app = create_app(config=load_config({
        "mode": "controller",
        "log_dir": str(tmp_path),
        "controller_retention_days": 14,
        "controller_archive_retention_days": 60,
        "nodes": {},
    }))
    client = TestClient(app)
    response = client.get("/controller/retention-policy")
    assert response.status_code == 200
    payload = response.json()
    assert payload["retention_days"] == 14
    assert payload["archive_retention_days"] == 60


def test_archive_export_writes_jsonl(tmp_path):
    app = create_app(config=load_config({"mode": "controller", "log_dir": str(tmp_path), "nodes": worker_nodes("win")}))
    client = TestClient(app)

    job = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}}).json()
    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS).json()
    attempt_id = claim[0]["attempt_id"]
    client.post(f"/nodes/win/work/{attempt_id}/complete", json={"result": {"ok": True}}, headers=WORKER_HEADERS)

    # make job old enough for retention_days=0 archive cutoff
    with app.state.orchestrator.repo.store.tx() as session:
        session.execute(
            update(JobOrm)
            .where(JobOrm.id == job["id"])
            .values(completed_at="2000-01-01T00:00:00+00:00")
        )

    export = client.post("/controller/archive/export?retention_days=0")
    assert export.status_code == 200
    data = export.json()
    assert data["jobs_exported"] >= 1
    archive_path = Path(data["archive_path"])
    assert archive_path.exists()
    text = archive_path.read_text(encoding="utf-8")
    assert "\"job\"" in text
    assert "\"events\"" in text


def test_auth_login_rejects_dev_fallback_without_bootstrap_key():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)

    login = client.post("/auth/login", json={"username": "alice", "api_key": "dev"})
    assert login.status_code == 401


def test_auth_login_me_logout_flow_with_bootstrapped_admin_key():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)
    created = app.state.auth_store.create_key("alice", "admin")

    login = client.post("/auth/login", json={"username": "alice", "api_key": created["key"]})
    assert login.status_code == 200
    token = login.json()["token"]
    assert login.json()["role"] == "admin"

    me = client.get("/auth/me", headers={"X-UI-Session": token})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["role"] == "admin"

    logout = client.post("/auth/logout", headers={"X-UI-Session": token})
    assert logout.status_code == 200
    assert logout.json()["ok"] is True

    me_after = client.get("/auth/me", headers={"X-UI-Session": token})
    assert me_after.status_code == 401


def test_sensitive_routes_fail_closed_until_auth_is_bootstrapped():
    app = create_app(
        config=load_config({"mode": "controller", "nodes": {}}),
    )
    client = RawTestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/models").status_code == 401
    assert client.get("/nodes").status_code == 401

    created = app.state.auth_store.create_key("admin", "admin")
    assert client.get("/models", headers={"X-Llama-Manager-Key": created["key"]}).status_code == 200


def test_heartbeat_route_bypasses_ui_session_auth_on_controller():
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "nodes": {
                    "linux-2080ti": {
                        "url": "http://127.0.0.1:9137",
                        "verify_tls": False,
                    }
                },
            }
        ),
    )
    client = RawTestClient(app)

    # Bootstrapping auth currently enables UI-session checks for most routes.
    # Heartbeats from remote agents should still be accepted.
    created = app.state.auth_store.create_key("admin", "admin")
    heartbeat = client.post("/nodes/linux-2080ti/heartbeat")
    assert heartbeat.status_code == 200

    nodes = client.get("/nodes", headers={"X-Llama-Manager-Key": created["key"]})
    assert nodes.status_code == 200
    payload = nodes.json()
    assert payload[0]["name"] == "linux-2080ti"
    assert payload[0]["heartbeat_fresh"] is True


def test_auth_key_management_forbidden_for_non_admin_session():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)
    app.state.ui_sessions["viewer-token"] = {
        "username": "viewer-user",
        "created_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "role": "viewer",
    }

    list_resp = client.get("/auth/keys", headers={"X-UI-Session": "viewer-token"})
    assert list_resp.status_code == 403

    create_resp = client.post(
        "/auth/keys",
        json={"username": "bob", "role": "operator"},
        headers={"X-UI-Session": "viewer-token"},
    )
    assert create_resp.status_code == 403

    revoke_resp = client.post(
        "/auth/keys/some-key/revoke",
        headers={"X-UI-Session": "viewer-token"},
    )
    assert revoke_resp.status_code == 403


def test_auth_key_management_admin_crud():
    app = create_app(
        config=load_config({"mode": "agent"}),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    client = TestClient(app)
    app.state.ui_sessions["admin-token"] = {
        "username": "admin-user",
        "created_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "role": "admin",
    }

    created = client.post(
        "/auth/keys",
        json={"username": "service-account", "role": "operator"},
        headers={"X-UI-Session": "admin-token"},
    )
    assert created.status_code == 200
    key_payload = created.json()
    key_id = key_payload["id"]
    assert key_payload["username"] == "service-account"
    assert key_payload["role"] == "operator"
    assert isinstance(key_payload.get("key"), str) and key_payload["key"]

    listed = client.get("/auth/keys", headers={"X-UI-Session": "admin-token"})
    assert listed.status_code == 200
    assert any(item["id"] == key_id for item in listed.json())

    revoked = client.post(f"/auth/keys/{key_id}/revoke", headers={"X-UI-Session": "admin-token"})
    assert revoked.status_code == 200
    assert revoked.json()["ok"] is True


def test_auth_store_defaults_to_orm_store(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "log_dir": str(tmp_path),
            }
        ),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    assert isinstance(app.state.auth_store, AuthStoreOrm)

    client = TestClient(app)
    created = app.state.auth_store.create_key("alice", "admin")
    login = client.post("/auth/login", json={"username": "alice", "api_key": created["key"]})
    assert login.status_code == 200
    assert login.json()["role"] == "admin"


def test_create_app_fails_when_migrations_not_applied(tmp_path):
    unmigrated_log_dir = tmp_path / "unmigrated"
    with pytest.raises(RuntimeError) as exc:
        create_app(
            config=load_config(
                {
                    "mode": "agent",
                    "log_dir": str(unmigrated_log_dir),
                }
            ),
            process_manager=StubProcessManager(),
            conversion_manager=StubConversionManager(),
            gguf_library=StubGgufLibrary(),
        )

    message = str(exc.value)
    assert "alembic -x db=chat_sessions upgrade chat_sessions@head" in message


def test_module_fallback_app_reports_startup_error_at_root(monkeypatch):
    import llama_manager.main as main_module

    def _raise_startup_error():
        raise RuntimeError("schema missing")

    monkeypatch.setattr(main_module, "create_app", _raise_startup_error)
    app = main_module._create_module_app()
    client = RawTestClient(app)

    response = client.get("/")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "detail": "schema missing"}


def test_audit_store_defaults_to_orm_store(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "log_dir": str(tmp_path),
            }
        ),
        process_manager=StubProcessManager(),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    assert isinstance(app.state.audit_store, AuditStoreOrm)

    client = TestClient(app)
    created = client.post(
        "/audit/events",
        json={
            "actor": "alice",
            "event_type": "auth_login",
            "dry_run": False,
            "target": "alice",
            "route": "auth",
            "payload": {"ok": True},
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["event_type"] == "auth_login"

    listed = client.get("/audit/events?event_type=auth")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())


def test_chat_sessions_store_defaults_to_orm_store(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "agent",
                "log_dir": str(tmp_path),
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )
    assert isinstance(app.state.chat_session_store, ChatSessionStoreOrm)

    client = TestClient(app)
    created = client.post(
        "/chat/sessions",
        json={
            "name": "orm-chat",
            "model": "qwen",
            "target": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "request_defaults": {"temperature": 0.2},
        },
    )
    assert created.status_code == 200
    session_id = created.json()["id"]

    listed = client.get("/chat/sessions")
    assert listed.status_code == 200
    assert any(item["id"] == session_id for item in listed.json())


def test_orchestration_store_defaults_to_orm_store(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "log_dir": str(tmp_path),
                "nodes": worker_nodes("win"),
            }
        )
    )
    assert isinstance(app.state.orchestrator.repo.store, OrchestrationStoreOrm)

    client = TestClient(app)
    created = client.post("/jobs", json={"type": "chat", "payload": {"prompt": "hi"}})
    assert created.status_code == 201
    job = created.json()

    claim = client.post("/nodes/win/work/claim", json={"max_jobs": 1}, headers=WORKER_HEADERS)
    assert claim.status_code == 200
    claim_payload = claim.json()
    assert len(claim_payload) == 1
    assert claim_payload[0]["job"]["id"] == job["id"]


def test_all_persistence_domains_use_orm_together(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "log_dir": str(tmp_path),
                "nodes": worker_nodes("win"),
                "models": {"qwen": {"path": "/models/qwen.gguf", "port": 8081}},
            }
        ),
        process_manager=StubProcessManager(running=True),
        conversion_manager=StubConversionManager(),
        gguf_library=StubGgufLibrary(),
    )

    assert isinstance(app.state.auth_store, AuthStoreOrm)
    assert isinstance(app.state.audit_store, AuditStoreOrm)
    assert isinstance(app.state.chat_session_store, ChatSessionStoreOrm)
    assert isinstance(app.state.orchestrator.repo.store, OrchestrationStoreOrm)

    client = TestClient(app)

    # auth path (store API)
    created_key = app.state.auth_store.create_key("alice", "admin")
    assert app.state.auth_store.resolve_key(created_key["key"]) is not None

    # audit path (HTTP)
    audit_resp = client.post(
        "/audit/events",
        json={
            "actor": "alice",
            "event_type": "toggle_smoke",
            "dry_run": False,
            "target": "all",
            "route": "test",
            "payload": {"ok": True},
        },
        headers={"X-Llama-Manager-Key": created_key["key"]},
    )
    assert audit_resp.status_code == 200

    # chat sessions path (HTTP)
    session_resp = client.post(
        "/chat/sessions",
        json={
            "name": "all-orm",
            "model": "qwen",
            "target": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "request_defaults": {"temperature": 0.2},
        },
        headers={"X-Llama-Manager-Key": created_key["key"]},
    )
    assert session_resp.status_code == 200

    # orchestration path (HTTP)
    job_resp = client.post(
        "/jobs",
        json={"type": "chat", "payload": {"prompt": "hi"}},
        headers={"X-Llama-Manager-Key": created_key["key"]},
    )
    assert job_resp.status_code == 201
