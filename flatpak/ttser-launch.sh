#!/usr/bin/env bash
set -euo pipefail

export LD_LIBRARY_PATH="/app/lib/ttser:${LD_LIBRARY_PATH:-}"
# RADV on AMD iGPUs can DeviceLost on coopmat kernels during long AR generate.
export GGML_VK_DISABLE_COOPMAT="${GGML_VK_DISABLE_COOPMAT:-1}"
export GGML_VK_ALLOW_SYSMEM_FALLBACK="${GGML_VK_ALLOW_SYSMEM_FALLBACK:-1}"

exec /app/bin/ttser "$@"
