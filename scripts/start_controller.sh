#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/rsmith/Apps/llama-manager"
CONFIG="$APP_DIR/config.yaml"
HOST="0.0.0.0"
PORT="9137"

cd "$APP_DIR"

export LLAMA_MANAGER_CONFIG="$CONFIG"

mkdir -p "$APP_DIR/logs"

echo "Using config: $LLAMA_MANAGER_CONFIG"
echo "Running migrations..."
.venv/bin/alembic -x db=controller upgrade controller@head
.venv/bin/alembic -x db=auth upgrade auth@head
.venv/bin/alembic -x db=audit upgrade audit@head
.venv/bin/alembic -x db=chat_sessions upgrade chat_sessions@head

echo "Starting Llama Manager controller on http://$HOST:$PORT"
exec .venv/bin/uvicorn llama_manager.main:app --host "$HOST" --port "$PORT"

