#!/usr/bin/env bash
# Amazing Hand 手势控制一键启动脚本
# 把所有环境变量和 dora 命令封装好，免得每次手敲一长串。
#
# 用法：
#   ./run_handtracking.sh sim         # 只跑仿真（摄像头+MuJoCo，不碰硬件）
#   ./run_handtracking.sh real        # 接真手（仿真+真机械手）
#   ./run_handtracking.sh build sim   # 第一次：先 build 仿真依赖再跑
#   ./run_handtracking.sh build real  # 第一次：先 build 真手(含编译Rust)再跑
#   ./run_handtracking.sh stop        # 停止所有节点
#
# 详细说明见 docs/AmazingHand_手势控制小白手册_中文.md

set -e
cd "$(dirname "$0")"   # 切到 Demo 目录

# ---- 环境（清华镜像 + 各工具 PATH）----
source "$HOME/.cargo/env" 2>/dev/null || true
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
export PKG_CONFIG_PATH="$HOME/.local/lib/pkgconfig:$PKG_CONFIG_PATH"
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export DISPLAY="${DISPLAY:-:0}"

usage() { sed -n '2,16p' "$0"; exit 1; }

# ---- 解析参数 ----
DO_BUILD=0
MODE=""
for a in "$@"; do
  case "$a" in
    build) DO_BUILD=1 ;;
    sim|simu) MODE="simu" ;;
    real) MODE="real" ;;
    stop) dora destroy 2>/dev/null || true
          pkill -9 -f "target/debug/AHControl" 2>/dev/null || true
          pkill -9 -f "AHSimulation/AHSimulation/mj_mink" 2>/dev/null || true
          pkill -9 -f "HandTracking/HandTracking/main.py" 2>/dev/null || true
          echo "✅ 已停止所有手势控制节点"; exit 0 ;;
    *) usage ;;
  esac
done
[ -z "$MODE" ] && usage

FLOW="dataflow_tracking_${MODE}.yml"

# ---- 首次需要 venv ----
if [ ! -d .venv ]; then
  echo "→ 创建 Python 3.12 虚拟环境（首次）..."
  uv venv --python 3.12
fi

# ---- build（首次或加了 build 参数）----
if [ "$DO_BUILD" = "1" ]; then
  echo "→ 构建 $FLOW （首次较久，下载依赖/编译 Rust）..."
  dora build "$FLOW" --uv
fi

# ---- 运行 ----
echo "→ 启动 dora 守护进程..."
dora up
echo "→ 运行 $FLOW ..."
echo "  把手伸到摄像头前；停止按 Ctrl-C 或另开终端跑 ./run_handtracking.sh stop"
exec dora run "$FLOW" --uv
