from __future__ import annotations

from fastapi import APIRouter, Depends

from llama_manager.api.dependencies import get_node_registry
from llama_manager.api.routes.nodes.common import proxy_node_request
from llama_manager.core.nodes.registry import NodeRegistry


router = APIRouter()


@router.post("/nodes/{node}/models/{name}/start")
async def start_node_model(
    node: str, name: str, registry: NodeRegistry = Depends(get_node_registry)
):
    return await proxy_node_request(registry, node, "POST", f"/models/{name}/start")


@router.post("/nodes/{node}/models/{name}/stop")
async def stop_node_model(
    node: str, name: str, registry: NodeRegistry = Depends(get_node_registry)
):
    return await proxy_node_request(registry, node, "POST", f"/models/{name}/stop")


@router.post("/nodes/{node}/models/{name}/restart")
async def restart_node_model(
    node: str, name: str, registry: NodeRegistry = Depends(get_node_registry)
):
    return await proxy_node_request(registry, node, "POST", f"/models/{name}/restart")


@router.get("/nodes/{node}/logs/{name}")
async def node_logs(
    node: str,
    name: str,
    lines: int = 200,
    registry: NodeRegistry = Depends(get_node_registry),
):
    return await proxy_node_request(registry, node, "GET", f"/logs/{name}?lines={lines}")


@router.get("/nodes/{node}/logs/{name}/stream")
async def node_logs_stream(
    node: str,
    name: str,
    lines: int = 200,
    registry: NodeRegistry = Depends(get_node_registry),
):
    return await proxy_node_request(registry, node, "GET", f"/logs/{name}/stream?lines={lines}")
