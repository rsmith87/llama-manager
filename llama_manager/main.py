from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from datetime import UTC, datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from llama_manager.api.routes import (
    audit,
    auth,
    chat,
    conversions,
    downloads,
    health,
    jobs,
    library,
    models,
    node_work,
    nodes,
    quantizations,
    settings,
    threads,
    transfers,
    ui,
)
from llama_manager.core.config import AppConfig, load_config
from llama_manager.core.chat.proxy import ChatProxy
from llama_manager.core.nodes.heartbeat import AgentHeartbeatClient
from llama_manager.core.model_assets.conversions import ConversionManager
from llama_manager.core.model_assets.library import GgufLibrary
from llama_manager.core.model_assets.downloads import DownloadManager
from llama_manager.core.model_assets.transfers import TransferManager
from llama_manager.core.nodes.registry import NodeRegistry
from llama_manager.core.runtime.process_manager import ProcessManager
from llama_manager.core.model_assets.quantizations import QuantizationManager
from llama_manager.core.orchestration.store_orm import OrchestrationStoreOrm
from llama_manager.core.orchestration.repo import OrchestrationRepo
from llama_manager.core.orchestration.orchestrator import Orchestrator
from llama_manager.core.threads.service import ThreadService
from llama_manager.core.threads.store import ThreadStore
from llama_manager.core.nodes.worker import AgentWorker
from llama_manager.storage.db import InMemoryStore, JsonFileStore
from llama_manager.core.persistence.chat_session_store_orm import ChatSessionStoreOrm
from llama_manager.core.persistence.audit_store_orm import AuditStoreOrm
from llama_manager.core.persistence.auth_store_orm import AuthStoreOrm
from llama_manager.core.persistence.db_infra import resolve_persistence_urls
from llama_manager.core.persistence.model_download_store_orm import ModelDownloadStoreOrm
from llama_manager.core.app.auth_policy import (
    is_viewer_forbidden,
    should_bypass_middleware,
    should_enforce_agent_key,
    should_validate_ui_session,
)


async def _controller_sweeper_loop(app: FastAPI, interval_seconds: int = 15) -> None:
    stop_event: asyncio.Event = app.state.controller_sweeper_stop_event
    while not stop_event.is_set():
        orchestrator = app.state.orchestrator
        if orchestrator is not None and orchestrator.try_acquire_leader_lease():
            orchestrator.sweep_expired_leases()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


def _build_orchestrator(config: AppConfig) -> Orchestrator | None:
    if config.mode != "controller":
        return None
    db_path = config.log_dir / "controller_state.db"
    orchestration_store = OrchestrationStoreOrm(db_path=db_path, db_url=config.controller_db_url)
    orchestration_repo = OrchestrationRepo(orchestration_store)
    return Orchestrator(
        orchestration_repo,
        retention_days=config.controller_retention_days,
        archive_retention_days=config.controller_archive_retention_days,
        controller_instance_id=config.controller_instance_id,
        leader_lease_seconds=config.controller_leader_lease_seconds,
    )


async def _thread_model_running(registry: NodeRegistry, node: str, model: str) -> bool:
    try:
        models = await registry.request_node(node, "GET", "/models")
    except Exception:
        return False
    if not isinstance(models, list):
        return False
    return any(item.get("name") == model and item.get("running") is True for item in models if isinstance(item, dict))


def _configure_app_state(
    app: FastAPI,
    app_config: AppConfig,
    process_manager: ProcessManager | None,
    conversion_manager: ConversionManager | None,
    quantization_manager: QuantizationManager | None,
    gguf_library: GgufLibrary | None,
    controller_request: Callable[[str, str, str | None, bool, dict[str, Any] | None], Awaitable[dict[str, Any]]] | None,
    chat_request: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None,
    chat_stream_request: Callable[[str, dict[str, Any]], AsyncIterator[bytes]] | None,
    heartbeat_request: Callable[[str, str, dict[str, Any] | None], Awaitable[dict[str, Any]]] | None,
) -> None:
    app.state.config = app_config
    app.state.process_manager = process_manager or ProcessManager(app_config)
    app.state.conversion_manager = conversion_manager or ConversionManager(app_config)
    app.state.quantization_manager = quantization_manager or QuantizationManager(app_config)
    app.state.gguf_library = gguf_library or GgufLibrary(app_config)
    app.state.transfer_manager = TransferManager(app_config)
    persistent_config = app_config.config_source not in {"(defaults)", "(in-memory)"}
    store = (
        JsonFileStore(app_config.log_dir / "controller_nodes_state.json")
        if app_config.mode == "controller" and persistent_config
        else InMemoryStore()
        if app_config.mode == "controller"
        else None
    )
    app.state.node_registry = NodeRegistry(app_config, request=controller_request, store=store)
    app.state.orchestrator = _build_orchestrator(app_config)
    app.state.chat_proxy = ChatProxy(
        app.state.process_manager,
        app_config,
        app.state.node_registry,
        request=chat_request,
        stream_request=chat_stream_request,
    )
    app.state.thread_service = ThreadService(
        config=app_config,
        store=ThreadStore(app_config.log_dir / "threads.db"),
        chat_proxy=app.state.chat_proxy,
        model_running=lambda node, model: _thread_model_running(app.state.node_registry, node, model),
    )
    auth_urls = resolve_persistence_urls(app_config)
    app.state.chat_session_store = ChatSessionStoreOrm(db_url=auth_urls.chat_sessions)
    app.state.model_download_store = ModelDownloadStoreOrm(db_url=auth_urls.chat_sessions)
    app.state.download_manager = DownloadManager(app_config, app.state.model_download_store)
    app.state.audit_store = AuditStoreOrm(db_url=auth_urls.audit)
    app.state.auth_store = AuthStoreOrm(db_url=auth_urls.auth)
    app.state.heartbeat_client = AgentHeartbeatClient(app_config, request=heartbeat_request)
    app.state.agent_worker = AgentWorker(
        app_config,
        chat=app.state.chat_proxy.chat_with_meta,
    )
    app.state.controller_sweeper_task = None
    app.state.controller_sweeper_stop_event = asyncio.Event()
    app.state.controller_sweeper_interval_seconds = 15
    app.state.ui_sessions = {}


