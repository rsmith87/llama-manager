# Llama Manager MVP Design

## Goal

Build a single FastAPI codebase that runs as a local `llama.cpp` agent or as a thin central controller.

## Scope

The first pass prioritizes local agent control: configured model discovery, start, stop, restart, health, process status, system metrics, active model/port reporting, and log tailing. Controller mode stores configured node URLs and proxies control calls to agents while aggregating status.

The UI, OpenAI-compatible router, task routing, idle unload, persistence, and GPU-aware scheduling are intentionally out of scope for this pass.

## Architecture

The app reads one YAML config and can be switched with `mode: agent` or `mode: controller`, with `LLAMA_MANAGER_MODE` as an environment override. API routers are mounted from one FastAPI app. Agent routes use a local `ProcessManager`; controller routes use a `NodeRegistry` and HTTP client calls to remote agents.

## Components

- `core/config.py`: YAML/environment config loading and typed model/node definitions.
- `core/process_manager.py`: local `llama-server` process lifecycle, status, and log tailing.
- `core/node_registry.py`: known controller nodes and proxy helpers.
- `core/health_check.py`: app health payloads.
- `providers/llama_cpp.py`: command construction for `llama-server`.
- `providers/system_metrics.py`: RAM/VRAM best-effort metrics.
- `api/routes_models.py`: local model management.
- `api/routes_nodes.py`: controller node listing, status aggregation, and proxy calls.
- `api/routes_health.py`: health endpoint.

## Error Handling

Unknown models and nodes return `404`. Attempts to start an already-running model return current status instead of spawning a duplicate. Stop and restart calls are idempotent where practical. Controller proxy failures return `502` with the upstream error detail.

## Testing

Unit tests cover config loading, command construction, process manager lifecycle with a fake subprocess factory, log tailing, agent routes, and controller proxy behavior.

