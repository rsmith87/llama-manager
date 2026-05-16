from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/settings", tags=["settings"])
SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
GEN_SCRIPT = SCRIPTS_DIR / "generate_api_key.py"


class KeyGenerateRequest(BaseModel):
    token_bytes: int = Field(default=32, ge=16, le=128)
    prefix: str = Field(default="llm", max_length=32)
    count: int = Field(default=1, ge=1, le=20)


@router.post("/api-keys/generate")
def generate_api_keys(payload: KeyGenerateRequest) -> dict[str, object]:
    if not GEN_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="Key generator script not found")

    cmd = [
        sys.executable,
        str(GEN_SCRIPT),
        "--bytes",
        str(payload.token_bytes),
        "--prefix",
        payload.prefix,
        "--count",
        str(payload.count),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=8)
    except subprocess.CalledProcessError as error:
        raise HTTPException(status_code=500, detail=error.stderr.strip() or "Key generation failed") from error
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=504, detail="Key generation timed out") from error

    keys = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {"keys": keys, "count": len(keys), "prefix": payload.prefix, "token_bytes": payload.token_bytes}
