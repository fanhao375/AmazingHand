# Amazing Hand 手势控制小白手册（MediaPipe + MuJoCo + 真手遥操作）

> 用普通摄像头追踪你的手，让 **MuJoCo 仿真手**和**真机械手**实时跟着你动。
> 本手册基于一次真实搭建全过程整理，**每条命令、每个坑、每个报错都写进来了**，
> 照着做就能复现。环境：**Ubuntu/Linux + 国内网络 + Waveshare 串口驱动板**。

> 📌 配套文档：装配 + 设 ID + 标定见
> [AmazingHand_小白复刻手册_中文.md](AmazingHand_小白复刻手册_中文.md)。
> **本手册假设你已经装好手、设好 8 个舵机 ID、标定过中位。**

---

## 目录
- [0. 这套系统长什么样](#0-这套系统长什么样)
- [1. 工作原理（Dora 数据流）](#1-工作原理dora-数据流)
- [2. 总体安装顺序](#2-总体安装顺序一览)
- [3. 装 uv 和 dora](#3-装-uv-和-dora)
- [4. 只跑仿真（第一步，强烈建议先做）](#4-只跑仿真第一步强烈建议先做)
- [5. 接真手（装 Rust + 编译控制节点）](#5-接真手装-rust--编译控制节点)
- [6. 调方向（r_hand.toml 的 invert）](#6-调方向r_handtoml-的-invert)
- [7. 踩过的坑合集（重要！）](#7-踩过的坑合集重要)
- [8. 命令速查](#8-命令速查)
- [9. 日常使用](#9-日常使用每次重新跑)

---

## 0. 这套系统长什么样

三个窗口并排：
- **左**：真机械手（跟着你动）
- **中**：MediaPipe Hands —— 摄像头画面 + 你手部的骨架关键点
- **右**：MuJoCo 仿真手 + 红球（指尖目标）

你的手张开/握拳/动手指，仿真手和真手都实时跟随。

---

## 1. 工作原理（Dora 数据流）

整套用 **dora-rs** 这个数据流框架把 3 个节点串起来：

```
摄像头 ──> HandTracking(MediaPipe)     识别手部 21 个关键点
              │ r_hand_pos
              v
          AHSimulation(MuJoCo + Mink)   用 IK 反解出 8 个关节角，并显示仿真
              │ mj_r_joints_pos
              v
          AHControl(Rust)               把关节角写给真舵机
              │
              v
          真机械手
```

- **只跑仿真**：`dataflow_tracking_simu.yml`（只要前两个节点，不碰硬件）
- **接真手**：`dataflow_tracking_real.yml`（多第三个 Rust 节点）

代码都在仓库 `Demo/` 目录：`HandTracking/`、`AHSimulation/`、`AHControl/`。

---

## 2. 总体安装顺序（一览）

| 步骤 | 装什么 | 需要 sudo？ |
|---|---|---|
| 3 | uv（Python 环境管理）、dora CLI | 否 |
| 4 | Python 3.12 venv + mediapipe/mujoco（仿真就够了）| 否 |
| 5 | Rust 工具链 + libudev shim（接真手才需要）| 否（用 shim 绕开）|

> 全程国内网络，**所有下载都走清华镜像**，否则直连国外（astral / crates.io / rustup）会超时或 SSL 报错。

---

## 3. 装 uv 和 dora

### 3.1 先有 pip
```bash
python3 -m pip --version    # 没有的话：python3 /tmp/get-pip.py --user（见复刻手册）
```

### 3.2 装 uv
> ⚠️ **坑**：官网 `curl https://astral.sh/uv/install.sh | sh` 在国内会 SSL 断开报错。
> **改用 pip 装**（走清华镜像）：
```bash
python3 -m pip install uv
export PATH="$HOME/.local/bin:$PATH"     # 让 uv 在 PATH 里
uv --version                              # 验证
```

### 3.3 装 dora CLI（版本要对齐）
节点要求 dora-rs 0.3.11~0.3.13，CLI 也装这个区间：
```bash
pip install dora-rs-cli==0.3.13
dora --version                            # 应显示 dora-cli 0.3.13
```

### 3.4 设清华镜像（每个新终端都要 export）
```bash
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 4. 只跑仿真（第一步，强烈建议先做）

先把"摄像头追踪 + 仿真"跑通，**不碰硬件、零风险**，验证摄像头和环境没问题。

### 4.1 建 Python 3.12 虚拟环境
> ⚠️ **坑**：不先建 venv 直接 `dora build` 会报
> `No virtual environment found; run uv venv`。
```bash
cd Demo            # 进到 Demo 目录（有那些 dataflow_*.yml 的地方）
uv venv --python 3.12        # uv 会自动下载 Python 3.12
```

### 4.2 确认摄像头
代码默认用 `cv2.VideoCapture(0)`，对应 `/dev/video0`：
```bash
ls /dev/video*
cat /sys/class/video4linux/video0/name    # 看是不是你的 RGB 摄像头
```
- 如果你的 RGB 摄像头不是 video0，改 `HandTracking/HandTracking/main.py` 里
  `cap = cv2.VideoCapture(0)` 的数字（比如改成 6）。
- ⚠️ 深度相机（如 Orbbec）的 video 节点不能直接当普通摄像头用，要用普通 RGB 摄像头。

### 4.3 启动
```bash
export PATH="$HOME/.local/bin:$PATH"
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export DISPLAY=:0                          # 远程桌面/无 DISPLAY 时必须设

dora up                                    # 起守护进程
dora build dataflow_tracking_simu.yml --uv # 装 mediapipe/mujoco/mink（下载大，几分钟）
dora run   dataflow_tracking_simu.yml --uv # 运行
```
跑起来弹 3 个窗口（MediaPipe + 左右手 MuJoCo）。**把手伸到摄像头前**，仿真手就跟着动。

> 停止：在跑 `dora run` 的终端按 **Ctrl-C**，或新终端 `dora destroy`。

---

## 5. 接真手（装 Rust + 编译控制节点）

真手控制节点 `AHControl` 是 **Rust** 写的，要装 Rust 工具链来编译。

### 5.1 装 Rust（清华镜像，免 sudo）
> ⚠️ **坑**：官网 `sh.rustup.rs` 在国内同样 SSL 报错。从清华镜像下 `rustup-init`：
```bash
# 1) 设 rustup 镜像
export RUSTUP_DIST_SERVER=https://mirrors.tuna.tsinghua.edu.cn/rustup
export RUSTUP_UPDATE_ROOT=https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup
# 2) 下载并运行 rustup-init
cd /tmp
curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup/dist/x86_64-unknown-linux-gnu/rustup-init -o rustup-init
chmod +x rustup-init
./rustup-init -y --default-toolchain stable --profile minimal
source ~/.cargo/env          # 让 cargo/rustc 进 PATH
rustc --version              # 验证
```

### 5.2 设 cargo 依赖镜像（清华）
否则编译时下载几百个 crate 会很慢。新建 `~/.cargo/config.toml`：
```toml
[source.crates-io]
replace-with = 'tuna'
[source.tuna]
registry = "sparse+https://mirrors.tuna.tsinghua.edu.cn/crates.io-index/"
```

### 5.3 ⭐ 解决 libudev 报错（免 sudo 的关键技巧）
> ⚠️ **大坑**：Rust 的 `serialport` 库依赖系统库 **libudev**，编译会报：
> `error: failed to run custom build command for libudev-sys ... No package 'libudev' found`
>
> 正常解法是 `sudo apt install libudev-dev`，但如果你不想用 sudo——系统其实**已经有
> 运行库 `libudev.so.1`**，只缺开发用的软链和 `.pc` 文件。`libudev-sys` 只需要**链接库**、
> 不需要头文件，所以可以在用户目录造个 shim 骗过它：

```bash
mkdir -p ~/.local/lib/pkgconfig
# 1) 造 libudev.so 软链，指向系统已有的 .so.1
ln -sf /usr/lib/x86_64-linux-gnu/libudev.so.1 ~/.local/lib/libudev.so
# 2) 造 libudev.pc 让 pkg-config 找得到，链接目录指向用户目录
cat > ~/.local/lib/pkgconfig/libudev.pc <<'EOF'
libdir=__HOME__/.local/lib
Name: libudev
Description: libudev (user shim -> system libudev.so.1)
Version: 249
Libs: -L${libdir} -ludev
Cflags:
EOF
sed -i "s#__HOME__#$HOME#" ~/.local/lib/pkgconfig/libudev.pc
# 3) 验证
export PKG_CONFIG_PATH="$HOME/.local/lib/pkgconfig:$PKG_CONFIG_PATH"
pkg-config --exists libudev && echo "✅ libudev 可见"
```
> 如果你有 sudo，更省事：`sudo apt-get install -y libudev-dev pkg-config`，就不用上面的 shim。

### 5.4 改串口为你自己的板子
`dataflow_tracking_real.yml` 里控制节点默认串口是 `/dev/ttyACM0`，改成你那块板的
**by-id 固定路径**（见复刻手册第 5.2 节获取）：
```bash
# 例（换成你自己的序列号）：
sed -i "s#--serialport /dev/ttyACM0#--serialport /dev/serial/by-id/usb-1a86_USB_Single_Serial_XXXX-if00#g" \
  dataflow_tracking_real.yml
```

### 5.5 编译并运行真手数据流
```bash
cd Demo
source ~/.cargo/env
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
export PKG_CONFIG_PATH="$HOME/.local/lib/pkgconfig:$PKG_CONFIG_PATH"   # build 时要
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export DISPLAY=:0

dora build dataflow_tracking_real.yml --uv   # 编译 Rust(rustypot+dora，较久)
dora run   dataflow_tracking_real.yml --uv
```
启动后 AHControl 会先给电机上扭矩。**手放电源开关附近**，万一动作异常立刻断电。
把手伸到摄像头前——真手跟着动！

> 🎉 **好消息**：`rustypot` 的 **Rust 原生版**在 CH343 驱动板上工作正常，
> 即使它的 Python 绑定在同一块板上会报 `Parsing error`。

---

## 6. 调方向（r_hand.toml 的 invert）

第一次跑真手，方向多半要调（开合反了、某指反了）。配置在
`AHControl/config/r_hand.toml`，每个电机有 `invert`（方向）和 `offset`（中位偏移）。

**要点**：
- `invert = true/false` 只改**方向**，**改不了幅度**。
- 一根手指 2 个电机，**反对称**配合做开合。若其中一个 invert 装反，两电机会
  **互相抵消** → 表现为"动作幅度小"；把那个反的翻过来，方向和幅度就一起好了。

**本右手实测的最终配置**（供参考，你的可能不同）：
| 手指 | 电机 ID | invert |
|---|---|---|
| 食指 | 1, 2 | true, true |
| 中指 | 3, 4 | true, true |
| 无名指 | 5, 6 | true, true |
| 拇指 | 7, 8 | **false, true** |

调法：改 `r_hand.toml` → **不用重新编译**（运行时读取）→ 重启 dataflow 看效果。
反复试，直到每根手指开合方向正确、幅度正常。

> 怎么定位是哪个电机反：单独看一根手指，开合时观察哪个电机方向不对，就翻它的 invert。

---

## 7. 踩过的坑合集（重要！）

| 报错 / 现象 | 原因 | 解决 |
|---|---|---|
| `curl astral.sh ... SSL ... unexpected eof` | 国内直连国外不稳 | uv 改用 `pip install uv` |
| `dora build` 报 `No virtual environment found` | 没先建 venv | 先 `uv venv --python 3.12` |
| `failed to run custom build command for libudev-sys` / `No package 'libudev'` | 缺 libudev 开发包 | 造 [libudev shim](#53--解决-libudev-报错免-sudo-的关键技巧) 或 `sudo apt install libudev-dev` |
| rustypot **Python** 版 `Parsing error` | Python 绑定与 CH343 板不兼容 | 用 Rust 的 AHControl（原生 rustypot 正常）|
| 摄像头打不开 / 画面黑 | `VideoCapture(0)` 不是你的 RGB 摄像头 | 改 main.py 里的设备序号；别用深度相机节点 |
| 扫描/控制突然全失败 | 外部电源或接头松了 | 检查电源、接头（最常见故障）|
| 真手开合方向反 | invert 没配 | 调 r_hand.toml 的 invert（见第 6 节）|
| 某指幅度小 | 该指一个电机 invert 装反，两电机抵消 | 翻转那个电机的 invert |
| 三个窗口"弹一下就没了" | 其实是**被最小化**了，进程没崩 | GNOME 按 Super 或 Alt+Tab 调出；远程桌面优先 Alt+Tab |
| 想停 dataflow，`pkill -f "dora run..."` 把自己也杀了 | pkill -f 匹配到自己命令行里的同名字符串 | 用 `dora destroy`，或按 PID `kill` |
| 下 crate 极慢 | 默认走 crates.io | 配 `~/.cargo/config.toml` 清华镜像 |
| 下 Python 包慢/失败 | 默认走 PyPI | `export UV_DEFAULT_INDEX=清华` |

---

## 8. 命令速查

```bash
# —— 每个新终端先设环境 ——
source ~/.cargo/env 2>/dev/null
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
export PKG_CONFIG_PATH="$HOME/.local/lib/pkgconfig:$PKG_CONFIG_PATH"
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export DISPLAY=:0
cd Demo

# —— 仿真 ——
dora up
dora build dataflow_tracking_simu.yml --uv     # 只第一次
dora run   dataflow_tracking_simu.yml --uv

# —— 真手 ——
dora build dataflow_tracking_real.yml --uv      # 只第一次（或改了 Rust 代码后）
dora run   dataflow_tracking_real.yml --uv

# —— 停止 ——
dora destroy        # 干净停掉守护进程和所有节点
```

---

## 9. 日常使用（每次重新跑）

环境装好后，以后每次只要：
```bash
cd Demo
source ~/.cargo/env
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
export DISPLAY=:0
dora up
dora run dataflow_tracking_real.yml --uv     # 真手；或 _simu 只仿真
```
> 舵机 ID 和方向配置（r_hand.toml）都是持久的，断电也不丢，重新上电直接跑。
> 改了 `r_hand.toml` 只需重启 dataflow，**不用重新 build**。

---

祝你玩得开心，也祝教程大火 🤖✋🎥
