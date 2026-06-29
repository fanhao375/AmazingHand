# Amazing Hand 小白复刻手册（Linux + Python 零依赖路线）

> 面向第一次做这个项目的新手，手把手从买料到让手指动起来。
> 本手册对应 **右手 + Linux 电脑 + Waveshare 串口总线驱动 + Python** 这条路线。
> 用的是仓库里**零依赖**的脚本（`AmazingHand_SetID.py` / `AmazingHand_Calib.py` /
> `AmazingHand_Demo_NoDeps.py`），**不需要 Windows 的 FD 软件，也不依赖 rustypot**。

---

## 0. 这个项目是什么

Amazing Hand 是一只开源的仿人机械手：4 根手指、8 个自由度，每根手指由 **2 个
Feetech SCS0009 小舵机**并联驱动，全部 3D 打印，舵机全藏在手内、无外部线缆，
成本 < 200€。

每根手指 2 个舵机合成两个动作：
- **屈/伸（开合）**：两个舵机**反向**转 → 手指握拢/张开
- **外展/内收（左右）**：两个舵机**同向**转 → 手指左右摆

---

## 1. 准备材料（BOM）

完整清单见仓库 README 里的 BOM 表格。核心要买的：
- **8× Feetech SCS0009 舵机** + 配套十字摇臂、螺丝
- 3D 打印件（手指框架、外壳、手掌、手腕接口等，STL 在 `cad/` 目录）
- 球头拉杆、各种螺丝螺母销钉（见 BOM）
- **控制硬件（本手册用第 1 种）**：
  1. **Waveshare 串口总线舵机驱动板**（USB 转 Feetech 总线）
  2. 或 Arduino + Feetech TTL Linker
- **外部电源**：给 8 个舵机供电，例如 5V / 2A DC 适配器（**必备**，USB 供不动）

---

## 2. 3D 打印

参考 `docs/AmazingHand_3D打印技巧_中文.md`。要点：
- 右手件以 `R` 开头，左手件以 `L` 开头，手指本身左右通用。
- 柔性外壳建议用 TPU；框架用 PLA/PETG 即可。

---

## 3. 机械装配

跟着 `docs/AmazingHand_装配指南_中文.md` 一步步装。装到"标定"那步之前，
先把电路和软件准备好（下面第 4、5 节），因为**装摇臂时需要舵机先转到中位**。

> 装配顺序提醒：先把舵机固定进手指框架、接好球头拉杆和摇臂总成，
> **但摇臂先别拧死到舵机轴上**——要等软件把舵机转到 0° 后再装摇臂（见第 6 节）。

---

## 4. 接线与供电

1. Waveshare 驱动板 → 电脑 USB。
2. 外部电源接到驱动板的电源端子（注意正负极），给舵机供电。
3. 舵机用 Feetech 三针总线线**菊花链**串接：驱动板 → 1 号舵机 → 2 号舵机 → …
   每个舵机有两个并排同款插座，一个进一个出。
4. 波特率统一 **1000000（1M）**。

> ⚠️ 接头务必插到底。**任何一个接头虚接，会让整条总线都通信失败**。
> ⚠️ 没接外部电源，舵机完全不响应。

---

## 5. Linux 软件环境（零依赖）

本路线**只需要系统自带的 `stty` 和 Python3 标准库**，设 ID / 标定全程不用 pip。
（只有"花样 Demo"是纯 Python，也不用第三方库。）

### 5.1 串口权限
把自己加进 `dialout` 组（一次即可，之后重新登录）：
```bash
sudo usermod -aG dialout $USER
```

### 5.2 找到你的驱动板串口
插上驱动板，列出串口：
```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
ls -l /dev/serial/by-id/      # 推荐用这里的“固定路径”，重启不变
```
> 不同芯片枚举不同：CH340 → `ttyUSB*`，CH343/CH9102 → 可能是 `ttyACM*`。
> **强烈建议用 `/dev/serial/by-id/usb-...` 那个带序列号的固定路径**，避免插多个
> USB 设备时编号乱跳。下文用 `$PORT` 代指它，先设个变量方便：
```bash
PORT=/dev/serial/by-id/usb-1a86_USB_Single_Serial_XXXXXXXX-if00   # 换成你自己的
```

### 5.3 验证通信
接一个舵机、上电，扫描：
```bash
python3 AmazingHand_SetID.py --port "$PORT" --scan
```
能看到 `找到的 ID： [1]` 就通了（新舵机出厂都是 ID=1）。
扫不到？→ 看第 9 节排查。

---

## 6. 设置舵机 ID

整只手 8 个舵机，ID 约定：

| 手指 | ID |
|---|---|
| 食指 Index | 1, 2 |
| 中指 Middle | 3, 4 |
| 无名 Ring | 5, 6 |
| 拇指 Thumb | 7, 8 |

每根手指内：奇数 ID = 右侧舵机，偶数 ID = 左侧舵机（按装配指南视角）。

> 🔑 **一次只接一个舵机**改 ID！出厂全是 1，多个一起会冲突。

