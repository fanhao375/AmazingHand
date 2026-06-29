#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AmazingHand_Calib.py — Feetech SCS0009 手指中位标定工具（零依赖，Linux 专用）

和 AmazingHand_SetID.py 用同一套底层通信（stty + os.read/os.write 直接收发
Feetech 串口总线协议），不依赖 rustypot / pyserial，避开 rustypot 在某些
CH343 驱动板上出现的 "Parsing error"。

核心原理：SCS 舵机一旦写入【扭矩使能 + 目标位置】，即使本程序退出，舵机
也会靠自身保持在该位置（直到断电或下一条指令）。所以每条命令设置完即退出，
无需后台常驻。

动作定义（与官方 FingerTest 一致，角度相对各自舵机的中位偏移）：
  中位 middle : ID1 = off1 + 0 ,  ID2 = off2 + 0
  闭合 close  : ID1 = off1 + 90,  ID2 = off2 - 90
  张开 open   : ID1 = off1 - 30,  ID2 = off2 + 30

Amazing Hand 的 ID 约定：食指 1&2 / 中指 3&4 / 无名 5&6 / 拇指 7&8

标定流程：
  1) 装摇臂前，先让舵机到中位：
       python3 AmazingHand_Calib.py middle --ids 1 2
     舵机停在 0°，此时把两个摇臂按中位姿态装上、拧 M2x4。

  2) 检查闭合对齐：
       python3 AmazingHand_Calib.py close --ids 1 2
     手指到闭合位并保持，观察摇臂是否与舵机中位面对齐。

  3) 不齐就调偏移（单位：度），反复试到对齐：
       python3 AmazingHand_Calib.py close --ids 1 2 --off1 3 --off2 0

  4) 看整体开合效果：
       python3 AmazingHand_Calib.py cycle --ids 1 2 --off1 3 --off2 0 --n 3

  5) 记下每个舵机最终的 off 值，后面 4 根手指 / 跑 Demo 都要用。

其它命令：
  read   读取并打印两个舵机当前角度
  relax  松扭矩（舵机变软，可用手扳动）
