from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from llama_manager.api.dependencies import get_node_registry
from llama_manager.api.routes.nodes.common import NodeRegistrationRequest, NodeUpdateRequest
from llama_manager.core.config import NodeConfig
from llama_manager.core.nodes.registry import NodeRegistry


router = APIRouter()


@router.get("/nodes")
def list_nodes(registry: NodeRegistry = Depends(get_node_registry)):
    return registry.list_nodes()


@router.post("/nodes/register")
def register_node(
    payload: NodeRegistrationRequest,
    registry: NodeRegistry = Depends(get_node_registry),
):
    expected = registry.config.controller_registration_key
    if expected and payload.registration_key != expected:
        raise HTTPException(status_code=401, detail="Invalid registration key")
    registry.register_node(
        payload.name,
        NodeConfig(url=payload.url, api_key=payload.api_key, verify_tls=payload.verify_tls),
    )
    return {"ok": True, "name": payload.name}


@router.put("/nodes/{node}")
def update_node(
    node: str,
    payload: NodeUpdateRequest,
    registry: NodeRegistry = Depends(get_node_registry),
):
    try:
        return registry.update_node(
            node,
            NodeConfig(url=payload.url, api_key=payload.api_key, verify_tls=payload.verify_tls),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/nodes/{node}/heartbeat")
def node_heartbeat(node: str, registry: NodeRegistry = Depends(get_node_registry)):
    try:
        registry.record_heartbeat(node)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "name": node}
