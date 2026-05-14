from __future__ import annotations

from fastapi import APIRouter

from llama_manager.api.routes.chat import inference, kv, sessions


router = APIRouter()
router.include_router(sessions.router)
router.include_router(inference.router)
router.include_router(kv.router)
