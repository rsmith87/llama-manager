from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from pydantic import BaseModel

from llama_manager.api.dependencies import get_gguf_library
from llama_manager.core.model_assets.library import GgufLibrary


class AddModelRequest(BaseModel):
    name: str
    port: int
    ctx: int = 4096
    gpu_layers: int = 0
    host: str = "0.0.0.0"
    reasoning: Literal["on", "off", "auto"] | None = None
    reasoning_budget: int | None = None


router = APIRouter(prefix="/library")


@router.get("/ggufs")
def list_ggufs(library: GgufLibrary = Depends(get_gguf_library)):
    return library.list_files()


@router.post("/ggufs/{file_id}/add-model")
def add_gguf_model(
    file_id: str,
    body: AddModelRequest,
    library: GgufLibrary = Depends(get_gguf_library),
):
    try:
        return library.add_model(
            file_id=file_id,
            name=body.name,
            port=body.port,
            ctx=body.ctx,
            gpu_layers=body.gpu_layers,
            host=body.host,
            reasoning=body.reasoning,
            reasoning_budget=body.reasoning_budget,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/ggufs/{file_id}")
def delete_gguf_file(
    file_id: str,
    library: GgufLibrary = Depends(get_gguf_library),
):
    try:
        return library.delete_file(file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/models/{name}")
def remove_model(
    name: str,
    library: GgufLibrary = Depends(get_gguf_library),
):
    try:
        return library.remove_model(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