"""

import os
import sys
import time
import select
import argparse
import subprocess

DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B61034381-if00"

# ---- SCS0009 (SCSCL) 寄存器地址 ----
ADDR_TORQUE_ENABLE = 40   # 0x28 扭矩使能
ADDR_GOAL_POSITION = 42   # 0x2A 目标位置（2 字节，SCSCL 为大端：高字节在前）
ADDR_GOAL_SPEED    = 46   # 0x2E 运行速度（2 字节，大端；0 = 最大速度）
ADDR_PRESENT_POS   = 56   # 0x38 当前位置（2 字节，大端）

# ---- 指令 ----
INST_PING       = 0x01
INST_READ       = 0x02
INST_WRITE      = 0x03
INST_SYNC_WRITE = 0x83
BROADCAST_ID    = 0xFE

# ---- 角度 <-> 原始值换算 ----
CENTER = 512                 # 中位对应的原始位置值
STEPS_PER_DEG = 1024 / 300.0 # SCS0009：1024 步覆盖约 300°，1 步 ≈ 0.293°

# ---- 各动作相对中位的角度偏移 (deg1, deg2) ----
POSES = {
    "middle": (0,  0),
    "close":  (90, -90),
    "open":   (-30, 30),
}


def configure_port(port, baud):
    try:
        subprocess.run(
            ["stty", "-F", port, str(baud), "raw", "-echo", "-echoe", "-echok"],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("找不到 stty 命令（需要 coreutils）")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"stty 配置串口失败：{e.stderr.strip() or e}")


def _cks(d):
    return (~sum(d)) & 0xFF


def _pkt(sid, inst, params):
    body = [sid, len(params) + 2, inst] + list(params)
    return bytes([0xFF, 0xFF] + body + [_cks(body)])


def _drain(fd):
    while select.select([fd], [], [], 0)[0]:
        try:
            if not os.read(fd, 256):
                break
        except OSError:
            break


def _txrx(fd, data, expect=0, timeout=0.1):
    _drain(fd)
    os.write(fd, data)
    buf = bytearray()
    need = 6 + expect
    deadline = time.time() + timeout
    while time.time() < deadline and len(buf) < need:
        if select.select([fd], [], [], 0.02)[0]:
            try:
                chunk = os.read(fd, 64)
                if chunk:
                    buf.extend(chunk)
            except OSError:
                pass
    i = buf.find(b'\xff\xff')
    if i < 0 or len(buf) - i < 6:
        return None
    p = buf[i:]
    length, err = p[3], p[4]
    params = list(p[5:5 + (length - 2)])
    return err, params


def ping(fd, sid):
    return _txrx(fd, _pkt(sid, INST_PING, []), 0) is not None


def write_bytes(fd, sid, addr, values):
    return _txrx(fd, _pkt(sid, INST_WRITE, [addr] + list(values)), 0)


def write_word(fd, sid, addr, value):
    """写 2 字节大端（高字节在前），SCSCL 协议。"""
    value &= 0xFFFF
    return write_bytes(fd, sid, addr, [(value >> 8) & 0xFF, value & 0xFF])


def sync_write_words(fd, addr, pairs):
    """SYNC WRITE：一帧广播给多个舵机写 2 字节大端（如目标位置）。
    pairs: [(sid, value), ...]。广播无返回包，纯发送，所有舵机同时生效。"""
    params = [addr, 2]
    for sid, val in pairs:
        val &= 0xFFFF
        params += [sid, (val >> 8) & 0xFF, val & 0xFF]
    _drain(fd)
    os.write(fd, _pkt(BROADCAST_ID, INST_SYNC_WRITE, params))


def read_word(fd, sid, addr, retries=3):
    """读 2 字节大端，失败重试。返回 int 或 None。"""
    for _ in range(retries):
        r = _txrx(fd, _pkt(sid, INST_READ, [addr, 2]), 2)
        if r and len(r[1]) >= 2:
            return (r[1][0] << 8) | r[1][1]
        time.sleep(0.02)
    return None


def deg_to_raw(deg):
    raw = int(round(CENTER + deg * STEPS_PER_DEG))
    return max(0, min(1023, raw))


def raw_to_deg(raw):
    return (raw - CENTER) / STEPS_PER_DEG


def torque(fd, sid, on):
    write_bytes(fd, sid, ADDR_TORQUE_ENABLE, [1 if on else 0])


def move(fd, sid, deg, speed):
    """使能扭矩并移动到指定角度（相对中位）。"""
    torque(fd, sid, True)
    if speed > 0:
        write_word(fd, sid, ADDR_GOAL_SPEED, speed)
    write_word(fd, sid, ADDR_GOAL_POSITION, deg_to_raw(deg))


def goto_pose(fd, ids, offs, pose, speed, flip=False):
    d1, d2 = POSES[pose]
    if flip:                      # 左右手方向相反时翻转动作符号
        d1, d2 = -d1, -d2
    targets = (offs[0] + d1, offs[1] + d2)
    for sid, deg in zip(ids, targets):
        move(fd, sid, deg, speed)
    return targets


def print_present(fd, ids):
    for sid in ids:
        raw = read_word(fd, sid, ADDR_PRESENT_POS)
        if raw is None:
            print(f"  ID {sid}: 读取失败")
        else:
            print(f"  ID {sid}: {raw_to_deg(raw):+6.1f}°  (raw {raw})")


def check_ids(fd, ids):
    missing = [s for s in ids if not ping(fd, s)]
    if missing:
        sys.exit(f"✗ 总线上找不到舵机 ID {missing}，请检查接线/供电/串口。")


def main():
    ap = argparse.ArgumentParser(
        description="Feetech SCS0009 手指中位标定工具（零依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("cmd", choices=["middle", "close", "open", "cycle", "read", "relax"],
                    help="动作：middle/close/open 移到对应位姿并保持；cycle 开合循环；read 读当前角度；relax 松扭矩")
    ap.add_argument("--ids", type=int, nargs=2, default=[1, 2], metavar=("ID1", "ID2"),
                    help="手指的两个舵机 ID（默认 1 2）")
    ap.add_argument("--off1", type=float, default=0.0, help="ID1 的中位偏移（度）")
    ap.add_argument("--off2", type=float, default=0.0, help="ID2 的中位偏移（度）")
    ap.add_argument("--speed", type=int, default=300,
                    help="运行速度，0=最大（默认 300，较柔和）")
    ap.add_argument("--n", type=int, default=3, help="cycle 模式开合次数（默认 3）")
    ap.add_argument("--flip", action="store_true",
                    help="翻转开合方向（左右手相反 / 舵机装反时使用）")
    ap.add_argument("--port", default=DEFAULT_PORT, help="串口设备")
    ap.add_argument("--baud", type=int, default=1000000, help="波特率（默认 1000000）")
    args = ap.parse_args()

    try:
        configure_port(args.port, args.baud)
    except RuntimeError as e:
        sys.exit(f"{e}\n（若提示权限不足：sudo usermod -aG dialout $USER 后重新登录）")

    try:
        fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as e:
        sys.exit(f"打开串口失败：{e}")

    ids = args.ids
    offs = (args.off1, args.off2)

    try:
        check_ids(fd, ids)

        if args.cmd == "relax":
            for sid in ids:
                torque(fd, sid, False)
            print(f"已松开扭矩：ID {ids}，现在可用手扳动。")
            return

        if args.cmd == "read":
            print_present(fd, ids)
            return

        if args.cmd in ("middle", "close", "open"):
            t = goto_pose(fd, ids, offs, args.cmd, args.speed, args.flip)
            print(f"→ {args.cmd}: ID{ids[0]}={t[0]:+.1f}°  ID{ids[1]}={t[1]:+.1f}°  (偏移 {offs[0]:+}/{offs[1]:+})")
            time.sleep(1.0)
            print("当前实际位置：")
            print_present(fd, ids)
            print("舵机会保持此位置（扭矩持续使能）。")
            return

        if args.cmd == "cycle":
            print(f"开合循环 {args.n} 次（偏移 {offs[0]:+}/{offs[1]:+}），Ctrl-C 可随时停止...")
            try:
                for k in range(args.n):
                    goto_pose(fd, ids, offs, "close", args.speed, args.flip)
                    print(f"  第{k+1}次：闭合"); time.sleep(2.0)
                    goto_pose(fd, ids, offs, "open", args.speed, args.flip)
                    print(f"  第{k+1}次：张开"); time.sleep(1.5)
                goto_pose(fd, ids, offs, "middle", args.speed, args.flip)
                print("回到中位。")
            except KeyboardInterrupt:
                print("\n已停止（舵机保持在当前位置）。")
            return
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
