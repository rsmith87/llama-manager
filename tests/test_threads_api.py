import pytest
from fastapi.testclient import TestClient as FastAPITestClient

from llama_manager.core.config import load_config
from llama_manager.core.threads.service import ThreadService
from llama_manager.core.threads.store import ThreadStore
from llama_manager.main import create_app
from tests.helpers import authenticated_client as TestClient
from tests.persistence_db_setup import prepare_all_persistence_dbs


class FakeChatProxy:
    async def chat_with_meta(self, model_name, payload):
        assert model_name == "qwen"
        assert payload["target"] == "node:linux-2080ti"
        return {"choices": [{"message": {"content": "hello"}}]}, {"route": "node:linux-2080ti"}


class RecordingChatProxy:
    def __init__(self, responses=None, error=None):
        self.calls = []
        self.responses = list(responses or ["hello"])
        self.error = error

    async def chat_with_meta(self, model_name, payload):
        self.calls.append({"model_name": model_name, "payload": payload})
        if self.error is not None:
            raise self.error
        content = self.responses.pop(0)
        return {"choices": [{"message": {"content": content}}]}, {"route": payload["target"]}


def _config():
    return load_config(
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


def _metadata_routing_config():
    return load_config(
        {
            "mode": "controller",
            "nodes": {
                "mac-mini": {
                    "url": "http://mac",
                    "default_model": "gemma",
                    "request_types": {"general": {"model": "gemma", "priority": 10}},
                },
                "linux-2080ti": {
                    "url": "http://linux",
                    "default_model": "qwen",
                    "request_types": {"coding": {"model": "qwen", "priority": 10}},
                },
            },
        }
    )


def _service(tmp_path, chat_proxy=None, model_running=None):
    return ThreadService(
        config=_config(),
        store=ThreadStore(tmp_path / "threads.db"),
        chat_proxy=chat_proxy or RecordingChatProxy(),
        model_running=model_running or (lambda node, model: True),
    )


def _thread(service):
    return service.create_thread(
        title="Test",
        default_model=None,
        metadata={"app": "codex", "purpose": "coding", "priority": "medium", "request_type": "coding"},
        created_by="alice",
    )


def _general_thread(service):
    return service.create_thread(
        title="General",
        default_model=None,
        metadata={"app": "codex", "purpose": "chat", "priority": "low", "request_type": "general"},
        created_by="alice",
    )


def test_thread_service_routes_message_and_records_public_events(tmp_path):
    config = load_config(
        {
            "mode": "controller",
            "nodes": {
                "linux-2080ti": {
                    "url": "http://linux",
                    "default_model": "qwen",
                    "request_types": {"coding": {"model": "qwen", "priority": 10}},
                }
            },
        }
    )
    service = ThreadService(
        config=config,
        store=ThreadStore(tmp_path / "threads.db"),
        chat_proxy=FakeChatProxy(),
        model_running=lambda node, model: True,
    )
    thread = service.create_thread(
        title="Test",
        default_model=None,
        metadata={"app": "codex", "purpose": "coding", "priority": "medium", "request_type": "coding"},
        created_by="alice",
    )

    response = service.post_message(
        thread_id=thread["id"],
        role="user",
        content="Say hello",
        model=None,
        target="auto",
        metadata=None,
    )

    assert response["message"]["content"] == "hello"
    assert response["route"]["node"] == "linux-2080ti"
    public_events = service.list_events(thread["id"], include_internal=False)
    assert [event["event_type"] for event in public_events] == ["user_message", "assistant_message"]
    internal_events = service.list_events(thread["id"], include_internal=True)
    assert "routing_decision" in [event["event_type"] for event in internal_events]


@pytest.mark.asyncio
async def test_post_message_async_sends_prior_public_messages_plus_current_user_message(tmp_path):
    chat_proxy = RecordingChatProxy(responses=["first reply", "second reply"])
    service = _service(tmp_path, chat_proxy=chat_proxy)
    thread = _thread(service)

    await service.post_message_async(
        thread_id=thread["id"],
        role="user",
        content="First question",
        model=None,
        target="auto",
        metadata=None,
    )
    await service.post_message_async(
        thread_id=thread["id"],
        role="user",
        content="Second question",
        model=None,
        target="auto",
        metadata=None,
    )

    assert chat_proxy.calls[1]["payload"]["messages"] == [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "first reply"},
        {"role": "user", "content": "Second question"},
    ]


@pytest.mark.asyncio
async def test_post_message_async_uses_thread_affinity_on_second_turn_when_previous_route_is_eligible(tmp_path):
    chat_proxy = RecordingChatProxy(responses=["first reply", "second reply"])
    service = _service(
        tmp_path,
        chat_proxy=chat_proxy,
        model_running=lambda node, model: node == "linux-2080ti" and model == "qwen",
    )
    thread = _thread(service)

    await service.post_message_async(thread["id"], "user", "First", None, "auto", None)
    response = await service.post_message_async(thread["id"], "user", "Second", None, "auto", None)

    assert response["route"]["node"] == "linux-2080ti"
    assert response["route"]["reason"] == "thread_affinity"


def test_thread_service_persists_route_metadata_on_assistant_events(tmp_path):
    service = _service(tmp_path, chat_proxy=RecordingChatProxy())
    thread = _thread(service)

    response = service.post_message(thread["id"], "user", "Route me", None, "auto", None)

    assistant_events = [
        event
        for event in service.list_events(thread["id"], include_internal=True)
        if event["event_type"] == "assistant_message"
    ]
    assert assistant_events[0]["route"] == response["route"]
    assert assistant_events[0]["agent_node"] == "linux-2080ti"
    assert assistant_events[0]["model"] == "qwen"


