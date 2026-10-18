#!/usr/bin/env bash
set -uo pipefail
WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$WORKSPACE/run/comfyui"
shopt -s nullglob
for pid_file in "$PID_DIR"/*.pid; do
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" && echo "stopped $(basename "$pid_file" .pid) pid=$pid"
  fi
  rm -f "$pid_file"
done
