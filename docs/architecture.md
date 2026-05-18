# Architecture Overview

This repository is intentionally split into three layers so behavior is easier to reason about and review:

- API layer (`llama_manager/api`): HTTP request/response translation and validation.
- Core layer (`llama_manager/core`): domain logic for process management, chat routing, orchestration, and persistence workflows.
- Provider/storage layer (`llama_manager/providers`, `llama_manager/storage`): external command composition and persistence primitives.

API routes live under package-style modules in `llama_manager/api/routes`:

- Single-resource routes use direct modules such as `routes.models`, `routes.library`, and `routes.health`.
- Grouped surfaces use packages such as `routes.auth`, `routes.chat`, and `routes.nodes`.
- Shared request/response helpers stay beside their route group, for example `routes.chat.common` and `routes.nodes.common`.

## Runtime Modes

`AppConfig.mode` controls deployment behavior:

- `agent`: manages local `llama-server` processes and local model utilities.
- `controller`: tracks nodes, proxies operations, and manages durable job orchestration.

Both modes share the same codebase and routes; mode-specific routes enforce behavior at runtime.

## Operational Scripts

- `scripts/onboard_controller.sh`: creates or validates controller config, writes `.llama-manager.env`, runs migrations, creates the first admin API key, and prints the registration key for agents.
- `scripts/onboard_agent.sh`: creates or validates agent config, writes `.llama-manager.env`, generates the agent API key, and prints the controller `nodes:` entry.
- `scripts/start_agent.sh`, `scripts/start_controller.sh`, and `scripts/stop_server.sh`: source `.llama-manager.env` and manage local uvicorn processes.
- `scripts/regenerate_key.sh`: rotates controller registration or agent API keys and prints the matching update for the other machines.

## Request Flow (High-Level)

1. `llama_manager/main.py` builds app state (config, managers, stores).
2. Dependencies in `llama_manager/api/dependencies.py` inject shared services.
3. Route handlers validate request shape and call core services.
4. Core services own business rules and persistence writes.

## Core Ownership Map

- `core/config`: typed config models plus file/env loading and saving.
- `core/runtime`: local process lifecycle and health payload construction.
- `core/chat`: target resolution, transport building, capability inspection, and chat proxying.
- `core/nodes`: controller node registry plus agent heartbeat and worker loops.
- `core/model_assets`: GGUF library registration, HF conversion, and quantization workflows.
- `core/orchestration`: durable job queue, attempts, events, contracts, retries, retention, archive export, and controller coordination.
- `core/persistence`: focused SQLite-backed persistence for auth, chat sessions, and audit events.

## Testing Strategy

- `tests/test_api.py`: route contract and API behavior.
- `tests/test_process_manager.py`: process lifecycle behavior.
- `tests/test_orchestration_store.py`: queue durability/retry/timeout behavior.
- Additional focused tests cover config normalization, library helpers, conversions, quantizations, and heartbeat logic.

## Review Heuristics

When reviewing changes, keep responsibilities narrow:

- Route files should not contain domain branching that belongs in `core`.
- Core modules should not perform implicit request parsing.
- Persistence changes should include tests for retries, timeout handling, and terminal-state transitions.

This keeps complexity bounded and allows reviewers to evaluate behavior by layer.

## Pull Request Rubric

Use this checklist before opening or approving a PR:

- Route vs Core boundary:
  - Route modules should do validation, dependency wiring, and HTTP error mapping only.
  - Business decisions, retries, and state transitions belong in `llama_manager/core`.
- Error mapping:
  - Upstream/network failures should be classified (`HTTP status` vs `transport`) and not collapsed into generic strings.
  - Preserve stable response keys for UI and API consumers.
- Status/result payload naming:
  - Use consistent keys for lifecycle states (`status`, `completed_at`, `error_code`, `error_detail`, `result`).
  - Avoid introducing synonymous fields for the same concept.
- Abstraction threshold:
  - Extract a helper when the same branching/payload logic appears in 2+ places.
  - Keep helpers private unless reused across modules.
- Test expectations:
  - Add or update tests for state-transition changes, retry/timeout behavior, and error-shape contracts.
  - Ensure full suite passes before merge.
