from __future__ import annotations


def should_bypass_middleware(path: str, method: str) -> bool:
    if path.startswith("/ui") or path in {"/", "/favicon.ico"}:
        return True
    if path.startswith("/health") or path.startswith("/auth/login"):
        return True
    if path.startswith("/nodes/register") or "/work/" in path or path.endswith("/work/claim"):
        return True
    if (method == "GET" and path.startswith("/auth/me")) or path.startswith("/auth/logout"):
        return True
    return False


def should_validate_ui_session(auth_enabled: bool, method: str) -> bool:
    return auth_enabled


def is_viewer_forbidden(path: str, role: str) -> bool:
    if role != "viewer":
        return False
    if path in {"/auth/logout"}:
        return False
    if path.startswith("/audit") or path.startswith("/auth"):
        return False
    return True


def should_enforce_agent_key(mode: str, configured_key: str | None, path: str) -> bool:
    if mode != "agent":
        return False
    if not configured_key:
        return False
    if path == "/health":
        return False
    return True