@pytest.mark.asyncio
async def test_post_message_async_merges_message_metadata_and_uses_request_type_override_for_routing(tmp_path):
    chat_proxy = RecordingChatProxy()
    service = ThreadService(
        config=_metadata_routing_config(),
        store=ThreadStore(tmp_path / "threads.db"),
        chat_proxy=chat_proxy,
        model_running=lambda node, model: True,
    )
    thread = _general_thread(service)

    response = await service.post_message_async(
        thread_id=thread["id"],
        role="user",
        content="Write code",
        model=None,
        target="auto",
        metadata={"purpose": "implementation", "request_type": "coding"},
    )

    public_events = service.list_events(thread["id"], include_internal=False)
    assert public_events[0]["content"]["metadata"] == {
        "app": "codex",
        "purpose": "implementation",
        "priority": "low",
        "request_type": "coding",
    }
    assert response["route"]["node"] == "linux-2080ti"
    assert response["route"]["model"] == "qwen"
    assert chat_proxy.calls[0]["model_name"] == "qwen"
    assert chat_proxy.calls[0]["payload"]["target"] == "node:linux-2080ti"


@pytest.mark.asyncio
async def test_post_message_async_appends_public_error_event_when_routing_fails(tmp_path):
    service = _service(tmp_path, model_running=lambda node, model: False)
    thread = _thread(service)

    with pytest.raises(ValueError):
        await service.post_message_async(thread["id"], "user", "No route", None, "auto", None)

    public_events = service.list_events(thread["id"], include_internal=False)
    assert [event["event_type"] for event in public_events] == ["user_message", "error"]
    assert public_events[-1]["error_code"] == "ROUTING_ERROR"
    assert "No eligible running model found" in public_events[-1]["error_detail"]


@pytest.mark.asyncio
async def test_post_message_async_appends_public_error_event_when_chat_proxy_fails(tmp_path):
    service = _service(tmp_path, chat_proxy=RecordingChatProxy(error=RuntimeError("proxy down")))
    thread = _thread(service)

    with pytest.raises(RuntimeError):
        await service.post_message_async(thread["id"], "user", "Hello", None, "auto", None)

    public_events = service.list_events(thread["id"], include_internal=False)
    assert [event["event_type"] for event in public_events] == ["user_message", "error"]
    assert public_events[-1]["error_code"] == "CHAT_PROXY_ERROR"
    assert public_events[-1]["error_detail"] == "proxy down"


def test_threads_api_creates_thread_and_posts_message(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "log_dir": str(tmp_path),
                "nodes": {
                    "linux-2080ti": {
                        "url": "http://linux",
                        "default_model": "qwen",
                        "request_types": {"coding": {"model": "qwen", "priority": 10}},
                    }
                },
            }
        )
    )

    async def fake_chat(model_name, payload):
        return {"choices": [{"message": {"content": "hello from linux"}}]}, {"route": "node:linux-2080ti"}

    app.state.chat_proxy.chat_with_meta = fake_chat
    app.state.thread_service.routing_policy.model_running = lambda node, model: True
    client = TestClient(app)

    thread_response = client.post(
        "/threads",
        json={
            "title": "Debug",
            "metadata": {"app": "codex", "purpose": "coding", "priority": "medium", "request_type": "coding"},
        },
    )
    assert thread_response.status_code == 201
    thread_id = thread_response.json()["id"]

    message_response = client.post(
        f"/threads/{thread_id}/messages",
        json={"role": "user", "content": "hello"},
    )

    assert message_response.status_code == 200
    assert message_response.json()["message"]["content"] == "hello from linux"
    assert message_response.json()["route"]["node"] == "linux-2080ti"

    public_events = client.get(f"/threads/{thread_id}/events").json()
    assert [event["event_type"] for event in public_events] == ["user_message", "assistant_message"]


def test_threads_api_returns_404_for_unknown_thread_events(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "log_dir": str(tmp_path),
                "nodes": {
                    "linux-2080ti": {
                        "url": "http://linux",
                        "default_model": "qwen",
                    }
                },
            }
        )
    )
    client = TestClient(app)

    response = client.get("/threads/not-a-thread/events")

    assert response.status_code == 404


def test_threads_api_internal_events_require_admin_role(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    app = create_app(
        config=load_config(
            {
                "mode": "controller",
                "log_dir": str(tmp_path),
                "nodes": {},
            }
        )
    )
    admin_key = app.state.auth_store.create_key("admin", "admin")["key"]
    viewer_key = app.state.auth_store.create_key("viewer", "viewer")["key"]
    admin = FastAPITestClient(app)
    admin.headers.update({"X-Llama-Manager-Key": admin_key})
    viewer = FastAPITestClient(app)
    viewer.headers.update({"X-Llama-Manager-Key": viewer_key})

    thread = admin.post("/threads", json={"title": "x"}).json()
    public_response = viewer.get(f"/threads/{thread['id']}/events")
    internal_response = viewer.get(f"/threads/{thread['id']}/events?include_internal=true")
    admin_internal_response = admin.get(f"/threads/{thread['id']}/events?include_internal=true")

    assert public_response.status_code == 200
    assert internal_response.status_code == 403
    assert admin_internal_response.status_code == 200
