from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from llama_manager.core.config.models import AppConfig


ModelRunning = Callable[[str, str], bool | Awaitable[bool]]


@dataclass(frozen=True)
class RouteDecision:
    node: str
    model: str
    strategy: str
    reason: str
    candidates: tuple[dict[str, Any], ...]


class RoutingPolicy:
    def __init__(self, config: AppConfig, model_running: ModelRunning) -> None:
        self.config = config
        self.model_running = model_running

    async def choose(
        self,
        request_type: str,
        requested_model: str | None,
        explicit_target: str,
        previous_route: dict[str, Any] | None,
    ) -> RouteDecision:
        if explicit_target.startswith("node:"):
            node_name = explicit_target.removeprefix("node:")
            return await self._choose_explicit_node(node_name, requested_model)
        if explicit_target not in {"", "auto"}:
            raise ValueError(f"Unsupported explicit target: {explicit_target}")

        affinity = await self._choose_thread_affinity(previous_route)
        if affinity is not None:
            return affinity

        request_type_decision = await self._choose_request_type(request_type)
        if request_type_decision is not None:
            return request_type_decision

        fallback = await self._choose_fallback(requested_model)
        if fallback is not None:
            return fallback

        raise ValueError("No eligible running model found")

    async def _choose_explicit_node(self, node_name: str, requested_model: str | None) -> RouteDecision:
        node = self.config.nodes.get(node_name)
        if node is None:
            raise ValueError(f"Unknown node target: {node_name}")
        model = requested_model or node.default_model
        if model is None:
            raise ValueError(f"No model specified for node target: {node_name}")
        candidates = ({"node": node_name, "model": model, "source": "explicit"},)
        if await self._model_running(node_name, model):
            return RouteDecision(
                node=node_name,
                model=model,
                strategy="explicit",
                reason="explicit_target",
                candidates=candidates,
            )
        raise ValueError(f"No eligible running model found for node target: {node_name}")

    async def _choose_thread_affinity(self, previous_route: dict[str, Any] | None) -> RouteDecision | None:
        if not previous_route:
            return None
        node = previous_route.get("node")
        model = previous_route.get("model")
        if not isinstance(node, str) or not isinstance(model, str):
            return None
        candidates = ({"node": node, "model": model, "source": "previous_route"},)
        if node in self.config.nodes and await self._model_running(node, model):
            return RouteDecision(
                node=node,
                model=model,
                strategy="deterministic",
                reason="thread_affinity",
                candidates=candidates,
            )
        return None

    async def _choose_request_type(self, request_type: str) -> RouteDecision | None:
        candidates = self._request_type_candidates(request_type)
        for candidate in candidates:
            if await self._model_running(candidate["node"], candidate["model"]):
                return RouteDecision(
                    node=candidate["node"],
                    model=candidate["model"],
                    strategy="deterministic",
                    reason="request_type",
                    candidates=tuple(candidates),
                )
        return None

    async def _choose_fallback(self, requested_model: str | None) -> RouteDecision | None:
        candidates: list[dict[str, Any]] = []
        for node_name in sorted(self.config.nodes):
            node = self.config.nodes[node_name]
            model = requested_model or node.default_model
            if model is None:
                continue
            candidate = {"node": node_name, "model": model, "source": "fallback"}
            candidates.append(candidate)
            if await self._model_running(node_name, model):
                return RouteDecision(
                    node=node_name,
                    model=model,
                    strategy="deterministic",
                    reason="fallback",
                    candidates=tuple(candidates),
                )
        return None

    def _request_type_candidates(self, request_type: str) -> list[dict[str, Any]]:
        candidates = []
        for node_name, node in self.config.nodes.items():
            route = node.request_types.get(request_type)
            if route is None:
                continue
            candidates.append(
                {
                    "node": node_name,
                    "model": route.model,
                    "priority": route.priority,
                    "source": "request_type",
                }
            )
        return sorted(candidates, key=lambda candidate: (candidate["priority"], candidate["node"]))

    async def _model_running(self, node: str, model: str) -> bool:
        result = self.model_running(node, model)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)
