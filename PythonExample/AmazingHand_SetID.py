#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AmazingHand_SetID.py — 给 Feetech SCS0009 舵机设置 ID（零依赖，Linux 专用）

不依赖 pyserial / 任何 SDK，也不需要 Windows 的 FD 软件：
  - 用 `stty` 把串口配置为指定波特率 + raw 模式
  - 用 Python 原始设备读写（os.read / os.write）直接收发 Feetech 串口总线协议报文
    （报文格式与 Dynamixel Protocol 1.0 兼容；设置 ID/锁/波特率都是单字节，无需关心大小端）

依赖：仅需系统自带的 `stty`（coreutils）和 Python3 标准库。无需 pip install。

用法示例：
  # 1) 扫描总线上现有的舵机（务必一次只接一个舵机来改 ID！）
  python3 AmazingHand_SetID.py --port /dev/ttyUSB0 --scan

  # 2) 把 ID=1 的舵机改成 ID=3
  python3 AmazingHand_SetID.py --port /dev/ttyUSB0 --old 1 --new 3

  # 3) 个别舵机 EEPROM 被锁，加 --unlock 解锁后再写
  python3 AmazingHand_SetID.py --port /dev/ttyUSB0 --old 1 --new 3 --unlock

提示：Waveshare 串口总线驱动在不同机器上可能枚举为 /dev/ttyUSB* 或 /dev/ttyACM*，
      先用 --scan 在各端口上确认。

Amazing Hand 的 ID 约定：
  食指 Index  = 1 & 2     中指 Middle = 3 & 4
  无名 Ring   = 5 & 6     拇指 Thumb  = 7 & 8

⚠️ 重要：
  - 设置 ID 时务必【一次只接一个舵机】，否则出厂默认都是 ID=1 会冲突。
  - 舵机需要【外部电源】供电才会响应。
  - 改完 ID 后建议【断电再上电】，脚本会先尝试回读校验。
"""

import os
import sys
import time
import select
import argparse
import subprocess

# ---- SCS0009 (SCSCL) 寄存器地址（见装配指南内存表）----
ADDR_ID        = 5    # ID 寄存器（EEPROM）
ADDR_BAUD_RATE = 6    # 波特率寄存器（EEPROM）
ADDR_LOCK      = 48   # EEPROM 锁：写 0 解锁，写 1 上锁

# ---- 指令 ----
INST_PING  = 0x01
INST_READ  = 0x02
INST_WRITE = 0x03


def configure_port(port, baud):
    """用 stty 把串口设为 raw + 指定波特率。失败抛 RuntimeError。"""
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
    """发送一帧并读取状态返回包。返回 (error, params) 或 None。"""
    _drain(fd)
    os.write(fd, data)
    buf = bytearray()
    need = 6 + expect            # FF FF ID LEN ERR [params] CHK
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


def read_byte(fd, sid, addr):
    r = _txrx(fd, _pkt(sid, INST_READ, [addr, 1]), 1)
    return r[1][0] if r and r[1] else None


def write_byte(fd, sid, addr, value):
    return _txrx(fd, _pkt(sid, INST_WRITE, [addr, value & 0xFF]), 0)


def scan(fd, lo=1, hi=20):
    found = []
    for sid in range(lo, hi + 1):
        if ping(fd, sid):
            found.append(sid)
    return found


def set_id(fd, old_id, new_id, unlock=False):
    if not ping(fd, old_id):
        print(f"✗ 找不到 ID={old_id} 的舵机，请检查接线/供电/串口。")
        return False
    print(f"  确认到 ID={old_id}")
    if old_id != new_id and ping(fd, new_id):
        print(f"✗ 总线上已存在 ID={new_id} 的舵机，会冲突！请一次只接一个舵机。")
        return False

    if unlock:
        print("  解锁 EEPROM ...")
        write_byte(fd, old_id, ADDR_LOCK, 0)
        time.sleep(0.05)

    print(f"  写入新 ID：{old_id} -> {new_id}")
    write_byte(fd, old_id, ADDR_ID, new_id)
    time.sleep(0.1)

    if unlock:
        print("  重新上锁 EEPROM ...")
        write_byte(fd, new_id, ADDR_LOCK, 1)
        time.sleep(0.05)

    time.sleep(0.1)
    if ping(fd, new_id):
        rid = read_byte(fd, new_id, ADDR_ID)
        if rid == new_id:
            print(f"✓ 成功：舵机现在的 ID = {rid}")
            return True
    print("⚠ 写入指令已发送，但未能用新 ID 回读校验。")
    print("  请将舵机【断电再上电】，然后运行 --scan 确认。")
    return False


def main():
    ap = argparse.ArgumentParser(description="给 Feetech SCS0009 舵机设置 ID（零依赖）")
    ap.add_argument("--port", default="/dev/ttyUSB0",
                    help="串口设备（默认 /dev/ttyUSB0；也可能是 /dev/ttyACM*）")
    ap.add_argument("--baud", type=int, default=1000000, help="波特率（默认 1000000）")
    ap.add_argument("--scan", action="store_true", help="扫描总线上的舵机 ID")
    ap.add_argument("--old", type=int, help="当前 ID（出厂默认 1）")
    ap.add_argument("--new", type=int, help="要设置的新 ID")
    ap.add_argument("--unlock", action="store_true", help="写入前解锁 EEPROM（个别舵机需要）")
    args = ap.parse_args()

    try:
        configure_port(args.port, args.baud)
    except RuntimeError as e:
        sys.exit(f"{e}\n（若提示权限不足：sudo usermod -aG dialout $USER 后重新登录）")

    try:
        fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as e:
        sys.exit(f"打开串口失败：{e}")

    try:
        if args.scan:
            print(f"扫描 {args.port} @ {args.baud} ...")
            ids = scan(fd)
            print("找到的 ID：", ids if ids else "（无）")
            return

        if args.old is None or args.new is None:
            ap.error("请提供 --old 和 --new，或使用 --scan")
        if not (0 <= args.new <= 253):
            ap.error("新 ID 必须在 0~253 之间")

        set_id(fd, args.old, args.new, unlock=args.unlock)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
