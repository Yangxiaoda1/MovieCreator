#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${CONDA_ACTIVATE:-/apdcephfs_gy2/share_302507476/xiaodayang/miniconda3/bin/activate}" "${CONDA_ENV:-minimaxh3}"
exec python "$ROOT/seedvr2_upscale.py" "$@"
