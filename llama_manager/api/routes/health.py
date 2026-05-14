from __future__ import annotations

from fastapi import APIRouter, Depends

from llama_manager.api.dependencies import get_config
from llama_manager.core.config import AppConfig
from llama_manager.core.runtime.health_check import health_payload


router = APIRouter()


@router.get("/health")
def health(config: AppConfig = Depends(get_config)) -> dict[str, object]:
    return health_payload(config)

