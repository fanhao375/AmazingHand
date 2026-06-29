#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AmazingHand_Demo_NoDeps.py — Amazing Hand 花样动作 Demo（零依赖，不用 rustypot）

复用 AmazingHand_Calib.py 的零依赖通信底层（stty + 原始设备读写），
所以避开了 rustypot 在这块 CH343 板上的 "Parsing error"。

—— 手指运动学 ——
每根手指 2 个舵机并联，合成两个自由度：
  flex (f) : 屈/伸（开合）—— 两舵机【反向】运动
  abd  (a) : 外展/内收（左右）—— 两舵机【同向】运动
舵机目标角（相对各自中位 off）：
  servo1 = off1 + s*( f + a)
  servo2 = off2 + s*(-f + a)
其中 s = -1（需要翻转方向的手，如本右手）或 +1。

—— 配置 ——
在下面 FINGERS 里把已装好、标定过的手指设 present=True，并填上
calibration.txt 里记录的 off1/off2/flip。其余 present=False 会被跳过。

用法：
  python3 AmazingHand_Demo_NoDeps.py            # 跑一遍花样
  python3 AmazingHand_Demo_NoDeps.py --loop     # 循环跑，Ctrl-C 停
  python3 AmazingHand_Demo_NoDeps.py --relax    # 结束后松扭矩
