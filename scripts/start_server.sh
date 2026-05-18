#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "scripts/start_server.sh is deprecated; use scripts/start_agent.sh for agent mode." >&2
exec "$ROOT_DIR/scripts/start_agent.sh" "$@"
