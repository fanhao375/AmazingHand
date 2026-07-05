#!/usr/bin/env bash
# =====================================================================
# 生成「AmazingHand-小白包.zip」—— 一键把控制台打包给小白用
#   用法：bash 打包.sh
#   产物：项目根目录下 AmazingHand-小白包.zip
# =====================================================================
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE="$(mktemp -d)/AmazingHand-小白包"
mkdir -p "$STAGE"

# 顶层：启动器、安装脚本、说明
cp "$HERE/打开控制台.sh"        "$STAGE/"
cp "$HERE/install.sh"           "$STAGE/安装.sh"
cp "$HERE/使用说明_控制台UI.md" "$STAGE/"

# 控制程序（只带需要的）
mkdir -p "$STAGE/PythonExample"
for f in AmazingHand_GUI.py AmazingHand_Calib.py AmazingHand_SetID.py \
         AmazingHand_RPS.py AmazingHand_Demo_NoDeps.py calibration.txt README.md; do
  cp "$HERE/PythonExample/$f" "$STAGE/PythonExample/"
done

# 手势控制（排除构建产物）
mkdir -p "$STAGE/Demo"
rsync -a --exclude '__pycache__' --exclude '.venv' --exclude 'target' \
      --exclude 'out' --exclude '*.egg-info' "$HERE/Demo/" "$STAGE/Demo/"

# 中文手册 PDF
mkdir -p "$STAGE/docs"
cp "$HERE"/docs/*.pdf "$STAGE/docs/" 2>/dev/null || true
cp "$HERE/docs/README_资料索引_中文.md" "$STAGE/docs/" 2>/dev/null || true

chmod +x "$STAGE/打开控制台.sh" "$STAGE/安装.sh"

OUT="$HERE/AmazingHand-小白包.zip"
rm -f "$OUT"
( cd "$(dirname "$STAGE")" && zip -rq "$OUT" "AmazingHand-小白包" )
echo "✓ 已生成: $OUT ($(du -h "$OUT" | cut -f1))"
