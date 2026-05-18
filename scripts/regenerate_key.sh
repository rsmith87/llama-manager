#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.llama-manager.env"
KEY_TYPE=""
NODE_NAME="$(hostname -s 2>/dev/null || hostname)"
AGENT_URL=""
TOKEN_BYTES="32"
PREFIX="llm"

usage() {
  cat <<'USAGE'
Usage: scripts/regenerate_key.sh --type TYPE [options]

Generate a replacement key, write it to .llama-manager.env, and print the
value or config snippet needed on the other machines.

Types:
  controller-registration   Rotate LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY.
  agent-api                 Rotate LLAMA_MANAGER_AGENT_API_KEY.
  agent-registration        Rotate LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND.

Options:
  --env-file PATH           Local secrets file to update. Default: ./.llama-manager.env
  --node NAME               Agent node name for printed controller snippet. Default: hostname
  --agent-url URL           Agent URL for printed controller snippet.
  --bytes N                 Random bytes before URL-safe encoding. Default: 32
  --prefix VALUE            Key prefix. Default: llm
  -h, --help                Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)
      KEY_TYPE="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --node)
      NODE_NAME="$2"
      shift 2
      ;;
    --agent-url)
      AGENT_URL="$2"
      shift 2
      ;;
    --bytes)
      TOKEN_BYTES="$2"
      shift 2
      ;;
    --prefix)
      PREFIX="$2"
      shift 2
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

case "$KEY_TYPE" in
  controller-registration)
    ENV_KEY="LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY"
    ;;
  agent-api)
    ENV_KEY="LLAMA_MANAGER_AGENT_API_KEY"
    ;;
  agent-registration)
    ENV_KEY="LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND"
    ;;
  "")
    echo "--type is required." >&2
    usage >&2
    exit 2
    ;;
  *)
    echo "Unknown key type: $KEY_TYPE" >&2
    usage >&2
    exit 2
    ;;
esac

cd "$ROOT_DIR"

PYTHON="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
fi

NEW_KEY="$(scripts/generate_api_key.py --bytes "$TOKEN_BYTES" --prefix "$PREFIX")"

"$PYTHON" - "$ENV_FILE" "$ENV_KEY" "$NEW_KEY" <<'PY'
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

echo "Updated $ENV_KEY in $ENV_FILE"
echo

case "$KEY_TYPE" in
  controller-registration)
    cat <<EOF
New controller registration key:
  export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY='$NEW_KEY'

On each agent, update:
  export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND='$NEW_KEY'

Then restart the controller and each agent.
EOF
    ;;
  agent-api)
    cat <<EOF
New agent API key:
  export LLAMA_MANAGER_AGENT_API_KEY='$NEW_KEY'

On the controller, update this node entry:
  nodes:
    $NODE_NAME:
      url: ${AGENT_URL:-http://AGENT_IP:9137}
      api_key: $NEW_KEY
      verify_tls: true

Then restart this agent and the controller.
EOF
    ;;
  agent-registration)
    cat <<EOF
New outbound controller registration key for this agent:
  export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND='$NEW_KEY'

On the controller, update:
  export LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY='$NEW_KEY'

Then restart the controller and this agent.
EOF
    ;;
esac
