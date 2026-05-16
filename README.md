# Llama Manager

Single-codebase FastAPI service for managing `llama.cpp` servers across local machines.

The app can run in two modes:

- `agent`: runs on each machine and manages local `llama-server` processes.
- `controller`: runs on a central Mac and proxies/aggregates calls across known agents.

The project started agent-first, but now includes a richer controller surface for node inventory, routing, and durable orchestration APIs.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# or, if you use uv:
uv sync
cp config.example.yaml config.yaml
export LLAMA_MANAGER_CONFIG=config.yaml
alembic -x db=controller upgrade controller@head
alembic -x db=auth upgrade auth@head
alembic -x db=audit upgrade audit@head
alembic -x db=chat_sessions upgrade chat_sessions@head
uv run python -m llama_manager.auth --config config.yaml create-admin robert
LLAMA_MANAGER_CONFIG=config.yaml uvicorn llama_manager.main:app --host 0.0.0.0 --port 9000
```

Or use the helper scripts:

```bash
scripts/start_server.sh
scripts/stop_server.sh
```

Script defaults:

```text
LLAMA_MANAGER_HOST=127.0.0.1
LLAMA_MANAGER_PORT=9137
LLAMA_MANAGER_CONFIG=./config.yaml if present, otherwise ./config.example.yaml
```

Linux agent smoke test for the `linux-2080ti` setup:

```bash
export LLAMA_MANAGER_AGENT_API_KEY=...
export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND=...
# Required if the controller protects GET /nodes with an admin/API key:
export LLAMA_MANAGER_CONTROLLER_API_KEY=...
scripts/linux_agent_smoke.py --config linux-agent.config.example.yaml
```

The smoke test validates the Linux agent config and runtime paths, starts the agent with that config, checks the agent `/health`, and waits until the controller lists `linux-2080ti` with a fresh heartbeat. Add `--stop-after-check` if you want the script to stop the agent after a successful run.

## Configuration

Set `LLAMA_MANAGER_CONFIG` to a YAML file path. Set `LLAMA_MANAGER_MODE` to override the mode without editing the file.

```yaml
mode: agent
llama_server_bin: llama-server
llama_cpp_dir: ./llama.cpp
python_bin: ./.venv/bin/python
hf_models_dirs:
  - ./models/HFModels
  - ./models/OtherModels
log_dir: ./logs

models:
  qwen-coder:
    path: ./models/qwen-coder.gguf
    port: 8081
    ctx: 16384
    gpu_layers: 999
    host: 0.0.0.0

nodes:
  mac-mini:
    url: http://127.0.0.1:9000
  windows-2080ti:
    url: http://192.168.1.74:9000
```

### First Admin Key

Llama Manager fails closed until you create an admin key or configure `agent_api_key`. Create the first admin key from the terminal:

```bash
uv run python -m llama_manager.auth --config config.yaml create-admin robert
```

The command stores a hashed key in `log_dir/auth_store.db` and prints the raw API key once. Use that key in the UI login form, or send it as `X-Llama-Manager-Key` for API requests. To create more keys later, log in as an admin and use the auth key management UI/API.

There is no built-in `dev` login fallback. For local development, create a throwaway admin key with the same command.

For static shared secrets in agent/controller config, generate a strong URL-safe value with:

```bash
scripts/generate_api_key.py
```

Use the printed value for matching config fields such as `agent_api_key`, `nodes.<name>.api_key`, `controller_registration_key`, and `controller_registration_key_outbound`.

### Agent Config

Use `mode: agent` on each machine that actually runs `llama-server` processes. Agent mode owns:

- local model definitions under `models`
- `llama_server_bin` startup for each configured model
- local log files and model process lifecycle
- optional local conversion/library workflows (`hf_models_dirs`, `llama_cpp_dir`, `python_bin`)

Example:

```yaml
mode: agent
llama_server_bin: /Users/robertsmith/Apps/llama.cpp/build/bin/llama-server
llama_cpp_dir: /Users/robertsmith/Apps/llama.cpp
python_bin: /Users/robertsmith/Apps/llama.cpp/.venv/bin/python
hf_models_dirs:
  - /Volumes/4TB/HFModels
