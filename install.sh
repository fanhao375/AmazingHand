#!/usr/bin/env bash
# =====================================================================
# Amazing Hand 傻瓜式安装脚本（Linux / Ubuntu）
#   一条命令装好控制这只手所需的全部环境：
#     bash install.sh              # 基础（控制/标定/GUI/跑Demo）
#     bash install.sh --with-rust  # 额外装 Rust（手势控制"真手"需要）
#
# 全程用清华镜像加速，避免直连国外超时。
# 需要 sudo 装少量系统包（会提示输密码）。
# =====================================================================
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TUNA_PIP="https://pypi.tuna.tsinghua.edu.cn/simple"
WITH_RUST=0
for a in "$@"; do [ "$a" = "--with-rust" ] && WITH_RUST=1; done

say()  { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()   { echo -e "  \033[1;32m✓\033[0m $*"; }
warn() { echo -e "  \033[1;33m!\033[0m $*"; }

# ---------------------------------------------------------------------
say "1/7 系统依赖（需要 sudo）"
SYS_PKGS="python3-pip python3-tk python3-venv pkg-config libudev-dev"
if command -v apt-get >/dev/null; then
  sudo apt-get update -qq || warn "apt update 失败，继续尝试安装"
  # shellcheck disable=SC2086
  if sudo apt-get install -y $SYS_PKGS; then ok "系统依赖已装: $SYS_PKGS"
  else warn "部分系统包安装失败，后面若报错请手动: sudo apt install $SYS_PKGS"; fi
else
  warn "非 apt 系统，请自行安装: $SYS_PKGS"
fi

# ---------------------------------------------------------------------
say "2/7 配置 pip 清华镜像"
mkdir -p ~/.config/pip
cat > ~/.config/pip/pip.conf <<EOF
[global]
index-url = $TUNA_PIP
EOF
ok "已写 ~/.config/pip/pip.conf"

# ---------------------------------------------------------------------
say "3/7 Python 工具：uv + dora-rs-cli"
python3 -m pip install --user -q -U pip uv "dora-rs-cli==0.3.13" || warn "uv/dora 安装可能失败，检查网络"
export PATH="$HOME/.local/bin:$PATH"
command -v uv   >/dev/null && ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"    || warn "uv 未就绪"
command -v dora >/dev/null && ok "dora $(dora --version 2>/dev/null | awk '{print $2}')" || warn "dora 未就绪"

# ---------------------------------------------------------------------
say "4/7 串口权限（dialout 组）"
if id -nG "$USER" | grep -qw dialout; then
  ok "已在 dialout 组"
else
  sudo usermod -aG dialout "$USER" && warn "已加入 dialout 组 —— 需【注销重新登录】才生效"
fi
PORT=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i Single_Serial | head -1)
[ -n "$PORT" ] && ok "检测到驱动板: /dev/serial/by-id/$PORT" || warn "未检测到 Waveshare 驱动板（插上再看）"

# ---------------------------------------------------------------------
say "5/7 Rust 工具链（手势控制真手用）"
if [ "$WITH_RUST" = "1" ]; then
  if command -v cargo >/dev/null; then
    ok "已有 cargo $(cargo --version 2>/dev/null | awk '{print $2}')"
  else
    export RUSTUP_DIST_SERVER=https://mirrors.tuna.tsinghua.edu.cn/rustup
    export RUSTUP_UPDATE_ROOT=https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup
    curl -fsSL "https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup/dist/x86_64-unknown-linux-gnu/rustup-init" -o /tmp/rustup-init \
      && chmod +x /tmp/rustup-init \
      && /tmp/rustup-init -y --default-toolchain stable --profile minimal \
      && ok "Rust 已装" || warn "Rust 安装失败，检查网络"
  fi
  # cargo 依赖镜像
  mkdir -p ~/.cargo
  cat > ~/.cargo/config.toml <<'EOF'
[source.crates-io]
replace-with = 'tuna'
[source.tuna]
registry = "sparse+https://mirrors.tuna.tsinghua.edu.cn/crates.io-index/"
EOF
  ok "已配 cargo 清华镜像"
else
  warn "跳过 Rust（只做控制/标定/仿真够用）。要真手手势控制请重跑: bash install.sh --with-rust"
fi

# ---------------------------------------------------------------------
say "6/7 桌面快捷方式（双击打开控制台）"
GUI="$HERE/PythonExample/AmazingHand_GUI.py"
APPDIR="$HOME/.local/share/applications"
mkdir -p "$APPDIR"
cat > "$APPDIR/amazing-hand.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Amazing Hand 控制台
Comment=控制、标定、跑Demo、手势控制
Exec=python3 "$GUI"
Terminal=false
Categories=Utility;
EOF
chmod +x "$APPDIR/amazing-hand.desktop"
ok "已创建应用菜单项『Amazing Hand 控制台』"

# ---------------------------------------------------------------------
say "7/7 完成 ✅"
cat <<EOF

下一步：
  • 打开图形控制台：   python3 "$GUI"
    （或在应用菜单里搜『Amazing Hand』）
  • 若刚加入 dialout 组：请先【注销重新登录】一次
  • 手势控制仿真：      cd Demo && ./run_handtracking.sh build sim
$( [ "$WITH_RUST" = "1" ] && echo "  • 手势控制真手：      cd Demo && ./run_handtracking.sh build real" )

文档见 docs/README_资料索引_中文.md
EOF
