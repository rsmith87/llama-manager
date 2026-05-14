# Windows Install And Troubleshooting

This guide runs Llama Manager as a Windows agent. The Mac controller should only show Windows model paths when it is talking to the Windows agent and the Windows agent was started with the Windows config.

## 1. Install Python Dependencies

Open PowerShell in this repository:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

If script activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 2. Build Or Locate llama.cpp

You need a working `llama-server.exe`.

Typical llama.cpp build output paths are:

```text
C:\llama.cpp\build\bin\Release\llama-server.exe
C:\llama.cpp\build\bin\Debug\llama-server.exe
```

For quantization, Llama Manager looks for:

```text
C:\llama.cpp\build\bin\Release\llama-quantize.exe
C:\llama.cpp\build\bin\Debug\llama-quantize.exe
C:\llama.cpp\build\bin\llama-quantize.exe
```

You can also put these binaries on `PATH`.

## 3. Create config.yaml

Do not use Mac paths in the Windows agent config. Use a local Windows path for every binary and model root.

```yaml
mode: agent
llama_server_bin: C:\llama.cpp\build\bin\Release\llama-server.exe
llama_cpp_dir: C:\llama.cpp
python_bin: C:\llama.cpp\.venv\Scripts\python.exe
hf_models_dirs:
  - D:\HFModels
log_dir: .\logs

models:
  gemma4-e2b:
    path: D:\HFModels\gemma4-e2b\model.gguf
    port: 8080
    ctx: 8192
    gpu_layers: 999
    host: 0.0.0.0
```

YAML accepts unquoted Windows paths like `D:\HFModels\model.gguf`. If a path contains `#`, `: `, or other YAML-special characters, wrap it in single quotes.

## 4. Start The Windows Agent

PowerShell environment variables only apply to the current terminal:

```powershell
$env:LLAMA_MANAGER_CONFIG = "config.yaml"
uvicorn llama_manager.main:app --host 0.0.0.0 --port 9000
```

Then check it locally:

```powershell
curl.exe http://127.0.0.1:9000/health
curl.exe http://127.0.0.1:9000/models
```

If `/models` still shows Mac paths, the running process is not using the config file you edited. Stop uvicorn, set `$env:LLAMA_MANAGER_CONFIG` again in the same PowerShell window, and restart it.

## 5. Open Firewall Ports

The Mac controller needs inbound access to the Windows manager port and each model port.

For the manager:

```powershell
New-NetFirewallRule -DisplayName "Llama Manager 9000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9000
```

For a model on port 8080:

```powershell
New-NetFirewallRule -DisplayName "llama-server 8080" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080
```

## 6. Configure The Mac Controller

On the Mac controller, point the Windows node at the Windows machine IP:

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

Start the controller on a different port than any local Mac agent:

```bash
LLAMA_MANAGER_CONFIG=controller.yaml uvicorn llama_manager.main:app --host 0.0.0.0 --port 9100
```

## 7. Common Causes Of Mac Paths In The UI

- The Windows agent was launched without `$env:LLAMA_MANAGER_CONFIG = "config.yaml"`.
- The app was started from a different directory and `config.yaml` points somewhere else.
- An old uvicorn process is still running with the previous config.
- You are viewing the local Mac agent at `http://127.0.0.1:9137`, not the Windows agent or Mac controller.
- The controller config points `windows-2080ti` to a Mac URL such as `http://127.0.0.1:9000`.
- Models added through the GGUF Library are runtime-only. If you restart the manager, only models saved in `config.yaml` remain.

## 8. Quick Diagnosis

Run this on Windows:

```powershell
$env:LLAMA_MANAGER_CONFIG
curl.exe http://127.0.0.1:9000/models
```

Run this on the Mac:

```bash
curl http://WINDOWS_IP:9000/health
curl http://WINDOWS_IP:9000/models
curl http://127.0.0.1:9100/nodes/models
```

The first two Mac commands should show the Windows platform and Windows model paths. If they do not, fix the Windows agent before debugging the controller UI.

## 9. Chat Capabilities And Structured Output On Windows

The Windows agent supports the same Chat advanced controls as other platforms.

Useful capability checks:

```powershell
curl.exe http://127.0.0.1:9000/chat/capabilities/gemma4-e2b
curl.exe "http://127.0.0.1:9000/chat/gemma4-e2b/kv/capabilities?target=auto"
```

Structured output controls in the UI (`JSON Schema` / `Grammar`) are capability-gated per model. The UI now also shows a capability source indicator:

- `default`: no explicit support hints were set
- `config_flag`: support came from model config (`supports_json_schema`, `supports_grammar`)
- `extra_args`: support was inferred from `extra_args` (for example flags containing `json-schema` or `grammar`)

If needed, set explicit hints in Windows `config.yaml`:

```yaml
models:
  gemma4-e2b:
    path: D:\HFModels\gemma4-e2b\model.gguf
    port: 8080
    supports_json_schema: false
    supports_grammar: false
```

## 10. Optional Auto-Registration From Windows Agent

If you prefer agent-driven registration instead of maintaining the node list manually, add this to the Windows agent config:

```yaml
controller_url: http://MAC_CONTROLLER_IP:9100
node_name: windows-2080ti
agent_url: http://WINDOWS_IP:9000
heartbeat_interval_seconds: 30
controller_registration_key_outbound: shared-registration-key
```

Set the same `controller_registration_key` on the controller. On startup, the agent registers itself and then sends heartbeats on the configured interval.