def _register_routers(app: FastAPI, app_config: AppConfig) -> None:
    app.include_router(ui.router)
    app.mount("/ui", ui.static_app, name="ui")
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(chat.router)
    app.include_router(conversions.router)
    app.include_router(downloads.router)
    app.include_router(quantizations.router)
    app.include_router(settings.router)
    app.include_router(library.router)
    app.include_router(transfers.router)
    app.include_router(nodes.router)
    app.include_router(audit.router)
    app.include_router(auth.router)
    if app_config.mode == "controller":
        app.include_router(threads.router)
        app.include_router(jobs.router)
        app.include_router(node_work.router)


def _register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def enforce_agent_api_key(request: Request, call_next):
        path = request.url.path
        method = request.method
        if should_bypass_middleware(path, method):
            return await call_next(request)

        configured = app.state.config.agent_api_key
        auth_store = app.state.auth_store
        provided_key = request.headers.get("X-Llama-Manager-Key") or ""
        resolved_key = auth_store.resolve_key(provided_key) if provided_key else None
        configured_key_ok = bool(configured and provided_key and secrets.compare_digest(provided_key, configured))

        if resolved_key is not None:
            request.state.ui_user = resolved_key.get("username", "api-key")
            request.state.ui_role = resolved_key.get("role", "operator")
            if is_viewer_forbidden(path, request.state.ui_role):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
            return await call_next(request)

        if configured_key_ok:
            request.state.ui_user = "agent-api-key"
            request.state.ui_role = "admin"
            return await call_next(request)

        auth_enabled = bool(configured or auth_store.has_active_keys())
        if should_validate_ui_session(auth_enabled, method):
            token = request.headers.get("X-UI-Session")
            session = app.state.ui_sessions.get(token or "")
            if not session:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            expires_at = session.get("expires_at")
            if expires_at and datetime.now(UTC) > datetime.fromisoformat(expires_at):
                app.state.ui_sessions.pop(token, None)
                return JSONResponse(status_code=401, content={"detail": "Session expired"})
            request.state.ui_user = session["username"]
            request.state.ui_role = session.get("role", "operator")
            if is_viewer_forbidden(path, request.state.ui_role):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
            return await call_next(request)

        if not auth_enabled:
            return JSONResponse(status_code=401, content={"detail": "Auth bootstrap required"})
        if not should_enforce_agent_key(app.state.config.mode, configured, path):
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})


def _register_lifespan(app: FastAPI) -> None:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await app.state.heartbeat_client.start()
        await app.state.agent_worker.start()
        if app.state.config.mode == "controller" and app.state.orchestrator is not None:
            app.state.controller_sweeper_stop_event.clear()
            app.state.controller_sweeper_task = asyncio.create_task(
                _controller_sweeper_loop(
                    app, interval_seconds=app.state.controller_sweeper_interval_seconds
                )
            )
        try:
            yield
        finally:
            sweeper_task = app.state.controller_sweeper_task
            if sweeper_task is not None:
                app.state.controller_sweeper_stop_event.set()
                await sweeper_task
                app.state.controller_sweeper_task = None
            await app.state.agent_worker.stop()
            await app.state.heartbeat_client.stop()

    app.router.lifespan_context = lifespan


def create_app(
    config: AppConfig | None = None,
    process_manager: ProcessManager | None = None,
    conversion_manager: ConversionManager | None = None,
    quantization_manager: QuantizationManager | None = None,
    gguf_library: GgufLibrary | None = None,
    controller_request: Callable[[str, str, str | None, bool, dict[str, Any] | None], Awaitable[dict[str, Any]]] | None = None,
    chat_request: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    chat_stream_request: Callable[[str, dict[str, Any]], AsyncIterator[bytes]] | None = None,
    heartbeat_request: Callable[[str, str, dict[str, Any] | None], Awaitable[dict[str, Any]]] | None = None,
) -> FastAPI:
    app_config = config or load_config()
    app = FastAPI(title="Llama Manager", version="0.1.0")
    _configure_app_state(
        app,
        app_config,
        process_manager,
        conversion_manager,
        quantization_manager,
        gguf_library,
        controller_request,
        chat_request,
        chat_stream_request,
        heartbeat_request,
    )
    _register_routers(app, app_config)
    _register_middleware(app)
    _register_lifespan(app)
    return app


def _create_module_app() -> FastAPI:
    try:
        return create_app()
    except RuntimeError as exc:
        app = FastAPI(title="Llama Manager", version="0.1.0")
        message = str(exc)

        def _startup_error_response() -> JSONResponse:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": message},
            )

        @app.get("/", include_in_schema=False)
        async def _root_unavailable():
            return _startup_error_response()

        @app.get("/health")
        async def _health_unavailable():
            return _startup_error_response()

        return app


app = _create_module_app()
