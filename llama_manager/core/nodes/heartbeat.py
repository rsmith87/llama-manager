from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from llama_manager.core.config import AppConfig


RequestFn = Callable[[str, str, dict[str, Any] | None], Awaitable[dict[str, Any]]]


class AgentHeartbeatClient:
    def __init__(self, config: AppConfig, request: RequestFn | None = None):
        self.config = config
        self._request = request or self._default_request
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    def enabled(self) -> bool:
        return (
            self.config.mode == "agent"
            and bool(self.config.controller_url)
            and bool(self.config.node_name)
        )

    async def start(self) -> None:
        if not self.enabled() or self._task is not None:
            return
        self._stopped.clear()
        await self._register()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        interval = max(5, self.config.heartbeat_interval_seconds)
        while not self._stopped.is_set():
            await self._heartbeat()
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _register(self) -> None:
        url = self.config.controller_url.rstrip("/")
        payload = {
            "name": self.config.node_name,
            "url": self.config.agent_url,
            "registration_key": self.config.controller_registration_key_outbound,
        }
        await self._request("POST", f"{url}/nodes/register", payload)

    async def _heartbeat(self) -> None:
        url = self.config.controller_url.rstrip("/")
        await self._request("POST", f"{url}/nodes/{self.config.node_name}/heartbeat", None)

    @staticmethod
    async def _default_request(
        method: str, url: str, payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, url, json=payload)
            response.raise_for_status()
            return response.json()
