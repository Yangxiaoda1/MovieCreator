#!/usr/bin/env bash
# 一次性安装：conda 环境 + ComfyUI + MiniMax-H3 Turbo 节点（+ 可选 HunyuanVideo-Foley）
# 用法：bash setup/install.sh [--with-foley]
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV="${CONDA_ENV:-minimaxh3}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"

# 验证过的版本
COMFYUI_COMMIT="15eb748b3ec5f8a0a2d470b7fb280e2d7579f916"
H3_NODE_COMMIT="4274783a23afcfdbea3b4876cb79effd6c510785"
FOLEY_COMMIT="df7b005b5023df2a9b73e1d66dd51d452799884e"

WITH_FOLEY=0
[[ "${1:-}" == "--with-foley" ]] && WITH_FOLEY=1

cd "$WORKSPACE"
command -v conda >/dev/null || { echo "需要 conda（miniconda3）" >&2; exit 1; }
for bin in git ffmpeg ffprobe tmux; do
  command -v "$bin" >/dev/null || { echo "缺少系统命令: $bin" >&2; exit 1; }
done

CONDA_BASE="$(conda info --base)"
# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"

echo "== [1/5] conda env: $CONDA_ENV"
conda env list | grep -qE "^${CONDA_ENV}\s" || conda create -y -n "$CONDA_ENV" python=3.11
conda activate "$CONDA_ENV"
pip install --upgrade pip
pip install torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 --index-url "$TORCH_INDEX"

echo "== [2/5] ComfyUI @ $COMFYUI_COMMIT"
[[ -d ComfyUI/.git ]] || git clone https://github.com/comfyanonymous/ComfyUI.git ComfyUI
git -C ComfyUI fetch --quiet origin
git -C ComfyUI checkout --quiet "$COMFYUI_COMMIT"
pip install -r ComfyUI/requirements.txt

echo "== [3/5] ComfyUI-MiniMax-H3-Turbo @ $H3_NODE_COMMIT"
NODE_DIR=ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo
[[ -d "$NODE_DIR/.git" ]] || git clone https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git "$NODE_DIR"
git -C "$NODE_DIR" fetch --quiet origin
git -C "$NODE_DIR" checkout --quiet "$H3_NODE_COMMIT"

echo "== [4/5] pipeline 依赖"
pip install -r setup/requirements.txt

mkdir -p .secrets output logs run
if [[ ! -f .secrets/aimovie_api.env ]]; then
  cp setup/aimovie_api.env.example .secrets/aimovie_api.env
  sed -i "s#^export CONDA_ACTIVATE=.*#export CONDA_ACTIVATE=\"$CONDA_BASE/bin/activate\"#" .secrets/aimovie_api.env
  sed -i "s#^export CONDA_ENV=.*#export CONDA_ENV=\"$CONDA_ENV\"#" .secrets/aimovie_api.env
  chmod 600 .secrets/aimovie_api.env
  echo "已生成 .secrets/aimovie_api.env，请填写 gpt-image-2 与 CloudBase 配置"
fi

if [[ "$WITH_FOLEY" == 1 ]]; then
  echo "== [5/5] HunyuanVideo-Foley @ $FOLEY_COMMIT（独立环境 aifilm-foley）"
  mkdir -p third_party
  [[ -d third_party/HunyuanVideo-Foley/.git ]] || \
    git clone https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley.git third_party/HunyuanVideo-Foley
  git -C third_party/HunyuanVideo-Foley fetch --quiet origin
  git -C third_party/HunyuanVideo-Foley checkout --quiet "$FOLEY_COMMIT"
  conda env list | grep -qE "^aifilm-foley\s" || conda create -y -n aifilm-foley python=3.11
  conda activate aifilm-foley
  pip install --upgrade pip
  pip install torch torchvision torchaudio --index-url "$TORCH_INDEX"
  pip install -r third_party/HunyuanVideo-Foley/requirements.txt
  conda activate "$CONDA_ENV"
else
  echo "== [5/5] 跳过 HunyuanVideo-Foley（需要时：bash setup/install.sh --with-foley）"
fi

echo "安装完成。下一步：python setup/download_models.py"
