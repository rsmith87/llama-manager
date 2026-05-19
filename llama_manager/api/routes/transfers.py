from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llama_manager.api.dependencies import get_node_registry, get_orchestrator, get_transfer_manager
from llama_manager.core.model_assets.transfers import TransferManager
from llama_manager.core.nodes.registry import NodeRegistry
from llama_manager.core.orchestration.job_contracts import validate_job_payload
from llama_manager.core.orchestration.orchestrator import Orchestrator


router = APIRouter()


class TransferGrantRequest(BaseModel):
    source_file_id: str
    transfer_token: str
    destination_node: str


class CreateTransferRequest(BaseModel):
    destination_node: str
    source_file_id: str
    include: str = "selected_with_sidecars"


@router.post("/nodes/{source}/transfers", status_code=status.HTTP_201_CREATED)
async def create_transfer(
    source: str,
    body: CreateTransferRequest,
    request: Request,
    registry: NodeRegistry = Depends(get_node_registry),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    try:
        source_config = registry.get_node_config(source)
        registry.get_node_config(body.destination_node)
        transfer_token = secrets.token_urlsafe(32)
        await registry.request_node(
            source,
            "POST",
            "/transfer-source/grants",
            json_body={
                "source_file_id": body.source_file_id,
                "transfer_token": transfer_token,
                "destination_node": body.destination_node,
            },
        )
        payload = validate_job_payload(
            "model.transfer",
            {
                "source_node": source,
                "destination_node": body.destination_node,
                "source_file_id": body.source_file_id,
                "include": body.include,
                "source_url": source_config.url,
                "transfer_token": transfer_token,
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    actor = getattr(request.state, "ui_user", None)
    return orchestrator.create_job(
        job_type="model.transfer",
        payload=payload,
        target=f"node:{body.destination_node}",
        requested_by=actor,
    )


@router.get("/transfers")
def list_transfers(orchestrator: Orchestrator = Depends(get_orchestrator)):
    jobs = orchestrator.list_jobs(limit=200)
    return [_transfer_payload(job) for job in jobs if job.get("type") == "model.transfer"]


@router.get("/transfers/{transfer_id}")
def get_transfer(transfer_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        job = orchestrator.get_job(transfer_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if job.get("type") != "model.transfer":
        raise HTTPException(status_code=404, detail=f"Unknown transfer: {transfer_id}")
    return _transfer_payload(job)


@router.post("/transfer-source/grants")
def create_transfer_grant(
    body: TransferGrantRequest,
    manager: TransferManager = Depends(get_transfer_manager),
):
    try:
        manager.create_grant(body.source_file_id, body.transfer_token, body.destination_node)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/transfer-source/ggufs/{file_id}/manifest")
def transfer_source_manifest(
    file_id: str,
    authorization: str | None = Header(default=None),
    manager: TransferManager = Depends(get_transfer_manager),
):
    try:
        manager.require_grant(file_id, authorization)
        return manager.build_manifest(file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/transfer-source/files/{file_id}/content")
def transfer_source_file_content(
    file_id: str,
    authorization: str | None = Header(default=None),
    manager: TransferManager = Depends(get_transfer_manager),
):
    try:
        path = manager.file_for_token(file_id)
        manager.require_file_grant(path, authorization)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(path)


def _transfer_payload(job: dict) -> dict:
    payload = job.get("payload") or {}
    result = job.get("result") or {}
    return {
        "id": job.get("id"),
        "status": job.get("status"),
        "source_node": payload.get("source_node"),
        "destination_node": payload.get("destination_node"),
        "source_file_id": payload.get("source_file_id"),
        "include": payload.get("include"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "completed_at": result.get("completed_at") or job.get("completed_at"),
        "files_total": result.get("files_total"),
        "files_copied": result.get("files_copied"),
        "files_skipped": result.get("files_skipped"),
        "bytes_copied": result.get("bytes_copied"),
        "copied": result.get("copied", []),
        "skipped": result.get("skipped", []),
        "error_code": job.get("error_code"),
        "error_detail": job.get("error_detail"),
    }
