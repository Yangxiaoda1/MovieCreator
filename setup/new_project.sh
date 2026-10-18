#!/usr/bin/env bash
# 新建项目目录：<WORKSPACE>/<项目名>/{aifilm_booklet, input/...}
#   bash setup/new_project.sh "interaction_10<剧名>"                    # 空骨架（booklet 第 00 节）
#   bash setup/new_project.sh "interaction_9<车上聊天>" --example car_chat # 从样例复现
# 项目必须直接放在 <WORKSPACE> 下：pipeline 按 ROOT.parent 找 ComfyUI/ 和 output/。
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1:?用法: new_project.sh <项目名> [--example car_chat]}"
EXAMPLE=""
[[ "${2:-}" == "--example" ]] && EXAMPLE="${3:?缺少样例名}"

DEST="$WORKSPACE/$NAME"
[[ -e "$DEST" ]] && { echo "已存在: $DEST" >&2; exit 1; }

mkdir -p "$DEST"
cp -r "$WORKSPACE/aifilm_booklet" "$DEST/aifilm_booklet"

if [[ -n "$EXAMPLE" ]]; then
  SRC="$WORKSPACE/examples/$EXAMPLE"
  [[ -d "$SRC" ]] || { echo "没有样例: $SRC" >&2; exit 1; }
  cp -r "$SRC/input" "$DEST/input"
  [[ -d "$SRC/pipeline" ]] && cp -r "$SRC/pipeline" "$DEST/pipeline"
  find "$DEST/input" -name .gitkeep -delete
else
  mkdir -p "$DEST/input/roles" "$DEST/input/scenes" "$DEST/input/other"
  cat >"$DEST/input/script.md" <<'EOF'
<在这里写剧本：角色名：台词>

严格遵循 <PROJECT_ROOT>/aifilm_booklet 中的步骤和规则，一定严格遵守，不要擅自发挥
EOF
fi
mkdir -p "$DEST/output/others"

echo "已创建 $DEST"
echo "角色素材放 input/roles/<角色名>/，场景放 input/scenes/<场景名>/，剧本写 input/script.md"
