#!/usr/bin/env bash
# 启动多实例 ComfyUI：每张卡一个端口，供 H3 候选 / SeedVR2 并行；另起 8192（ACE-Step 配乐，也可跑 H3 / SeedVR2）。
#   GPUS="0 1 2 3"   -> 8188 8189 8190 8191
#   ACE_GPU=2        -> 8192（与 8190 共卡；显存紧张时改成空闲卡，或 ACE_GPU=none 不启动）
# ComfyUI 的输出目录固定为 <WORKSPACE>/output，pipeline 依赖这个位置取回结果。
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPUS="${GPUS:-0 1 2 3}"
BASE_PORT="${BASE_PORT:-8188}"
ACE_GPU="${ACE_GPU:-2}"
ACE_PORT="${ACE_PORT:-8192}"
CONDA_ENV="${CONDA_ENV:-minimaxh3}"

LOG_DIR="$WORKSPACE/logs/comfyui"
PID_DIR="$WORKSPACE/run/comfyui"
USER_ROOT="$WORKSPACE/.comfyui_users"
mkdir -p "$WORKSPACE/output" "$LOG_DIR" "$PID_DIR" "$USER_ROOT"

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

launch() {
  local gpu="$1" port="$2" extra="${3:-}"
  local name="gpu${gpu}_port${port}"
  if ss -ltn 2>/dev/null | grep -q ":${port}\b"; then
    echo "port ${port} already listening, skip"
    return
  fi
  mkdir -p "$USER_ROOT/$name"
  (
    cd "$WORKSPACE/ComfyUI"
    # shellcheck disable=SC2086
    CUDA_VISIBLE_DEVICES="$gpu" exec python main.py \
      --listen 127.0.0.1 --port "$port" \
      --output-directory "$WORKSPACE/output" \
      --user-directory "$USER_ROOT/$name" \
      --temp-directory "/tmp/aifilm_comfy_${port}" \
      --preview-method none $extra
  ) >"$LOG_DIR/$name.log" 2>&1 &
  echo $! >"$PID_DIR/$name.pid"
  echo "started gpu=${gpu} port=${port} log=logs/comfyui/${name}.log"
}

i=0
for gpu in $GPUS; do
  launch "$gpu" $((BASE_PORT + i))
  i=$((i + 1))
done
[[ "$ACE_GPU" != "none" ]] && launch "$ACE_GPU" "$ACE_PORT"

echo "waiting for ComfyUI..."
ports=()
i=0; for _ in $GPUS; do ports+=($((BASE_PORT + i))); i=$((i + 1)); done
[[ "$ACE_GPU" != "none" ]] && ports+=("$ACE_PORT")
for port in "${ports[@]}"; do
  ok=0
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 3 "http://127.0.0.1:${port}/system_stats" >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
  done
  [[ $ok == 1 ]] && echo "OK   http://127.0.0.1:${port}" || echo "FAIL http://127.0.0.1:${port}（看 logs/comfyui/）"
done
