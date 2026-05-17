# How To Use Llama Manager

This guide shows how to run Llama Manager as local `llama.cpp` agents and, optionally, a central controller.

## 1. Install

From this project directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

For a Windows-only checklist and troubleshooting flow, see [Windows Install And Troubleshooting](windows-install.md).

## 2. Create An Agent Config

Start from:

```bash
cp config.example.yaml config.yaml
```

Example Mac agent:

```yaml
mode: agent
llama_server_bin: /Users/{user_name}/Apps/llama.cpp/build/bin/llama-server
llama_cpp_dir: /Users/{user_name}/Apps/llama.cpp
python_bin: /Users/{user_name}/Apps/llama.cpp/.venv/bin/python
hf_models_dirs:
  - /Users/{user_name}/models
log_dir: ./logs
agent_api_key: local-agent-key
agent_worker_enabled: false

models:
  qwen-coder:
    path: /Users/{user_name}/models/qwen-coder.gguf
    port: 8081
    ctx: 16384
    gpu_layers: 999
    host: 0.0.0.0
    reasoning: auto
    reasoning_budget: 2048
    extra_args: []
    supports_json_schema: false
    supports_grammar: false
```

Legacy single-root config still works:

```yaml
hf_models_dir: /Volumes/4TB/HFModels
```

If `hf_models_dirs` is present, it is used instead of the legacy single-root field.

## 3. Create The First Admin Key

Before creating admin keys or starting the service, apply migrations:

```bash
export LLAMA_MANAGER_CONFIG=config.yaml
alembic -x db=controller upgrade controller@head
alembic -x db=auth upgrade auth@head
alembic -x db=audit upgrade audit@head
alembic -x db=chat_sessions upgrade chat_sessions@head
```

Before using the UI or protected API routes, create an admin key:

```bash
uv run python -m llama_manager.auth --config config.yaml create-admin {user_name}
```

The command stores only a hash in `log_dir/auth_store.db` and prints the raw key once. Use that key in the UI login form or as the `X-Llama-Manager-Key` header for API requests. There is no `dev` fallback login.

## 4. Start An Agent

```bash
LLAMA_MANAGER_CONFIG=config.yaml uvicorn llama_manager.main:app --host 0.0.0.0 --port 9000
```

On Windows PowerShell:

```powershell
$env:LLAMA_MANAGER_CONFIG = "config.yaml"
uvicorn llama_manager.main:app --host 0.0.0.0 --port 9000
```

Check health:

```bash
curl http://127.0.0.1:9000/health
```

Local Mac helper scripts:

```bash
scripts/start_server.sh
scripts/stop_server.sh
```

## 5. Control Models On An Agent

```bash
curl http://127.0.0.1:9000/models
curl -X POST http://127.0.0.1:9000/models/qwen-coder/start
curl -X POST http://127.0.0.1:9000/models/qwen-coder/stop
curl -X POST http://127.0.0.1:9000/models/qwen-coder/restart
curl "http://127.0.0.1:9000/logs/qwen-coder?lines=200"
```

The underlying OpenAI-compatible endpoint remains on the model port:

```bash
curl http://127.0.0.1:8081/health
```

## 6. Use Chat Features

Basic API call:

```bash
curl -X POST http://127.0.0.1:9000/chat/qwen-coder \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Say hello in one sentence."}
    ],
    "temperature": 0.7,
    "max_tokens": 128
  }'
```

The Chat UI supports:

- advanced sampling controls (`top_p`, `top_k`, `min_p`, `repeat_penalty`, `seed`, `stop`, `n_predict` alias behavior)
- structured output mode (`None`, `JSON Schema`, `Grammar`) with mutual exclusion and client-side validation
- per-model capability gating from `GET /chat/capabilities/{model}`
- capability source metadata (`default`, `config_flag`, `extra_args`) in the feature matrix and capabilities detail panel
- capability debug tools: full JSON detail + `Copy Capabilities JSON`
- session save/load with persisted advanced defaults, including structured mode and schema/grammar text

Useful chat endpoints:

- `POST /chat/{model}`
- `POST /chat/{model}/stream`
- `GET /chat/capabilities/{model}`
- `POST /chat/{model}/inspect`
- `POST /chat/{model}/embeddings`
- `GET /chat/{model}/kv/slots`
- `POST /chat/{model}/kv/slots/{slot_id}`
- `GET /chat/{model}/kv/capabilities`
- `GET|POST|DELETE /chat/sessions...`

## 7. Add Existing GGUFs As Runnable Models

Scan and register existing GGUF files:

```bash
curl http://127.0.0.1:9000/library/ggufs
curl -X POST http://127.0.0.1:9000/library/ggufs/{file_id}/add-model \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gemma-4-E2B-it",
    "port": 8080,
    "ctx": 8192,
    "gpu_layers": 999,
    "host": "0.0.0.0"
  }'
```

## 8. Convert HF Models To GGUF

Set config values on the agent with HF models:

```yaml
hf_models_dirs:
  - /Volumes/4TB/HFModels
  - /Volumes/4TB/OtherModels
llama_cpp_dir: /Users/{user_name}/Apps/llama.cpp
python_bin: /Users/{user_name}/Apps/llama.cpp/.venv/bin/python
```

Use:

```bash
curl http://127.0.0.1:9000/conversions/models
curl -X POST http://127.0.0.1:9000/conversions/qwen2.5-7b-instruct/start
curl "http://127.0.0.1:9000/conversions/qwen2.5-7b-instruct/logs?lines=200"
```

If conversion logs show missing packages (for example `ModuleNotFoundError: No module named 'transformers'`), point `python_bin` at the correct llama.cpp venv Python.

## 9. Quantize Existing GGUFs

Use:

```bash
curl http://127.0.0.1:9000/quantizations/files
curl -X POST http://127.0.0.1:9000/quantizations/{file_id}/start \
  -H "Content-Type: application/json" \
  -d '{"type":"Q4_K_M"}'
curl "http://127.0.0.1:9000/quantizations/{file_id}/logs?lines=200"
```

## 10. Create A Controller Config (Optional)

```yaml
mode: controller
log_dir: ./logs

nodes:
  windows-2080ti:
    url: http://192.168.1.74:9000
    api_key: windows-agent-key-if-enabled
    verify_tls: true

controller_registration_key: shared-registration-key
node_heartbeat_timeout_seconds: 90
```

Run controller (different port from local agent):

```bash
LLAMA_MANAGER_CONFIG=controller.yaml uvicorn llama_manager.main:app --host 0.0.0.0 --port 9100
```

Controller endpoints include node inventory/proxy plus orchestration (`/jobs`, node `/work/*`, stats, retention, archive export). In the UI, use the Nodes page to inspect registered agents, heartbeat freshness, reported models, and remote model Start/Stop/Restart/Logs actions.

## 11. Run The Controller On A Raspberry Pi

Raspberry Pi integration is a good fit for the always-on controller role. The Pi runs `mode: controller`, owns node inventory and durable orchestration state, and each agent machine points its `controller_url` at the Pi.

```bash
cp raspberry-pi-controller.config.example.yaml raspberry-pi-controller.config.yaml
export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY=...
export LLAMA_MANAGER_MAC_MINI_AGENT_API_KEY=...
export LLAMA_MANAGER_LINUX_2080TI_AGENT_API_KEY=...
LLAMA_MANAGER_CONFIG=raspberry-pi-controller.config.yaml uvicorn llama_manager.main:app --host 0.0.0.0 --port 9137
```

Pi controller config essentials:

```yaml
mode: controller
log_dir: /home/{user_name}/llama-manager/logs
controller_registration_key: ${LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY}
node_heartbeat_timeout_seconds: 90

nodes:
  mac-mini:
    url: http://MAC_MINI_IP:9137
    api_key: ${LLAMA_MANAGER_MAC_MINI_AGENT_API_KEY}
    verify_tls: true
  linux-2080ti:
    url: http://LINUX_2080TI_IP:9137
    api_key: ${LLAMA_MANAGER_LINUX_2080TI_AGENT_API_KEY}
    verify_tls: true
```

On each agent, set `controller_url: http://RASPBERRY_PI_IP:9137` and `controller_registration_key_outbound` to the same value as the Pi controller's `controller_registration_key`. If the agent worker is enabled, make sure the agent's `agent_api_key` matches the corresponding `nodes.<name>.api_key` value on the Pi controller.

## 12. Enable Agent Worker Jobs

The controller owns durable jobs. Agents execute jobs only when the worker is explicitly enabled.

Controller config:

```yaml
mode: controller
log_dir: ./logs

nodes:
  mac-agent:
    url: http://127.0.0.1:9000
    api_key: local-agent-key
    verify_tls: true
```

Worker APIs fail closed: the controller only accepts `/nodes/{node}/work/*` requests for registered nodes that have an `api_key`, and the request must send that key in `X-Llama-Manager-Key`.

Agent config:

```yaml
mode: agent
controller_url: http://127.0.0.1:9100
node_name: mac-agent
agent_url: http://127.0.0.1:9000
agent_api_key: local-agent-key
controller_registration_key_outbound: local-agent-key
agent_worker_enabled: true
agent_worker_poll_interval_seconds: 2
agent_worker_max_jobs: 1
agent_worker_labels:
  platform: mac
agent_worker_capacity:
  vram_gb: 24
```

Create a typed generation job on the controller:

```bash
curl -X POST http://127.0.0.1:9100/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "llm.generate",
    "target": "node:mac-agent",
    "payload": {
      "model": "qwen-coder",
      "messages": [
        {"role": "user", "content": "Say hello in one sentence."}
      ],
      "target": "local",
      "max_tokens": 64,
      "requirements": {
        "labels": {"platform": "mac"},
        "capacity": {"vram_gb": 8}
      }
    }
  }'
```

Watch durable events:

```bash
curl http://127.0.0.1:9100/jobs/{job_id}/events
```

Watch live events with SSE:

```bash
curl -N http://127.0.0.1:9100/jobs/{job_id}/events/stream
```

Cancel cooperatively:

```bash
curl -X POST http://127.0.0.1:9100/jobs/{job_id}/cancel
```

Queued jobs cancel immediately. Assigned or running jobs move to `cancel_requested`; workers check before and after local model execution and then report a terminal state.

The only typed worker contract in this milestone is `llm.generate`. Additional contracts such as embeddings, quantization, conversion, or tool/workflow execution should be designed separately before implementation.

## 13. Run Tests

Backend/API:

```bash
uv run pytest -v
```

Frontend telemetry unit tests:

```bash
cd frontend-tests
npm install
npm test
```

Production UI telemetry helpers are in:

```text
llama_manager/ui/chat_telemetry.js
```

## 13. Alembic-Managed Persistence

Legacy sqlite store code paths were removed after migration parity validation.
The app now always uses SQLAlchemy-managed persistence implementations across
all databases.

Safe startup procedure:

1. Run migrations for all targets:
```bash
alembic -x db=controller upgrade controller@head
alembic -x db=auth upgrade auth@head
alembic -x db=audit upgrade audit@head
alembic -x db=chat_sessions upgrade chat_sessions@head
```
2. Start the app normally.
3. Run focused smoke checks for auth, audit, chat sessions, and jobs.

Rollback procedure:

1. Roll back to a previous application version.
2. Keep the database at its current Alembic head unless a schema rollback is explicitly required.
3. Re-run smoke checks.
