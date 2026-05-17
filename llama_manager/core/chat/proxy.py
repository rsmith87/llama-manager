from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
import inspect
from typing import Any

import httpx

from llama_manager.core.chat import CapabilityInspector, ModelNotRunningError, PromptTemplateAdapter, TargetResolver, TransportBuilder
from llama_manager.core.config import AppConfig
from llama_manager.core.nodes.registry import NodeRegistry
from llama_manager.core.runtime.process_manager import ProcessManager


ChatRequest = Callable[..., Awaitable[dict[str, Any]]]
ChatStreamRequest = Callable[..., AsyncIterator[bytes]]


class ChatProxy:
    def __init__(self, process_manager: ProcessManager, config: AppConfig, node_registry: NodeRegistry, request: ChatRequest | None = None, stream_request: ChatStreamRequest | None = None):
        self.process_manager = process_manager
        self.config = config
        self.node_registry = node_registry
        self._request = self._adapt_request_callable(request or self._default_request)
        self._stream_request = self._adapt_stream_request_callable(stream_request or self._default_stream_request)
        self._resolver = TargetResolver(process_manager, node_registry, config)
        self._transport = TransportBuilder(node_registry)
        self._capabilities = CapabilityInspector(process_manager, config)
        self._prompt_templates = PromptTemplateAdapter()

    async def chat(self, model_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        response, _ = await self.chat_with_meta(model_name, payload)
        return response

    async def chat_with_meta(self, model_name: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        url, request_payload, headers, verify_tls, route_meta = await self._build_request(model_name, payload, stream=False)
        response = await self._call_request(url, request_payload, headers, verify_tls)
        return response, route_meta

    def stream(self, model_name: str, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        async def _stream() -> AsyncIterator[bytes]:
            stream, _ = await self.stream_with_meta(model_name, payload)
            async for chunk in stream:
                yield chunk
        return _stream()

    async def stream_with_meta(self, model_name: str, payload: dict[str, Any]) -> tuple[AsyncIterator[bytes], dict[str, str]]:
        url, request_payload, headers, verify_tls, route_meta = await self._build_request(model_name, payload, stream=True)

        async def _stream() -> AsyncIterator[bytes]:
            async for chunk in self._call_stream_request(url, request_payload, headers, verify_tls):
                yield chunk

        return _stream(), route_meta

    async def embeddings_with_meta(self, model_name: str, inputs: list[str], target_selector: str = "auto") -> tuple[dict[str, Any], dict[str, str]]:
        if not inputs:
            return {"data": [], "model": model_name}, {"route": "unknown"}
        payload = {"input": inputs, "model": model_name}
        if self.config.mode == "controller":
            target = await self._resolver.resolve_controller_target(model_name, target_selector)
            url, headers, verify_tls, route_meta = self._transport.embedding_transport_for_target(target)
            response = await self._call_request(url, payload, headers, verify_tls)
            return response, route_meta
        local_target = self._resolver.resolve_local_target(model_name)
        url = local_target["url"].replace("/v1/chat/completions", "/v1/embeddings")
        response = await self._call_request(url, payload, {}, True)
        return response, {"route": "local"}

    async def kv_slots_with_meta(self, model_name: str, target_selector: str = "auto") -> tuple[dict[str, Any], dict[str, str]]:
        url, headers, verify_tls, route_meta = await self._build_slots_request(model_name, target_selector, "")
        async with httpx.AsyncClient(timeout=None, verify=verify_tls) as client:
            response = await client.get(url, headers=headers or None)
            response.raise_for_status()
            return response.json(), route_meta

    async def kv_slot_action_with_meta(self, model_name: str, slot_id: int, action: str, target_selector: str = "auto") -> tuple[dict[str, Any], dict[str, str]]:
        suffix = f"/{slot_id}" if action == "clear" else f"/{slot_id}/{action}"
        url, headers, verify_tls, route_meta = await self._build_slots_request(model_name, target_selector, suffix)
        async with httpx.AsyncClient(timeout=None, verify=verify_tls) as client:
            response = await client.post(url, headers=headers or None, json={})
            response.raise_for_status()
            return response.json() if response.content else {"ok": True}, route_meta

    async def kv_capabilities_with_meta(self, model_name: str, target_selector: str = "auto") -> tuple[dict[str, Any], dict[str, str]]:
        checks = {
            "list_slots": ("GET", "/slots"),
            "clear_slot": ("POST", "/slots/0"),
            "save_slot": ("POST", "/slots/0/save"),
            "restore_slot": ("POST", "/slots/0/restore"),
            "erase_slot": ("POST", "/slots/0/erase"),
        }
        supports: dict[str, bool] = {}
        details: dict[str, Any] = {}
        route_meta: dict[str, str] = {"route": "unknown"}
        for key, (method, path_suffix) in checks.items():
            ok, status, route_meta = await self._probe_slot_path(model_name, target_selector, method, path_suffix)
            supports[key] = ok
            details[key] = {"status_code": status}
        return {"supports": supports, "probe": details}, route_meta

    def capabilities(self, model_name: str) -> dict[str, Any]:
        return self._capabilities.capabilities(model_name)

    def inspect_prompt(self, model_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages", [])
        joined = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "user"))
            content = msg.get("content", "")
            joined.append(f"{role}: {content}")
        rendered = "\n".join(joined).strip() or "(empty)"
        estimated_tokens = max(1, len(rendered) // 4)
        return {
            "model": model_name,
            "rendered_prompt_preview": rendered,
            "estimated_prompt_tokens": estimated_tokens,
            "estimation_method": "approx_chars_div_4",
        }

    async def _build_request(self, model_name: str, payload: dict[str, Any], stream: bool) -> tuple[str, dict[str, Any], dict[str, str], bool, dict[str, str]]:
        request_payload = {
            "messages": payload["messages"],
            "temperature": payload.get("temperature", 0.7),
            "max_tokens": payload.get("max_tokens", 512),
            "stream": stream,
            "chat_template_kwargs": {"enable_thinking": bool(payload.get("reasoning", False))},
        }
        model_template = self.config.models.get(model_name).prompt_template if model_name in self.config.models else None
        request_payload = self._prompt_templates.apply(model_name, model_template, request_payload, payload)
        for key in ("top_p", "top_k", "min_p", "repeat_penalty", "seed", "stop", "json_schema", "grammar"):
            if payload.get(key) is not None:
                request_payload[key] = payload[key]
        for key in ("cache_prompt", "slot_id"):
            if payload.get(key) is not None:
                request_payload[key] = payload[key]

        if self.config.mode == "controller":
            target = await self._resolver.resolve_controller_target(model_name, str(payload.get("target", "auto")))
            url, headers, verify_tls, route_meta = self._transport.chat_transport_for_target(target, model_name, stream)
            return url, request_payload, headers, verify_tls, route_meta

        local_target = self._resolver.resolve_local_target(model_name)
        return local_target["url"], request_payload, {}, True, {"route": "local"}

    async def _build_slots_request(self, model_name: str, target_selector: str, suffix: str) -> tuple[str, dict[str, str], bool, dict[str, str]]:
        if self.config.mode == "controller":
            target = await self._resolver.resolve_controller_target(model_name, target_selector)
            return self._transport.slot_transport_for_target(target, suffix)
        local_target = self._resolver.resolve_local_target(model_name)
        return local_target["url"].replace("/v1/chat/completions", f"/slots{suffix}"), {}, True, {"route": "local"}

    async def _probe_slot_path(self, model_name: str, target_selector: str, method: str, path_suffix: str) -> tuple[bool, int | None, dict[str, str]]:
        url, headers, verify_tls, route_meta = await self._build_slots_request(model_name, target_selector, path_suffix.replace("/slots", ""))
        async with httpx.AsyncClient(timeout=5.0, verify=verify_tls) as client:
            opt = await client.request("OPTIONS", url, headers=headers or None)
            allow = (opt.headers.get("allow") or "").upper()
            wanted = method.upper()
            if opt.status_code < 400 and allow and wanted in {item.strip() for item in allow.split(",")}:
                return True, opt.status_code, route_meta
            if method.upper() in {"GET", "HEAD"}:
                resp = await client.request(method.upper(), url, headers=headers or None)
                return resp.status_code < 400, resp.status_code, route_meta
            return False, opt.status_code, route_meta

    async def _call_request(self, url: str, payload: dict[str, Any], headers: dict[str, str], verify_tls: bool) -> dict[str, Any]:
        return await self._request(url, payload, headers, verify_tls)

    async def _call_stream_request(self, url: str, payload: dict[str, Any], headers: dict[str, str], verify_tls: bool) -> AsyncIterator[bytes]:
        async for chunk in self._stream_request(url, payload, headers, verify_tls):
            yield chunk

    @staticmethod
    async def _default_request(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, verify_tls: bool = True) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=None, verify=verify_tls) as client:
            response = await client.post(url, json=payload, headers=headers or None)
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def _default_stream_request(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, verify_tls: bool = True) -> AsyncIterator[bytes]:
        async with httpx.AsyncClient(timeout=None, verify=verify_tls) as client:
            async with client.stream("POST", url, json=payload, headers=headers or None) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    @staticmethod
    def _adapt_request_callable(fn: ChatRequest) -> Callable[[str, dict[str, Any], dict[str, str], bool], Awaitable[dict[str, Any]]]:
        param_count = len(inspect.signature(fn).parameters)
        if param_count >= 4:
            return fn

        async def _wrapped(url: str, payload: dict[str, Any], headers: dict[str, str], verify_tls: bool) -> dict[str, Any]:
            return await fn(url, payload)

        return _wrapped

    @staticmethod
    def _adapt_stream_request_callable(fn: ChatStreamRequest) -> Callable[[str, dict[str, Any], dict[str, str], bool], AsyncIterator[bytes]]:
        param_count = len(inspect.signature(fn).parameters)
        if param_count >= 4:
            return fn

        async def _wrapped(url: str, payload: dict[str, Any], headers: dict[str, str], verify_tls: bool) -> AsyncIterator[bytes]:
            async for chunk in fn(url, payload):
                yield chunk

        return _wrapped
