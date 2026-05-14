from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends

from llama_manager.api.dependencies import get_node_registry
from llama_manager.api.routes.nodes.common import (
    annotate_model_sources,
    failed_node_payload,
    stale_node_payload,
)
from llama_manager.core.nodes.registry import NodeRegistry


router = APIRouter()


@router.get("/nodes/status")
async def node_status(registry: NodeRegistry = Depends(get_node_registry)):
    results = []
    for node in registry.list_nodes():
        if not node["heartbeat_fresh"]:
            results.append(stale_node_payload(node, include_models=False))
            continue
        try:
            payload = await registry.request_node(node["name"], "GET", "/health")
            results.append({**node, "reachable": True, "health": payload})
        except httpx.HTTPStatusError as exc:
            results.append(failed_node_payload(node, exc, include_models=False))
        except httpx.HTTPError as exc:
            results.append(failed_node_payload(node, exc, include_models=False))
        except Exception as exc:
            results.append(failed_node_payload(node, exc, include_models=False))
    return results


@router.get("/nodes/models")
async def node_models(registry: NodeRegistry = Depends(get_node_registry)):
    results = []
    for node in registry.list_nodes():
        if not node["heartbeat_fresh"]:
            results.append(stale_node_payload(node, include_models=True))
            continue
        try:
            models = await registry.request_node(node["name"], "GET", "/models")
            models_source = annotate_model_sources(models)
            health = await registry.request_node(node["name"], "GET", "/health")
            results.append(
                {
                    **node,
                    "reachable": True,
                    "models": models,
                    "agent_config_source": health.get("config_source"),
                    "models_source": models_source,
                }
            )
        except Exception as exc:
            results.append(failed_node_payload(node, exc, include_models=True))
    return results
