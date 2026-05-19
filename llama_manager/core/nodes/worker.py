from __future__ import annotations

import asyncio
import io
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import monotonic
from typing import Any

import httpx

from llama_manager.core.config import AppConfig
from llama_manager.core.model_assets.transfers import TransferManager
from llama_manager.core.orchestration.job_contracts import chat_payload_from_llm_generate


WorkerRequest = Callable[[str, str, dict[str, Any] | None, dict[str, str] | None], Awaitable[Any]]
WorkerChat = Callable[[str, dict[str, Any]], Awaitable[tuple[dict[str, Any], dict[str, str]]]]
WorkerTransferStream = Callable[[str, dict[str, str]], Awaitable[Any]]


class AgentWorker:
    def __init__(
        self,
        config: AppConfig,
        request: WorkerRequest | None = None,
        chat: WorkerChat | None = None,
        transfer_stream: WorkerTransferStream | None = None,
    ):
        self.config = config
        self._request = request or self._default_request
        self._chat = chat
        self._transfer_stream = transfer_stream or self._default_transfer_stream
        self._transfer_manager = TransferManager(config)
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    @property
    def enabled(self) -> bool:
        return bool(
            self.config.mode == "agent"
            and self.config.agent_worker_enabled
            and self.config.controller_url
            and self.config.node_name
        )

    async def start(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        assert self._stop_event is not None
        self._stop_event.set()
        await self._task
        self._task = None
        self._stop_event = None

    async def _loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                pass
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.agent_worker_poll_interval_seconds,
                )
            except TimeoutError:
                continue

    async def run_once(self) -> int:
        if not self.enabled:
            return 0
        claims = await self._claim()
        for claim in claims:
            await self._handle_claim(claim)
        return len(claims)

    async def _claim(self) -> list[dict[str, Any]]:
        payload = {
            "max_jobs": self.config.agent_worker_max_jobs,
            "labels": self.config.agent_worker_labels,
            "capacity": self.config.agent_worker_capacity,
        }
        response = await self._request("POST", self._url(f"/nodes/{self.config.node_name}/work/claim"), payload, self._headers())
        return response if isinstance(response, list) else []

    async def _handle_claim(self, claim: dict[str, Any]) -> None:
        job = claim.get("job") if isinstance(claim.get("job"), dict) else {}
        attempt_id = str(claim.get("attempt_id", ""))
        job_type = str(job.get("type", ""))
        if not attempt_id:
            return
        if job_type == "llm.generate":
            await self._run_llm_generate(attempt_id, job)
            return
        if job_type == "model.transfer":
            await self._run_model_transfer(attempt_id, job)
            return
        await self._fail(attempt_id, "UNSUPPORTED_JOB_TYPE", f"Unsupported job type: {job_type}", retryable=False)

    async def _run_llm_generate(self, attempt_id: str, job: dict[str, Any]) -> None:
        job_id = str(job.get("id", ""))
        if await self._is_cancel_requested(job_id):
            await self._fail(attempt_id, "CANCELED", "Job canceled before execution", retryable=False)
            return
        await self._progress(attempt_id, {"stage": "started", "job_type": "llm.generate"})
        started = monotonic()
        try:
            if self._chat is None:
                raise RuntimeError("Agent worker chat executor is not configured")
            model, chat_payload = chat_payload_from_llm_generate(job.get("payload", {}))
            response, route_meta = await self._chat(model, {**chat_payload, "target": "local"})
            elapsed_ms = int((monotonic() - started) * 1000)
            if await self._is_cancel_requested(job_id):
                await self._fail(attempt_id, "CANCELED", "Job canceled after model execution", retryable=False)
                return
            await self._complete(
                attempt_id,
                {
                    "response": response,
                    "route": route_meta,
                    "model": model,
                    "target": chat_payload.get("target", "local"),
                    "worker_node": self.config.node_name,
                    "elapsed_ms": elapsed_ms,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except ValueError as exc:
            await self._fail(attempt_id, "INVALID_JOB_PAYLOAD", str(exc), retryable=False)
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            await self._fail(attempt_id, "UPSTREAM_HTTP_ERROR", str(exc), retryable=retryable)
        except httpx.HTTPError as exc:
            await self._fail(attempt_id, "UPSTREAM_TRANSPORT_ERROR", str(exc), retryable=True)
        except Exception as exc:
            await self._fail(attempt_id, "EXECUTION_ERROR", str(exc), retryable=True)

    async def _run_model_transfer(self, attempt_id: str, job: dict[str, Any]) -> None:
        job_id = str(job.get("id", ""))
        payload = job.get("payload", {})
        if await self._is_cancel_requested(job_id):
            await self._fail(attempt_id, "CANCELED", "Job canceled before transfer", retryable=False)
            return
        await self._progress(attempt_id, {"stage": "manifest", "job_type": "model.transfer"})
        try:
            source_node = str(payload["source_node"])
            source_file_id = str(payload["source_file_id"])
            source_base = str(payload["source_url"]).rstrip("/")
            transfer_headers = {"Authorization": f"Bearer {payload['transfer_token']}"}
            manifest = await self._transfer_stream(
                f"{source_base}/transfer-source/ggufs/{source_file_id}/manifest",
                transfer_headers,
            )
            files = manifest.get("files", []) if isinstance(manifest, dict) else []
            copied = []
            skipped = []
            bytes_copied = 0
            for index, manifest_file in enumerate(files, start=1):
                if await self._is_cancel_requested(job_id):
                    await self._fail(attempt_id, "CANCELED", "Job canceled during transfer", retryable=False)
                    return
                await self._progress(
                    attempt_id,
                    {
                        "stage": "copying",
                        "file_index": index,
                        "files_total": len(files),
                        "relative_path": manifest_file.get("relative_path"),
                    },
                )
                stream = await self._transfer_stream(
                    f"{source_base}/transfer-source/files/{manifest_file['id']}/content",
                    transfer_headers,
                )
                result = self._transfer_manager.write_manifest_file(manifest_file, stream)
                if result["status"] == "copied":
                    copied.append(result)
                    bytes_copied += int(result["bytes"])
                else:
                    skipped.append(result)
            await self._complete(
                attempt_id,
                {
                    "source_node": source_node,
                    "destination_node": self.config.node_name,
                    "source_file_id": source_file_id,
                    "files_total": len(files),
                    "files_copied": len(copied),
                    "files_skipped": len(skipped),
                    "bytes_copied": bytes_copied,
                    "copied": copied,
                    "skipped": skipped,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except FileExistsError as exc:
            await self._fail(attempt_id, "DESTINATION_CONFLICT", str(exc), retryable=False)
        except KeyError as exc:
            await self._fail(attempt_id, "INVALID_TRANSFER_PAYLOAD", str(exc), retryable=False)
        except Exception as exc:
            await self._fail(attempt_id, "TRANSFER_ERROR", str(exc), retryable=True)

    async def _is_cancel_requested(self, job_id: str) -> bool:
        if not job_id:
            return False
        job = await self._request("GET", self._url(f"/jobs/{job_id}"), None, self._headers())
        return bool(isinstance(job, dict) and job.get("cancellation_requested"))

    async def _progress(self, attempt_id: str, progress: dict[str, Any]) -> None:
        await self._request("POST", self._url(f"/nodes/{self.config.node_name}/work/{attempt_id}/progress"), {"progress": progress}, self._headers())

    async def _complete(self, attempt_id: str, result: dict[str, Any]) -> None:
        await self._request("POST", self._url(f"/nodes/{self.config.node_name}/work/{attempt_id}/complete"), {"result": result}, self._headers())

    async def _fail(self, attempt_id: str, error_code: str, error_detail: str, retryable: bool) -> None:
        await self._request(
            "POST",
            self._url(f"/nodes/{self.config.node_name}/work/{attempt_id}/fail"),
            {"error_code": error_code, "error_detail": error_detail, "retryable": retryable},
            self._headers(),
        )

    def _url(self, path: str) -> str:
        return f"{str(self.config.controller_url).rstrip('/')}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        if self.config.controller_registration_key_outbound:
            return {"X-Llama-Manager-Key": self.config.controller_registration_key_outbound}
        return {}

    @staticmethod
    async def _default_request(method: str, url: str, payload: dict[str, Any] | None, headers: dict[str, str] | None) -> Any:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.request(method, url, json=payload, headers=headers or None)
            response.raise_for_status()
            return response.json() if response.content else {"ok": True}

    @staticmethod
    async def _default_transfer_stream(url: str, headers: dict[str, str]) -> Any:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.json()
            return io.BytesIO(response.content)
