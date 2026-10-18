#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python sync_public.py
python validate_vis.py
VIS_PORT="${VIS_PORT:-18080}" exec python app.py
