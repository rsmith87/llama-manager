#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/config.yaml"
ENV_FILE="$ROOT_DIR/.llama-manager.env"
TEMPLATE=""
HOST="0.0.0.0"
PORT="9137"
ADMIN_USER="${USER:-admin}"
FORCE="false"
RUN_MIGRATIONS="true"

usage() {
  cat <<'USAGE'
Usage: scripts/onboard_controller.sh [options]

Create and validate a controller config, generate a controller registration key,
run controller/auth/audit/chat-session migrations, and print startup commands.

Options:
  --config PATH          Controller config to create/update. Default: ./config.yaml
  --env-file PATH        Local secrets file to create/update. Default: ./.llama-manager.env
  --template PATH        Optional controller template to copy instead of generating a portable config.
  --host HOST            Host used in the printed start command. Default: 0.0.0.0
  --port PORT            Port used in the printed start command. Default: 9137
  --admin-user NAME      Admin key username shown in the create-admin command. Default: $USER
  --skip-migrations      Do not run Alembic migrations.
  --force                Overwrite --config if it already exists.
  -h, --help             Show this help.
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
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --admin-user)
      ADMIN_USER="$2"
      shift 2
      ;;
    --skip-migrations)
      RUN_MIGRATIONS="false"
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

cd "$ROOT_DIR"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -n "$TEMPLATE" && ! -f "$TEMPLATE" ]]; then
  echo "Controller template not found: $TEMPLATE" >&2
  exit 1
fi

if [[ -f "$CONFIG" && "$FORCE" != "true" ]]; then
  echo "Config already exists: $CONFIG"
  echo "Use --force to overwrite it, or pass --config for a different path."
else
  mkdir -p "$(dirname "$CONFIG")"
  if [[ -n "$TEMPLATE" ]]; then
    sed "s|{user_name}|${USER:-llama-manager}|g" "$TEMPLATE" > "$CONFIG"
  else
    cat > "$CONFIG" <<'YAML'
mode: controller
log_dir: ./logs

controller_registration_key: ${LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY}
node_heartbeat_timeout_seconds: 90

controller_db_url: sqlite+pysqlite:///./logs/controller_state.db
auth_db_url: sqlite+pysqlite:///./logs/auth_store.db
audit_db_url: sqlite+pysqlite:///./logs/audit_events.db
chat_sessions_db_url: sqlite+pysqlite:///./logs/chat_sessions.db

controller_instance_id: local-controller
controller_leader_lease_seconds: 60
controller_retention_days: 14
controller_archive_retention_days: 30
controller_archive_dir: ./logs/archives

nodes: {}
YAML
  fi
  echo "Wrote controller config: $CONFIG"
fi

if [[ -z "${LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY:-}" ]]; then
  CONTROLLER_REGISTRATION_KEY="$(scripts/generate_api_key.py)"
  export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY="$CONTROLLER_REGISTRATION_KEY"
  echo "Generated LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY for this shell."
else
  CONTROLLER_REGISTRATION_KEY="$LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY"
  echo "Using existing LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY from the environment."
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
if config.mode != "controller":
    raise SystemExit(f"Expected controller mode, got {config.mode!r}")
if not config.controller_registration_key:
    raise SystemExit("controller_registration_key is required")
print(f"Controller config OK: {config.config_source}")
print(f"Configured nodes: {len(config.nodes)}")
PY

if [[ "$RUN_MIGRATIONS" == "true" ]]; then
  for db in controller auth audit chat_sessions; do
    LLAMA_MANAGER_CONFIG="$CONFIG" "$PYTHON" -m alembic -x "db=$db" upgrade "${db}@head"
  done
fi

upsert_env "LLAMA_MANAGER_CONFIG" "$CONFIG"
upsert_env "LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY" "$CONTROLLER_REGISTRATION_KEY"
upsert_env "LLAMA_MANAGER_HOST" "$HOST"
upsert_env "LLAMA_MANAGER_PORT" "$PORT"

if [[ "$RUN_MIGRATIONS" == "true" && -z "${LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY:-}" ]]; then
  ADMIN_OUTPUT="$(LLAMA_MANAGER_CONFIG="$CONFIG" "$PYTHON" -m llama_manager.auth --config "$CONFIG" create-admin "$ADMIN_USER")"
  echo "$ADMIN_OUTPUT"
  CONTROLLER_ADMIN_API_KEY="$(printf '%s\n' "$ADMIN_OUTPUT" | awk -F': ' '/^API key: / {print $2}')"
  if [[ -n "$CONTROLLER_ADMIN_API_KEY" ]]; then
    export LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY="$CONTROLLER_ADMIN_API_KEY"
    upsert_env "LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY" "$CONTROLLER_ADMIN_API_KEY"
  fi
elif [[ -n "${LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY:-}" ]]; then
  upsert_env "LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY" "$LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY"
  echo "Using existing LLAMA_MANAGER_CONTROLLER_ADMIN_API_KEY from $ENV_FILE or the environment."
else
  echo "Skipped admin API key creation because --skip-migrations was used."
fi

cat <<EOF

Controller onboarding complete.

Local secrets were written to:
  $ENV_FILE

Give this controller-owned registration key to agents:
  export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY='$CONTROLLER_REGISTRATION_KEY'

Start the controller:
  scripts/start_server.sh

Agents should use:
  controller_url: http://<controller-host>:$PORT
  controller_registration_key_outbound: \${LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND}
EOF
