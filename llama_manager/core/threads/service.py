from __future__ import annotations

import asyncio
from typing import Any

from llama_manager.core.config.models import AppConfig
from llama_manager.core.threads.routing import ModelRunning, RoutingPolicy
from llama_manager.core.threads.store import ThreadStore


class ThreadService:
    def __init__(
        self,
        config: AppConfig,
        store: ThreadStore,
        chat_proxy: Any,
        model_running: ModelRunning,
    ) -> None:
        self.config = config
        self.store = store
        self.chat_proxy = chat_proxy
        self.routing_policy = RoutingPolicy(config, model_running)

    def create_thread(
        self,
        title: str | None,
        default_model: str | None,
        metadata: dict[str, Any],
        created_by: str | None,
    ) -> dict[str, Any]:
        return self.store.create_thread(
            title=title,
            default_model=default_model,
            metadata=metadata,
            created_by=created_by,
        )

    def list_events(self, thread_id: str, include_internal: bool = False) -> list[dict[str, Any]]:
        self.store.get_thread(thread_id)
        return self.store.list_events(thread_id, include_internal=include_internal)

    def post_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        model: str | None,
        target: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.post_message_async(
                thread_id=thread_id,
                role=role,
                content=content,
                model=model,
                target=target,
                metadata=metadata,
            )
        )

    async def post_message_async(
        self,
        thread_id: str,
        role: str,
        content: str,
        model: str | None,
        target: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if role != "user":
            raise ValueError("ThreadService only accepts user messages")

        thread = self.store.get_thread(thread_id)
        request_metadata = {**thread.get("metadata", {}), **(metadata or {})}
        request_type = request_metadata.get("request_type") or "general"
        previous_route = self._previous_route(thread_id)
        messages = [
            *self._public_messages(thread_id),
            {"role": "user", "content": content},
        ]

        self.store.append_event(
            thread_id=thread_id,
            event_type="user_message",
            role="user",
            content={"text": content, "metadata": request_metadata},
            public=True,
        )

        try:
            decision = await self.routing_policy.choose(
                request_type=request_type,
                requested_model=model or thread.get("default_model"),
                explicit_target=target,
                previous_route=previous_route,
            )
        except ValueError as exc:
            self._append_error(thread_id, "ROUTING_ERROR", exc)
            raise

        route = {
            "node": decision.node,
            "model": decision.model,
            "strategy": decision.strategy,
            "reason": decision.reason,
        }

        self.store.append_event(
            thread_id=thread_id,
            event_type="routing_decision",
            role=None,
            content={**route, "candidates": list(decision.candidates)},
            public=False,
            route=route,
            agent_node=decision.node,
            model=decision.model,
        )

        try:
            raw_response, response_meta = await self.chat_proxy.chat_with_meta(
                decision.model,
                {
                    "messages": messages,
                    "target": f"node:{decision.node}",
                },
            )
            assistant_content = raw_response["choices"][0]["message"]["content"]
        except Exception as exc:
            self._append_error(thread_id, "CHAT_PROXY_ERROR", exc)
            raise

        self.store.append_event(
            thread_id=thread_id,
            event_type="assistant_message",
            role="assistant",
            content={
                "text": assistant_content,
                "raw_response": raw_response,
                "response_meta": response_meta,
            },
            public=True,
            route=route,
            agent_node=decision.node,
            model=decision.model,
        )

        return {
            "thread_id": thread_id,
            "message": {"role": "assistant", "content": assistant_content},
            "route": route,
        }

    def _previous_route(self, thread_id: str) -> dict[str, Any] | None:
        for event in reversed(self.store.list_events(thread_id, include_internal=True)):
            if event["event_type"] != "assistant_message":
                continue
            if event.get("agent_node") and event.get("model"):
                return {"node": event["agent_node"], "model": event["model"]}
        return None

    def _public_messages(self, thread_id: str) -> list[dict[str, str]]:
        messages = []
        for event in self.store.list_events(thread_id, include_internal=False):
            if event["event_type"] not in {"user_message", "assistant_message"}:
                continue
            text = event["content"].get("text")
            role = event.get("role")
            if isinstance(text, str) and role in {"user", "assistant"}:
                messages.append({"role": role, "content": text})
        return messages

    def _append_error(self, thread_id: str, error_code: str, exc: Exception) -> None:
        self.store.append_event(
            thread_id=thread_id,
            event_type="error",
            role=None,
            content={"text": str(exc)},
            public=True,
            error_code=error_code,
            error_detail=str(exc),
        )
