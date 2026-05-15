#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${LLAMA_MANAGER_HOST:-0.0.0.0}"
PORT="${LLAMA_MANAGER_PORT:-9137}"
DEFAULT_CONFIG="$ROOT_DIR/config.example.yaml"
if [[ -f "$ROOT_DIR/config.yaml" ]]; then
  DEFAULT_CONFIG="$ROOT_DIR/config.yaml"
fi
CONFIG="${LLAMA_MANAGER_CONFIG:-$DEFAULT_CONFIG}"
PID_FILE="${LLAMA_MANAGER_PID_FILE:-$ROOT_DIR/.llama_manager.pid}"
LOG_FILE="${LLAMA_MANAGER_LOG_FILE:-$ROOT_DIR/logs/llama_manager_uvicorn.log}"

cd "$ROOT_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "Llama Manager is already running on PID $PID."
    echo "URL: http://$HOST:$PORT"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

LLAMA_MANAGER_CONFIG="$CONFIG" "$PYTHON" - <<'PY'
from llama_manager.main import create_app

create_app()
PY

LLAMA_MANAGER_CONFIG="$CONFIG" nohup "$PYTHON" -m uvicorn llama_manager.main:app \
  --host "$HOST" \
  --port "$PORT" \
  >"$LOG_FILE" 2>&1 &

PID="$!"
echo "$PID" > "$PID_FILE"

echo "Started Llama Manager on PID $PID."
echo "URL: http://$HOST:$PORT"
echo "Config: $CONFIG"
echo "Log: $LOG_FILE"
