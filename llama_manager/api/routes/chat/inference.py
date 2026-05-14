from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from llama_manager.api.dependencies import get_chat_proxy
from llama_manager.api.routes.chat.common import ChatRequestBody, EmbeddingsRequestBody, raise_proxy_http_exception
from llama_manager.core.chat.proxy import ChatProxy


router = APIRouter(prefix="/chat")


@router.post("/{model_name}/embeddings")
async def chat_embeddings(
    model_name: str,
    body: EmbeddingsRequestBody,
    proxy: ChatProxy = Depends(get_chat_proxy),
):
    try:
        values = [body.input] if isinstance(body.input, str) else body.input
        payload, meta = await proxy.embeddings_with_meta(model_name, values, body.target)
        return JSONResponse(content=payload, headers={"X-Llama-Manager-Route": meta.get("route", "unknown")})
    except Exception as exc:
        raise_proxy_http_exception(exc)


@router.post("/{model_name}/inspect")
async def chat_inspect(
    model_name: str,
    body: ChatRequestBody,
    proxy: ChatProxy = Depends(get_chat_proxy),
):
    try:
        return proxy.inspect_prompt(model_name, body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/capabilities/{model_name}")
async def chat_capabilities(
    model_name: str,
    proxy: ChatProxy = Depends(get_chat_proxy),
):
    try:
        return proxy.capabilities(model_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{model_name}")
async def chat(
    model_name: str,
    body: ChatRequestBody,
    proxy: ChatProxy = Depends(get_chat_proxy),
):
    try:
        payload, meta = await proxy.chat_with_meta(model_name, body.model_dump())
        return JSONResponse(content=payload, headers={"X-Llama-Manager-Route": meta.get("route", "unknown")})
    except Exception as exc:
        raise_proxy_http_exception(exc)


@router.post("/{model_name}/stream")
async def chat_stream(
    model_name: str,
    body: ChatRequestBody,
    proxy: ChatProxy = Depends(get_chat_proxy),
):
    try:
        stream, meta = await proxy.stream_with_meta(model_name, body.model_dump())
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={"X-Llama-Manager-Route": meta.get("route", "unknown")},
        )
    except Exception as exc:
        raise_proxy_http_exception(exc)
