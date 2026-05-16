#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "linux-agent.config.example.yaml"


class SmokeCheckError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SystemExit(message)


def has_unresolved_placeholder(value: str | None) -> bool:
    return bool(value and "${" in value)


def validate_linux_agent_config(config: Any, expected_node: str) -> None:
    errors = []
    if config.mode != "agent":
        errors.append("mode must be 'agent'")
    if config.node_name != expected_node:
        errors.append(f"node_name must be '{expected_node}'")
    if not config.controller_url:
        errors.append("controller_url is required")
    if not config.agent_url:
        errors.append("agent_url is required")
    if not config.agent_api_key:
        errors.append("agent_api_key is required for controller reachability checks")
    elif has_unresolved_placeholder(config.agent_api_key):
        errors.append("agent_api_key has an unresolved environment placeholder")
    if config.controller_registration_key_outbound is None:
        errors.append("controller_registration_key_outbound is required")
    elif has_unresolved_placeholder(config.controller_registration_key_outbound):
        errors.append("controller_registration_key_outbound has an unresolved environment placeholder")
    if errors:
        fail("Linux agent config is not smoke-test ready:\n- " + "\n- ".join(errors))


def validate_runtime_paths(config: Any) -> None:
    errors = []
    llama_server_bin = Path(config.llama_server_bin).expanduser()
    llama_cpp_dir = Path(config.llama_cpp_dir).expanduser()
    if not llama_server_bin.is_file():
        errors.append(f"llama_server_bin does not exist: {llama_server_bin}")
    if not llama_cpp_dir.is_dir():
        errors.append(f"llama_cpp_dir does not exist: {llama_cpp_dir}")
    for root in config.model_roots:
        expanded = Path(root).expanduser()
        if not expanded.is_dir():
            errors.append(f"hf_models_dirs entry does not exist: {expanded}")
    if errors:
        fail("Linux runtime paths are not smoke-test ready:\n- " + "\n- ".join(errors))


def headers(api_key: str | None) -> dict[str, str]:
    return {"X-Llama-Manager-Key": api_key} if api_key else {}


def get_json(client: httpx.Client, url: str, api_key: str | None = None) -> Any:
    response = client.get(url, headers=headers(api_key))
    response.raise_for_status()
    return response.json()


def wait_for_agent_health(
    client: httpx.Client,
    agent_url: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    url = f"{agent_url.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            payload = get_json(client, url, api_key)
            if payload.get("mode") == "agent":
                return payload
            last_error = SmokeCheckError(f"{url} returned mode={payload.get('mode')!r}")
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise SmokeCheckError(f"Agent health did not become ready at {url}: {last_error}")


def normalize_url(value: str) -> str:
    return value.rstrip("/")


def find_registered_node(nodes: list[dict[str, Any]], node_name: str, agent_url: str) -> dict[str, Any]:
    for node in nodes:
        if node.get("name") != node_name:
            continue
        if normalize_url(str(node.get("url", ""))) != normalize_url(agent_url):
            raise SmokeCheckError(
                f"{node_name} registered with url={node.get('url')!r}, expected {agent_url!r}"
            )
        if not node.get("heartbeat_fresh"):
            raise SmokeCheckError(f"{node_name} heartbeat is not fresh")
        if not node.get("last_heartbeat"):
            raise SmokeCheckError(f"{node_name} has no last_heartbeat")
        return node
    raise SmokeCheckError(f"{node_name} is not listed by the controller")


def wait_for_controller_registration(
    client: httpx.Client,
    controller_url: str,
    node_name: str,
    agent_url: str,
    controller_api_key: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    url = f"{controller_url.rstrip('/')}/nodes"
    while time.monotonic() < deadline:
        try:
            nodes = get_json(client, url, controller_api_key)
            return find_registered_node(nodes, node_name, agent_url)
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    raise SmokeCheckError(f"Controller did not report fresh registration at {url}: {last_error}")


def start_agent(config_path: Path, host: str, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["LLAMA_MANAGER_CONFIG"] = str(config_path)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "llama_manager.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=ROOT_DIR,
        env=env,
        text=True,
    )


def stop_agent(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Linux agent and verify controller registration plus heartbeat."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--node", default="linux-2080ti")
    parser.add_argument("--host", default=os.getenv("LLAMA_MANAGER_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LLAMA_MANAGER_PORT", "9137")))
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument(
        "--controller-api-key",
        default=os.getenv("LLAMA_MANAGER_CONTROLLER_API_KEY"),
        help="API key for GET /nodes when the controller has auth enabled.",
    )
    parser.add_argument(
        "--stop-after-check",
        action="store_true",
        help="Stop the uvicorn process after the smoke checks pass.",
    )
    parser.add_argument(
        "--skip-runtime-path-check",
        action="store_true",
        help="Skip llama.cpp and model directory existence checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from llama_manager.core.config import load_config

    args = parse_args(argv or sys.argv[1:])
    config_path = args.config.resolve()
    config = load_config(config_path)
    validate_linux_agent_config(config, expected_node=args.node)
    if not args.skip_runtime_path_check:
        validate_runtime_paths(config)

    print(f"Config OK: {config_path}")
    process = start_agent(config_path, args.host, args.port)
    print(f"Started agent PID {process.pid} on {args.host}:{args.port}")
    try:
        with httpx.Client(timeout=5) as client:
            health = wait_for_agent_health(
                client,
                config.agent_url,
                config.agent_api_key or "",
                args.timeout,
            )
            print(f"Agent health OK: mode={health.get('mode')} config={health.get('config_source')}")
            node = wait_for_controller_registration(
                client,
                config.controller_url or "",
                args.node,
                config.agent_url,
                args.controller_api_key,
                args.timeout,
            )
            print(
                "Controller registration OK: "
                f"name={node.get('name')} heartbeat={node.get('last_heartbeat')}"
            )
    except Exception as exc:
        stop_agent(process)
        fail(f"Linux agent smoke test failed: {exc}")

    if args.stop_after_check:
        stop_agent(process)
        print("Stopped agent after successful smoke check.")
    else:
        print(f"Smoke test passed. Agent is still running on PID {process.pid}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
