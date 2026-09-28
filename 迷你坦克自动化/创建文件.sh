#!/usr/bin/env bash
# create_project.sh
set -euo pipefail

PROJECT_NAME="迷你坦克自动化"   # 改成你的项目目录名
ROOT="$PWD/$PROJECT_NAME"

# 目录
DIRS=(
  "config/flows"
  "core"
  "utils"
  "截屏"
)

# 文件（相对路径）
FILES=(
  "main.py"
  "config/config.yaml"
  "config/flows/建筑升级.yaml"
  "config/flows/将领升级.yaml"
  "config/flows/将领第二次升级.yaml"
  "config/flows/将领技能精工.yaml"
  "config/flows/将领技能强化.yaml"
  "config/flows/将领技能升级.yaml"
  "config/flows/将领技能精工强化.yaml"
  "config/loader.py"
  "core/device.py"
  "core/ocr_finder.py"
  "core/keyword_matcher.py"
  "core/actions.py"
  "core/abort_checker.py"
  "core/flow_runner.py"
  "core/skill_upgrader.py"
  "utils/logger.py"
)

# 创建根目录
mkdir -p "$ROOT"

# 创建目录
for d in "${DIRS[@]}"; do
  mkdir -p "$ROOT/$d"
done

# 创建文件
for f in "${FILES[@]}"; do
  touch "$ROOT/$f"
done

# 生成 __init__.py（可选，方便当包导入）
for d in config core utils; do
  touch "$ROOT/$d/__init__.py"
done

echo "✅ 项目已创建: $ROOT"
echo
echo "结构预览:"
if command -v tree >/dev/null 2>&1; then
  tree "$ROOT"
else
  find "$ROOT" | sed "s|$ROOT|.|"
fi