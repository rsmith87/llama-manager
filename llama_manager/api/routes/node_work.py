from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from llama_manager.api.dependencies import get_orchestrator
from llama_manager.core.orchestration.orchestrator import Orchestrator


router = APIRouter()


def _enforce_node_work_auth(request: Request, node: str) -> None:
    try:
        node_config = request.app.state.node_registry.get_node_config(node)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown node: {node}") from exc
    expected = node_config.api_key
    if not expected:
        raise HTTPException(status_code=401, detail="Node work API key is required")
    provided = request.headers.get("X-Llama-Manager-Key")
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


class ClaimRequest(BaseModel):
    capacity: dict | None = None
    labels: dict | None = None
    max_jobs: int = Field(default=1, ge=1, le=20)


class ProgressRequest(BaseModel):
    progress: dict


class CompleteRequest(BaseModel):
    result: dict
    artifacts: list[dict] | None = None


class FailRequest(BaseModel):
    error_code: str
    error_detail: str | None = None
    retryable: bool = True


@router.post("/nodes/{node}/work/claim")
def claim_work(
    node: str,
    body: ClaimRequest,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    _enforce_node_work_auth(request, node)
    return orchestrator.claim_jobs(
        node_name=node,
        max_jobs=body.max_jobs,
        capacity=body.capacity,
        labels=body.labels,
    )


@router.post("/nodes/{node}/work/{attempt_id}/progress")
def progress_work(
    node: str,
    attempt_id: str,
    body: ProgressRequest,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    _enforce_node_work_auth(request, node)
    try:
        orchestrator.progress(node_name=node, attempt_id=attempt_id, progress=body.progress)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/nodes/{node}/work/{attempt_id}/complete")
def complete_work(
    node: str,
    attempt_id: str,
    body: CompleteRequest,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    _enforce_node_work_auth(request, node)
    try:
        return orchestrator.complete(node_name=node, attempt_id=attempt_id, result=body.result, artifacts=body.artifacts)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/nodes/{node}/work/{attempt_id}/fail")
def fail_work(
    node: str,
    attempt_id: str,
    body: FailRequest,
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    _enforce_node_work_auth(request, node)
    try:
        return orchestrator.fail(
            node_name=node,
            attempt_id=attempt_id,
            error_code=body.error_code,
            error_detail=body.error_detail,
            retryable=body.retryable,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