log_dir: ./logs

models:
  qwen-coder:
    path: /Users/robertsmith/models/qwen-coder.gguf
    port: 8081
    ctx: 16384
    gpu_layers: 999
    host: 0.0.0.0
    reasoning: auto
    reasoning_budget: 2048
    extra_args: []
    supports_json_schema: false
    supports_grammar: false
    vision: false
    mmproj: null
```

### Controller Config

Use `mode: controller` on a central machine that coordinates agents. Controller mode owns:

- the `nodes` list (agent base URLs)
- node health/status aggregation
- proxying model start/stop/restart/log calls to each node

Example:

```yaml
mode: controller
log_dir: ./logs

nodes:
  mac-mini:
    url: http://127.0.0.1:9000
  windows-2080ti:
    url: http://192.168.1.74:9000
    api_key: your-agent-api-key-if-enabled
    verify_tls: true
```

For full setup and troubleshooting, see [docs/how-to-use.md](docs/how-to-use.md) and [docs/windows-install.md](docs/windows-install.md).
For a contributor-focused code map, see [docs/architecture.md](docs/architecture.md).

Optional security/registration fields:

- Agent-side auth: `agent_api_key` requires clients to send `X-Llama-Manager-Key`.
- Controller-to-agent auth per node: `nodes.<name>.api_key`.
- Auto-registration auth: `controller_registration_key` on controller, `controller_registration_key_outbound` on agent.
- Agent heartbeat/registration fields: `controller_url`, `node_name`, `agent_url`, `heartbeat_interval_seconds`.
- Stale node timeout on controller: `node_heartbeat_timeout_seconds`.

Optional controller persistence/retention fields:

- `controller_db_url`: optional SQLite URL/path override for controller orchestration state.
- `controller_instance_id`: identifier used for controller leader leases.
- `controller_leader_lease_seconds`: lease duration for the controller sweeper.
- `controller_retention_days`: active job/event retention window.
- `controller_archive_retention_days`: exported archive retention window.
- `controller_archive_dir`: archive export directory.

Optional agent worker fields:

- `agent_worker_enabled`: opt in to background work claiming from `controller_url`.
- `agent_worker_poll_interval_seconds`: polling interval when enabled.
- `agent_worker_max_jobs`: maximum jobs to claim per poll.
- `agent_worker_labels`: labels advertised to the controller claim matcher.
- `agent_worker_capacity`: numeric/string capacity advertised to the controller claim matcher.

Agent workers must be registered/configured on the controller under `nodes.<name>` with an `api_key`. The agent sends that same value with `controller_registration_key_outbound` when claiming or updating work; unknown nodes and nodes without an API key are rejected.

The first typed worker contract is `llm.generate`. It is intentionally narrow and reuses the existing chat payload shape (`model`, `messages`, sampling fields, structured-output fields, `reasoning`, and optional `target`/`requirements`). Future typed contracts are tracked in `docs/superpowers/plans/2026-05-12-execution-substrate.md`.

## Schema Migrations (Alembic)

Run migration upgrades before starting the app or creating admin keys.

Persistence is now Alembic-managed and SQLAlchemy-backed across all app
databases.

Alembic is scaffolded with multiple DB targets:

- `controller`
- `auth`
- `audit`
- `chat_sessions`

Select a target via `-x db=<target>`.

Examples:

```bash
alembic -x db=controller current
alembic -x db=auth revision -m "auth change" --version-path migrations/versions/auth
alembic -x db=audit upgrade audit@head
alembic -x db=chat_sessions downgrade -1
alembic -x db=controller stamp controller@head
```

If `-x db=` is omitted, target defaults to `controller`. Use target-qualified heads such as `auth@head`; unqualified `head` is ambiguous because each database target has its own Alembic branch.

Optional chat capability hint fields per model:

- `supports_json_schema`: override capability introspection for JSON Schema structured output.
- `supports_grammar`: override capability introspection for grammar structured output.
- `extra_args`: capability fallback infers structured output support when args include tokens like `json-schema` or `grammar`.
- `reasoning` and `reasoning_budget`: configure llama.cpp reasoning mode and budget for supported models.
- `vision` and `mmproj`: mark multimodal models and point to the matching projector file.
- `favorite`: mark a model as a UI favorite so it sorts first in model tables.

Windows paths work in YAML:

```yaml
models:
  gemma4-e2b:
    path: C:\models\gemma4-e2b.gguf
    port: 8080
    ctx: 8192
    gpu_layers: 999
