#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/agent.config.yaml"
ENV_FILE="$ROOT_DIR/.llama-manager.env"
TEMPLATE="$ROOT_DIR/linux-agent.config.example.yaml"
NODE_NAME="$(hostname -s 2>/dev/null || hostname)"
CONTROLLER_URL=""
AGENT_URL=""
HOST="0.0.0.0"
PORT="9137"
FORCE="false"
RUN_SMOKE="false"
SKIP_RUNTIME_PATH_CHECK="false"

usage() {
  cat <<'USAGE'
Usage: scripts/onboard_agent.sh --controller-url URL --agent-url URL [options]

Create and validate an agent config, generate the agent API key when needed,
and print the controller-side values needed to register this node.

Options:
  --config PATH                 Agent config to create/update. Default: ./agent.config.yaml
  --env-file PATH               Local secrets file to create/update. Default: ./.llama-manager.env
  --template PATH               Agent template. Default: ./linux-agent.config.example.yaml
  --node NAME                   Agent node name. Default: local hostname
  --controller-url URL          Controller URL, for example http://192.168.1.104:9137
  --agent-url URL               URL the controller should use to reach this agent
  --host HOST                   Host used in the printed start command. Default: 0.0.0.0
  --port PORT                   Port used in the printed start command. Default: 9137
  --run-smoke                   Run scripts/linux_agent_smoke.py after config creation.
  --skip-runtime-path-check     Pass through to the smoke test.
  --force                       Overwrite --config if it already exists.
  -h, --help                    Show this help.

Required environment:
  LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND must match the controller's
  LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --template)
      TEMPLATE="$2"
      shift 2
      ;;
    --node)
      NODE_NAME="$2"
      shift 2
      ;;
    --controller-url)
      CONTROLLER_URL="$2"
      shift 2
      ;;
    --agent-url)
      AGENT_URL="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --run-smoke)
      RUN_SMOKE="true"
      shift
      ;;
    --skip-runtime-path-check)
      SKIP_RUNTIME_PATH_CHECK="true"
      shift
      ;;
    --force)
      FORCE="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "$CONTROLLER_URL" || -z "$AGENT_URL" ]]; then
  echo "--controller-url and --agent-url are required." >&2
  usage >&2
  exit 2
fi

if [[ -z "${LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND:-}" ]]; then
  echo "LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND is required." >&2
  echo "Set it to the controller's LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY." >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Agent template not found: $TEMPLATE" >&2
  exit 1
fi

if [[ -z "${LLAMA_MANAGER_AGENT_API_KEY:-}" ]]; then
  AGENT_API_KEY="$(scripts/generate_api_key.py)"
  export LLAMA_MANAGER_AGENT_API_KEY="$AGENT_API_KEY"
  echo "Generated LLAMA_MANAGER_AGENT_API_KEY for this shell."
else
  AGENT_API_KEY="$LLAMA_MANAGER_AGENT_API_KEY"
  echo "Using existing LLAMA_MANAGER_AGENT_API_KEY from the environment."
fi

if [[ -f "$CONFIG" && "$FORCE" != "true" ]]; then
  echo "Config already exists: $CONFIG"
  echo "Use --force to overwrite it, or pass --config for a different path."
else
  mkdir -p "$(dirname "$CONFIG")"
  sed \
    -e "s|{user_name}|${USER:-llama-manager}|g" \
    -e "s|node_name: .*|node_name: $NODE_NAME|g" \
    -e "s|controller_url: .*|controller_url: $CONTROLLER_URL|g" \
    -e "s|agent_url: .*|agent_url: $AGENT_URL|g" \
    "$TEMPLATE" > "$CONFIG"
  echo "Wrote agent config: $CONFIG"
fi

mkdir -p logs

PYTHON="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
fi

upsert_env() {
  local key="$1"
  local value="$2"
  "$PYTHON" - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import shlex
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
line = f"export {key}={shlex.quote(value)}\n"
lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
prefix = f"export {key}="
updated = False
for index, existing in enumerate(lines):
    if existing.startswith(prefix):
        lines[index] = line
        updated = True
        break
if not updated:
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.append(line)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("".join(lines), encoding="utf-8")
path.chmod(0o600)
PY
}

LLAMA_MANAGER_CONFIG="$CONFIG" "$PYTHON" - <<'PY'
from llama_manager.core.config import load_config

config = load_config()
if config.mode != "agent":
    raise SystemExit(f"Expected agent mode, got {config.mode!r}")
if not config.node_name:
    raise SystemExit("node_name is required")
if not config.controller_url:
    raise SystemExit("controller_url is required")
if not config.agent_url:
    raise SystemExit("agent_url is required")
if not config.agent_api_key:
    raise SystemExit("agent_api_key is required")
if not config.controller_registration_key_outbound:
    raise SystemExit("controller_registration_key_outbound is required")
print(f"Agent config OK: {config.config_source}")
print(f"Node: {config.node_name}")
print(f"Controller URL: {config.controller_url}")
print(f"Agent URL: {config.agent_url}")
PY

if [[ "$RUN_SMOKE" == "true" ]]; then
  SMOKE_ARGS=(--config "$CONFIG" --node "$NODE_NAME" --host "$HOST" --port "$PORT")
  if [[ "$SKIP_RUNTIME_PATH_CHECK" == "true" ]]; then
    SMOKE_ARGS+=(--skip-runtime-path-check)
  fi
  scripts/linux_agent_smoke.py "${SMOKE_ARGS[@]}"
fi

upsert_env "LLAMA_MANAGER_CONFIG" "$CONFIG"
upsert_env "LLAMA_MANAGER_AGENT_API_KEY" "$AGENT_API_KEY"
upsert_env "LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND" "$LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND"
upsert_env "LLAMA_MANAGER_HOST" "$HOST"
upsert_env "LLAMA_MANAGER_PORT" "$PORT"

cat <<EOF

Agent onboarding complete.

Local secrets were written to:
  $ENV_FILE

Add or verify this node on the controller:
  nodes:
    $NODE_NAME:
      url: $AGENT_URL
      api_key: $AGENT_API_KEY
      verify_tls: true

Start the agent:
  scripts/start_agent.sh
EOF
