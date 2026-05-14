#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="${LLAMA_MANAGER_PID_FILE:-$ROOT_DIR/.llama_manager.pid}"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found at $PID_FILE."
  exit 0
fi

PID="$(cat "$PID_FILE")"
if ! kill -0 "$PID" 2>/dev/null; then
  echo "Process $PID is not running. Removing stale PID file."
  rm -f "$PID_FILE"
  exit 0
fi

kill "$PID"

for _ in {1..30}; do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "Stopped Llama Manager process $PID."
    exit 0
  fi
  sleep 0.2
done

echo "Process $PID did not stop after SIGTERM; sending SIGKILL."
kill -9 "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "Stopped Llama Manager process $PID."

