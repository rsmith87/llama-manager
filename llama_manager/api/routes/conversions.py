from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from llama_manager.api.dependencies import get_conversion_manager
from llama_manager.core.model_assets.conversions import ConversionManager


router = APIRouter(prefix="/conversions")


@router.get("/models")
def list_conversion_models(manager: ConversionManager = Depends(get_conversion_manager)):
    return manager.list_models()


@router.get("/{name}")
def conversion_status(name: str, manager: ConversionManager = Depends(get_conversion_manager)):
    try:
        return manager.status(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{name}/start")
def start_conversion(name: str, manager: ConversionManager = Depends(get_conversion_manager)):
    try:
        return manager.start(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{name}/logs")
def conversion_logs(
    name: str,
    lines: int = 200,
    manager: ConversionManager = Depends(get_conversion_manager),
):
    try:
        return {"name": name, "text": manager.tail_logs(name, lines=lines)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

