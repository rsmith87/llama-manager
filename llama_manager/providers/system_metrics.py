from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - exercised in dependency-light environments
    psutil = None


def get_system_metrics() -> dict[str, Any]:
    if psutil is None:
        return {
            "platform": platform.system(),
            "ram": None,
            "cpu": None,
            "vram": _nvidia_smi_metrics(),
        }

    memory = psutil.virtual_memory()
    metrics: dict[str, Any] = {
        "platform": platform.system(),
        "ram": {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent,
        },
        "cpu": {"percent": psutil.cpu_percent(interval=None)},
        "vram": None,
    }
    metrics["vram"] = _nvidia_smi_metrics()
    return metrics


def _nvidia_smi_metrics() -> list[dict[str, int | str]] | None:
    if shutil.which("nvidia-smi") is None:
        return None

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    gpus = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        name, total, used, free = parts
        gpus.append(
            {
                "name": name,
                "memory_total_mb": int(total),
                "memory_used_mb": int(used),
                "memory_free_mb": int(free),
            }
        )
    return gpus
