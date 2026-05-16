from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from llama_manager.api.dependencies import get_quantization_manager
from llama_manager.core.model_assets.quantizations import QuantizationManager
from llama_manager.core.runtime.log_stream import stream_log_file


router = APIRouter(prefix="/quantizations")


class StartQuantizationRequest(BaseModel):
    type: str = "Q4_K_M"


@router.get("/files")
def list_quantization_files(manager: QuantizationManager = Depends(get_quantization_manager)):
    return manager.list_files()


@router.get("/{file_id}")
def quantization_status(file_id: str, manager: QuantizationManager = Depends(get_quantization_manager)):
    try:
        return manager.status(file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{file_id}/start")
def start_quantization(
    file_id: str,
    request: StartQuantizationRequest,
    manager: QuantizationManager = Depends(get_quantization_manager),
):
    try:
        return manager.start(file_id, request.type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{file_id}/logs")
def quantization_logs(
    file_id: str,
    lines: int = 200,
    manager: QuantizationManager = Depends(get_quantization_manager),
):
    try:
        return {"id": file_id, "text": manager.tail_logs(file_id, lines=lines)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{file_id}/logs/stream")
def stream_quantization_logs(
    file_id: str,
    lines: int = 200,
    manager: QuantizationManager = Depends(get_quantization_manager),
):
    try:
        log_path = manager.log_path(file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(stream_log_file(log_path, lines=lines), media_type="text/event-stream")
