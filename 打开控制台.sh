#!/usr/bin/env bash
# =====================================================================
# Amazing Hand 控制台 —— 一键打开图形界面（Linux）
#   把这个包解压后，双击本文件（或在终端里运行）即可打开控制台。
#   第一次用请先跑一次「安装.sh」装好环境。
# =====================================================================
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
GUI="$HERE/PythonExample/AmazingHand_GUI.py"

echo "==> 正在打开 Amazing Hand 控制台…"

# 1) 检查 python3
if ! command -v python3 >/dev/null; then
  echo "✗ 没找到 python3。请先运行本目录里的『安装.sh』。"
  read -rp "按回车键关闭…" _; exit 1
fi

# 2) 检查 tkinter（图形界面必须）
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "!  缺少图形界面组件 python3-tk，正在尝试安装（需要输入开机密码）…"
  if command -v apt-get >/dev/null; then
    sudo apt-get install -y python3-tk || {
      echo "✗ 自动安装失败。请手动运行：sudo apt-get install -y python3-tk"
      read -rp "按回车键关闭…" _; exit 1; }
  else
    echo "✗ 请自行安装 python3-tk 后再打开。"
    read -rp "按回车键关闭…" _; exit 1
  fi
fi

# 3) 打开控制台
cd "$HERE"
exec python3 "$GUI"