把一个舵机从 1 改成 2（**务必加 `--unlock`**，否则断电会退回去）：
```bash
python3 AmazingHand_SetID.py --port "$PORT" --old 1 --new 2 --unlock
```
改完**断电再上电**，扫描确认存住了：
```bash
python3 AmazingHand_SetID.py --port "$PORT" --scan
```
依次把 8 个舵机设成 1~8。每根手指的两个都设好后，一起接上扫描应看到全部 ID。

> 💡 **血泪教训**：不加 `--unlock` 时，ID 看似改好，一断电就退回 1。务必加。

---

## 7. 中位标定（关键）

舵机摇臂和舵机轴是花键咬合，每次装角度都差几度，所以每个舵机要标一个**中位偏移**。
用 `AmazingHand_Calib.py`（零依赖，不用 rustypot）。下面以食指（ID 1、2）为例。

### 7.1 让舵机转到中位，再装摇臂
```bash
python3 AmazingHand_Calib.py middle --ids 1 2 --port "$PORT"
```
舵机停在 0°（**程序退出后舵机仍自保持**）。此时把两个摇臂按"中位"姿态尽量对齐
套上舵机轴，拧 M2x4 螺丝固定。

### 7.2 确定开合方向（左右手不同！）
让手指闭合：
```bash
python3 AmazingHand_Calib.py close --ids 1 2 --port "$PORT"
```
- 如果手指**真的往握拢方向动** → 方向对，后续命令不用加 `--flip`。
- 如果**动反了**（该闭合却张开）→ 以后所有命令都加 `--flip`，方向就对了：
  ```bash
  python3 AmazingHand_Calib.py close --ids 1 2 --flip --port "$PORT"
  ```
> 📌 本项目**右手实测需要 `--flip`**。左右手方向相反是正常的，README 也说明
> 要在软件里选左右手。

### 7.3 精细微调
看闭合时手指是否**对称**：
- 对称、闭合到位 → 偏移就是 `0/0`，搞定。
- 偏向某侧 → 给偏的那个舵机加几度偏移，反复试：
  ```bash
  python3 AmazingHand_Calib.py close --ids 1 2 --flip --off1 3 --off2 0 --port "$PORT"
  ```
看整体开合效果：
```bash
python3 AmazingHand_Calib.py cycle --ids 1 2 --flip --off1 0 --off2 0 --n 3 --port "$PORT"
```
> ⚠️ 闭合时舵机会顶住限位**堵转发热**，别长时间停在闭合位，调完及时 `cycle` 或
> `middle`。`relax` 命令可松开扭矩用手扳动。

### 7.4 记录标定值
把每根手指的 `flip / off1 / off2` 记到 `PythonExample/calibration.txt`，
跑 Demo 时要用。

四根手指各重复 7.1~7.4。

---

## 8. 跑花样 Demo

编辑 `AmazingHand_Demo_NoDeps.py` 顶部的 `FINGERS`，把已标定好的手指设
`present=True` 并填入 `off`、`flip`，然后：
```bash
python3 AmazingHand_Demo_NoDeps.py            # 跑一遍花样
python3 AmazingHand_Demo_NoDeps.py --loop     # 循环跑（拍视频），Ctrl-C 停
python3 AmazingHand_Demo_NoDeps.py --relax    # 结束后松开舵机
```
动作包含：醒手、招手、左右摆、慢握拳、快速点按、画圈、收势。
只装了一根手指也能跑，它只会动启用的手指。

---

## 9. 常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| `--scan` 扫不到任何 ID | 多半是**供电没接/掉了**，或总线接头虚接；先确认外部电源，再检查菊花链每个接头。换串口路径试试（`ttyUSB*` vs `ttyACM*`）。 |
| 接一个能扫到，接两个就都没了 | 两个舵机 **ID 冲突**（都是 1），或它们之间那段总线线虚接/插反。 |
| 改了 ID 断电后又变回 1 | 改 ID 时**没加 `--unlock`**。加上重改一次。 |
| 用官方 `*.py`（rustypot）报 `Parsing error` | rustypot 在某些 CH343 板上不兼容。**改用本手册的零依赖脚本**即可。 |
| 闭合方向反了 | 加 `--flip`（左右手方向相反，属正常）。 |
| 舵机发烫 | 长时间堵转（顶限位）导致。别长时间停在闭合位。 |
| 提示串口权限不足 | `sudo usermod -aG dialout $USER` 后**重新登录**。 |
| 没有 pip（只有跑 Demo 需要时） | 本路线设 ID/标定/Demo 都零依赖，不需要 pip。若你要用官方 rustypot 脚本才需要 pip，可用 `python3 get-pip.py --user` 在用户目录装，免 sudo。 |

---

## 10. 文件速查

| 文件 | 作用 |
|---|---|
| `PythonExample/AmazingHand_SetID.py` | 扫描 / 设置舵机 ID（零依赖） |
| `PythonExample/AmazingHand_Calib.py` | 中位标定：middle/close/open/cycle/read/relax（零依赖） |
| `PythonExample/AmazingHand_Demo_NoDeps.py` | 花样动作 Demo（零依赖） |
| `PythonExample/calibration.txt` | 四根手指的标定值记录 |
| `docs/AmazingHand_装配指南_中文.md` | 机械装配图文步骤 |
| `docs/AmazingHand_3D打印技巧_中文.md` | 3D 打印参数建议 |

---

祝复刻顺利！动起来那一刻很有成就感 🤖✋
