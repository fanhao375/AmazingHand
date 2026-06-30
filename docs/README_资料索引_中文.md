# Amazing Hand 中文资料总索引

> 从零复刻一只 Amazing Hand（右手）+ 玩手势控制的全套中文资料与程序。
> 按学习顺序排列，照着走即可。环境：Linux + Waveshare 串口驱动板 + Python。

---

## 📖 手册（照着做）

| 顺序 | 文档 | 内容 |
|---|---|---|
| 1 | [总览](AmazingHand_总览_中文.md) | 项目是什么、能做什么 |
| 2 | [3D 打印技巧](AmazingHand_3D打印技巧_中文.md) | 打印参数、材料建议 |
| 3 | [装配指南](AmazingHand_装配指南_中文.md) | 机械装配图文步骤 |
| 4 | [**小白复刻手册**](AmazingHand_小白复刻手册_中文.md) | ⭐ 设 ID + 中位标定 + 跑基础 Demo（零依赖路线，含踩坑表）|
| 5 | [**手势控制小白手册**](AmazingHand_手势控制小白手册_中文.md) | ⭐ MediaPipe + MuJoCo + 真手遥操作（环境安装 + 踩坑全记录）|

---

## 🛠 程序与脚本

### 基础控制（零依赖，不用 pip / rustypot）
位于 `PythonExample/`：

| 脚本 | 作用 | 示例 |
|---|---|---|
| `AmazingHand_SetID.py` | 扫描 / 设置舵机 ID | `python3 AmazingHand_SetID.py --port "$PORT" --scan` |
| `AmazingHand_Calib.py` | 中位标定（middle/close/open/cycle/read/relax）| `python3 AmazingHand_Calib.py middle --ids 1 2 --port "$PORT"` |
| `AmazingHand_Demo_NoDeps.py` | 整手花样动作 Demo | `python3 AmazingHand_Demo_NoDeps.py --port "$PORT"` |
| `AmazingHand_RPS.py` | 剪刀石头布（含 `--random` 随机对战）| `python3 AmazingHand_RPS.py --port "$PORT" --random --rounds 5` |
| `calibration.txt` | 8 个舵机的标定值记录 | — |

> `$PORT` = 你驱动板的 by-id 路径，见手册第 5.2 节。

### 手势控制（MediaPipe + MuJoCo + 真手）
位于 `Demo/`：

| 文件 | 作用 |
|---|---|
| `run_handtracking.sh` | ⭐ 一键启动脚本（封装所有环境变量）|
| `AHControl/config/r_hand.toml` | 右手电机方向(invert)/偏移配置（已按本右手标定）|
| `dataflow_tracking_simu.yml` | 只跑仿真的数据流 |
| `dataflow_tracking_real.yml` | 仿真 + 真手的数据流 |

一键启动：
```bash
cd Demo
./run_handtracking.sh build sim   # 首次：装依赖并跑仿真
./run_handtracking.sh sim         # 之后：只跑仿真
./run_handtracking.sh build real  # 首次：编译 Rust 并接真手
./run_handtracking.sh real        # 之后：接真手
./run_handtracking.sh stop        # 停止
```

---

## 🧭 推荐学习路线

```
打印零件 → 装配 → 设 8 个舵机 ID → 中位标定 → 跑花样Demo/剪刀石头布
                                                      │
                                                      ▼
                              只跑手势仿真 → 接真手手势遥操作
```

1. **先复刻**：跟[小白复刻手册](AmazingHand_小白复刻手册_中文.md)把手装好、ID 设好、标定好，跑通花样 Demo。
2. **再玩手势**：跟[手势控制手册](AmazingHand_手势控制小白手册_中文.md)装环境，**先只跑仿真**验证，再接真手。

---

## ⚠️ 三条最容易踩的坑（详见各手册踩坑表）
1. **设 ID 要加 `--unlock`**，否则断电退回；且**一次只接一个新舵机**（多个 ID=1 会被一起改）。
2. **右手开合方向要翻转**（标定加 `--flip`；手势控制里改 `r_hand.toml` 的 `invert`）。
3. **国内网络全程用清华镜像**（uv/dora/rustup/cargo），直连国外会 SSL 失败。

---

祝复刻顺利 🤖✋
