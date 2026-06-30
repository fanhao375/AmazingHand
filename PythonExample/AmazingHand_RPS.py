#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AmazingHand_RPS.py — 剪刀石头布（零依赖，复用 Calib 底层 + SYNC WRITE）

手势：
  石头 Rock     : 四指全握拳
  布   Paper    : 四指全张开
  剪刀 Scissors : 食指+中指伸出并向两侧张开成 V，无名指+拇指收起

手势用每根手指的 (flex, abd) 表示：
  flex 屈伸：负=张开/伸直，正=握拢   abd 外展：让手指向侧向摆（张开 V 用）
舵机角（相对中位 off）：servo1 = off1 + s*(flex+abd)，servo2 = off2 + s*(-flex+abd)
其中 s = -1（flip=True 的手指）或 +1（拇指 flip=False）。

用法：
  python3 AmazingHand_RPS.py --port "$PORT"
  python3 AmazingHand_RPS.py --port "$PORT" --shake 3   # 先“石头石头石头”晃3下再出
"""
import sys, os, time, argparse
import AmazingHand_Calib as ah

# 手指配置：ids, (off1,off2), flip —— 按 calibration.txt
FINGERS = {
    "index":  ((1, 2), (0.0, 0.0), True),
    "middle": ((3, 4), (0.0, 0.0), True),
    "ring":   ((5, 6), (0.0, 0.0), True),
    "thumb":  ((7, 8), (0.0, 0.0), False),
}
F_OPEN, F_CLOSE = -25.0, 90.0   # 屈伸：负=张开，正=握拢(顶机械限位)
V_ABD = 35.0                    # 剪刀时食指/中指向两侧张开的外展角

# 手势 = {finger: (flex, abd)}
ROCK     = {n: (F_CLOSE, 0.0) for n in FINGERS}
PAPER    = {n: (F_OPEN,  0.0) for n in FINGERS}
SCISSORS = {
    "index":  (F_OPEN, -V_ABD),   # 伸出 + 向一侧张
    "middle": (F_OPEN, +V_ABD),   # 伸出 + 向另一侧张
    "ring":   (F_CLOSE, 0.0),     # 收起
    "thumb":  (F_CLOSE, 0.0),     # 收起
}
MIDDLE = {n: (0.0, 0.0) for n in FINGERS}

cur = {n: (0.0, 0.0) for n in FINGERS}


def finger_pairs(name, f, a):
    ids, off, flip = FINGERS[name]
    s = -1.0 if flip else 1.0
    return [(ids[0], ah.deg_to_raw(off[0] + s * (f + a))),
            (ids[1], ah.deg_to_raw(off[1] + s * (-f + a)))]


def lerp_to(fd, gesture, dur=0.6):
    steps = max(1, int(dur / 0.02))
    for i in range(1, steps + 1):
        t = i / steps
        pairs = []
        for name in FINGERS:
            f0, a0 = cur[name]
            f1, a1 = gesture.get(name, cur[name])
            pairs += finger_pairs(name, f0 + (f1 - f0) * t, a0 + (a1 - a0) * t)
        ah.sync_write_words(fd, ah.ADDR_GOAL_POSITION, pairs)
        time.sleep(0.02)
    for name in gesture:
        cur[name] = gesture[name]


def main():
    ap = argparse.ArgumentParser(description="剪刀石头布")
    ap.add_argument("--port", default=ah.DEFAULT_PORT)
    ap.add_argument("--baud", type=int, default=1000000)
    ap.add_argument("--shake", type=int, default=3, help="出拳前晃几下（石头）")
    ap.add_argument("--relax", action="store_true", help="结束松扭矩")
    args = ap.parse_args()

    ah.configure_port(args.port, args.baud)
    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

    miss = [sid for ids, _, _ in FINGERS.values() for sid in ids if not ah.ping(fd, sid)]
    if miss:
        os.close(fd); sys.exit(f"✗ 找不到舵机 {miss}，检查接线/供电。")

    for ids, _, _ in FINGERS.values():
        for sid in ids:
            ah.torque(fd, sid, True)
            ah.write_word(fd, sid, ah.ADDR_GOAL_SPEED, 0)

    try:
        lerp_to(fd, PAPER, 0.5); time.sleep(0.4)
        # 预备：石头石头石头……上下晃
        for k in range(args.shake):
            print(f"石头…({k+1})")
            lerp_to(fd, ROCK, 0.18)
            lerp_to(fd, {n: (F_CLOSE - 25, 0.0) for n in FINGERS}, 0.18)
        # 依次出三种手势
        for name, g in [("✊ 石头", ROCK), ("✌️ 剪刀", SCISSORS), ("✋ 布", PAPER)]:
            print(name)
            lerp_to(fd, g, 0.45)
            time.sleep(1.4)
        lerp_to(fd, MIDDLE, 0.6)
        print("收。")
    except KeyboardInterrupt:
        print("\n停止。")
    finally:
        if args.relax:
            for ids, _, _ in FINGERS.values():
                for sid in ids:
                    ah.torque(fd, sid, False)
        os.close(fd)


if __name__ == "__main__":
    main()
