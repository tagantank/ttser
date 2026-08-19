#!/usr/bin/env bash
set -euo pipefail

export LD_LIBRARY_PATH="/app/lib/ttser:${LD_LIBRARY_PATH:-}"

exec /app/bin/ttser "$@"