```

## API

Core endpoints:

- `GET /health`
- `GET /models`
- `POST /models/{name}/start`
- `POST /models/{name}/stop`
- `POST /models/{name}/restart`
- `GET /logs/{name}?lines=200`
- `POST /chat/{name}`
- `POST /chat/{name}/stream`
- `GET /chat/capabilities/{name}`
- `POST /chat/{name}/inspect`
- `POST /chat/{name}/embeddings`
- `GET /chat/{name}/kv/slots?target=auto`
- `POST /chat/{name}/kv/slots/{slot_id}`
- `GET /chat/{name}/kv/capabilities?target=auto`
- `GET /chat/sessions`
- `GET /chat/sessions/{session_id}`
- `POST /chat/sessions`
- `DELETE /chat/sessions/{session_id}`
- `GET /library/ggufs`
- `POST /library/ggufs/{file_id}/add-model`
- `DELETE /library/ggufs/{file_id}`
- `DELETE /library/models/{name}`
- `GET /conversions/models`
- `POST /conversions/{name}/start`
- `GET /conversions/{name}`
- `GET /conversions/{name}/logs?lines=200`
- `GET /quantizations/files`
- `GET /quantizations/{file_id}`
- `POST /quantizations/{file_id}/start`
- `GET /quantizations/{file_id}/logs?lines=200`
- `GET /audit/events`
- `POST /audit/events`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`
- `GET /auth/keys`
- `POST /auth/keys`
- `POST /auth/keys/{key_id}/revoke`

Controller node endpoints:

- `GET /nodes`
- `GET /nodes/status`
- `GET /nodes/models`
- `POST /nodes/register`
- `POST /nodes/{node}/heartbeat`
- `POST /nodes/{node}/models/{name}/start`
- `POST /nodes/{node}/models/{name}/stop`
- `POST /nodes/{node}/models/{name}/restart`
- `GET /nodes/{node}/logs/{name}?lines=200`

The UI includes a Nodes page for controller mode that shows node reachability, heartbeat/config metadata, reported models, and remote model Start/Stop/Restart/Logs actions.

Controller orchestration endpoints (controller mode only):

- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`
- `GET /jobs/{job_id}/events`
- `GET /jobs/{job_id}/events/stream`
- `GET /jobs/{job_id}/artifacts`
- `GET /controller/stats`
- `GET /controller/retention-policy`
- `POST /controller/archive/export`
- `POST /nodes/{node}/work/claim`
- `POST /nodes/{node}/work/{attempt_id}/progress`
- `POST /nodes/{node}/work/{attempt_id}/complete`
- `POST /nodes/{node}/work/{attempt_id}/fail`

## Notes

- `agent` mode starts `llama-server` with `--model`, `--host`, `--port`, `--ctx-size`, and `--n-gpu-layers`.
- HF model conversion writes `{model-name}.gguf` inside the existing HF model directory, and existing conversion detection checks for any top-level `*.gguf` in that directory.
- Logs are written per model under `log_dir`.
- Process state is in-memory for this MVP. If the manager restarts, it reports configured models but does not reattach to old processes.

## Testing

Backend/API tests:

```bash
uv run pytest -v
```

Frontend telemetry unit tests:

```bash
cd frontend-tests
npm install
npm test
```

UI telemetry runtime code imports shared helpers from:

- `llama_manager/ui/chat_telemetry.js`