"""

import sys
import time
import argparse

import AmazingHand_Calib as ah

# ====== 手指配置（按 calibration.txt 填写）======
FINGERS = {
    "index":  dict(ids=(1, 2), off=(0.0, 0.0), flip=True,  present=True),
    "middle": dict(ids=(3, 4), off=(0.0, 0.0), flip=True,  present=True),
    "ring":   dict(ids=(5, 6), off=(0.0, 0.0), flip=True,  present=False),
    "thumb":  dict(ids=(7, 8), off=(0.0, 0.0), flip=True,  present=False),
}

# 安全角度范围（相对中位，单位度）
F_OPEN, F_CLOSE = -25.0, 85.0   # 屈伸：负=张开，正=闭合
A_MAX = 22.0                    # 外展/内收最大幅度

SERVO_SPEED = 0                 # 0=按插值步进自然移动；底层每步直接给位置
STEP_DT = 0.02                  # 插值步长时间(s)


def active():
    return {k: v for k, v in FINGERS.items() if v["present"]}


def servo_targets(cfg, f, a):
    """把 (flex, abd) 换成两个舵机的角度（含 flip 与中位偏移）。"""
    s = -1.0 if cfg["flip"] else 1.0
    off1, off2 = cfg["off"]
    return (off1 + s * (f + a), off2 + s * (-f + a))


def apply_state(fd, state):
    """state: {finger: (f,a)} —— 用一帧 SYNC WRITE 同时驱动所有舵机，
    避免逐个发指令导致的卡顿/不同步。"""
    pairs = []
    for name, (f, a) in state.items():
        cfg = FINGERS[name]
        d1, d2 = servo_targets(cfg, f, a)
        pairs.append((cfg["ids"][0], ah.deg_to_raw(d1)))
        pairs.append((cfg["ids"][1], ah.deg_to_raw(d2)))
    ah.sync_write_words(fd, ah.ADDR_GOAL_POSITION, pairs)


def lerp(fd, cur, tgt, dur):
    """从 cur 平滑插值到 tgt（都是 {finger:(f,a)}），耗时 dur 秒。就地更新 cur。"""
    steps = max(1, int(dur / STEP_DT))
    for i in range(1, steps + 1):
        t = i / steps
        mid = {}
        for name in tgt:
            f0, a0 = cur.get(name, (0.0, 0.0))
            f1, a1 = tgt[name]
            mid[name] = (f0 + (f1 - f0) * t, a0 + (a1 - a0) * t)
        apply_state(fd, mid)
        time.sleep(STEP_DT)
    cur.update(tgt)


def all_same(fingers, f, a):
    return {name: (f, a) for name in fingers}


# ====== 花样动作 ======
def demo(fd, fingers):
    cur = all_same(fingers, 0.0, 0.0)         # 从中位开始
    apply_state(fd, cur)
    time.sleep(0.4)

    print("1) 醒手：张开")
    lerp(fd, cur, all_same(fingers, F_OPEN, 0.0), 0.8)
    time.sleep(0.4)

    print("2) 招手：屈伸摆动 ×3")
    for _ in range(3):
        lerp(fd, cur, all_same(fingers, 45.0, 0.0), 0.35)
        lerp(fd, cur, all_same(fingers, 5.0, 0.0), 0.35)

    print("3) 左右摆：外展/内收 ×3")
    for _ in range(3):
        lerp(fd, cur, all_same(fingers, 20.0, A_MAX), 0.4)
        lerp(fd, cur, all_same(fingers, 20.0, -A_MAX), 0.4)
    lerp(fd, cur, all_same(fingers, 20.0, 0.0), 0.3)

    print("4) 慢握拳：缓缓闭合并保持")
    lerp(fd, cur, all_same(fingers, F_OPEN, 0.0), 0.5)
    lerp(fd, cur, all_same(fingers, F_CLOSE, 0.0), 1.6)
    time.sleep(0.8)
    print("   松开")
    lerp(fd, cur, all_same(fingers, F_OPEN, 0.0), 1.0)

    print("5) 快速点按 ×4")
    for _ in range(4):
        lerp(fd, cur, all_same(fingers, 60.0, 0.0), 0.18)
        lerp(fd, cur, all_same(fingers, 15.0, 0.0), 0.18)

    print("6) 画圈：屈伸+外展组合 ×2")
    import math
    for _ in range(2):
        for deg in range(0, 360, 30):
            r = math.radians(deg)
            f = 35.0 + 25.0 * math.sin(r)
            a = A_MAX * math.cos(r)
            lerp(fd, cur, all_same(fingers, f, a), 0.08)

    print("7) 收势：回中位")
    lerp(fd, cur, all_same(fingers, 0.0, 0.0), 0.8)


def main():
    ap = argparse.ArgumentParser(description="Amazing Hand 花样动作 Demo（零依赖）")
    ap.add_argument("--port", default=ah.DEFAULT_PORT, help="串口设备")
    ap.add_argument("--baud", type=int, default=1000000, help="波特率")
    ap.add_argument("--loop", action="store_true", help="循环播放，Ctrl-C 停止")
    ap.add_argument("--relax", action="store_true", help="结束后松开扭矩")
    args = ap.parse_args()

    fingers = active()
    if not fingers:
        sys.exit("没有启用的手指。请在 FINGERS 里把已标定手指设为 present=True。")

    try:
        ah.configure_port(args.port, args.baud)
    except RuntimeError as e:
        sys.exit(str(e))

    import os
    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    # 先确认在用手指的舵机都在线
    miss = [sid for cfg in fingers.values() for sid in cfg["ids"] if not ah.ping(fd, sid)]
    if miss:
        os.close(fd)
        sys.exit(f"✗ 找不到舵机 ID {miss}，请检查接线/供电。")

    # 使能扭矩
    for cfg in fingers.values():
        for sid in cfg["ids"]:
            ah.torque(fd, sid, True)
            ah.write_word(fd, sid, ah.ADDR_GOAL_SPEED, SERVO_SPEED)

    print(f"启用手指：{list(fingers)}")
    try:
        if args.loop:
            n = 0
            while True:
                n += 1
                print(f"=== 第 {n} 遍 ===")
                demo(fd, fingers)
                time.sleep(0.5)
        else:
            demo(fd, fingers)
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        if args.relax:
            for cfg in fingers.values():
                for sid in cfg["ids"]:
                    ah.torque(fd, sid, False)
            print("已松开扭矩。")
        os.close(fd)


if __name__ == "__main__":
    main()
