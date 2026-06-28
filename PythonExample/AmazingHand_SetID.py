#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AmazingHand_SetID.py — 给 Feetech SCS0009 舵机设置 ID（Linux 友好，无需 Windows FD 软件）

只依赖 pyserial，直接走 Feetech 串口总线协议（与 Dynamixel Protocol 1.0 兼容的报文格式），
因此不依赖任何会随版本变化 API 的 SDK。

用法示例：
  # 1) 先扫描总线上现有的舵机（务必一次只接一个舵机来改 ID！）
  python3 AmazingHand_SetID.py --port /dev/ttyUSB0 --scan

  # 2) 把 ID=1 的舵机改成 ID=3
  python3 AmazingHand_SetID.py --port /dev/ttyUSB0 --old 1 --new 3

  # 3) 个别舵机 EEPROM 被锁，加 --unlock 解锁后再写
  python3 AmazingHand_SetID.py --port /dev/ttyUSB0 --old 1 --new 3 --unlock

Amazing Hand 的 ID 约定：
  食指 Index  = 1 & 2     中指 Middle = 3 & 4
  无名 Ring   = 5 & 6     拇指 Thumb  = 7 & 8

⚠️ 重要：
  - 设置 ID 时务必【一次只接一个舵机】，否则出厂默认都是 ID=1 会冲突。
  - 改完 ID 后舵机需要【重新上电】才生效（脚本会等待并回读校验）。
"""

import sys
import time
import argparse

try:
    import serial  # pyserial
except ImportError:
    sys.exit("缺少依赖：请先运行  pip install pyserial")

# ---- SCS0009 (SCSCL) 寄存器地址（见装配指南内存表）----
ADDR_ID         = 5    # ID 寄存器（EEPROM）
ADDR_BAUD_RATE  = 6    # 波特率寄存器（EEPROM）
ADDR_LOCK       = 48   # EEPROM 锁：写 0 解锁，写 1 上锁

# ---- 指令 ----
INST_PING  = 0x01
INST_READ  = 0x02
INST_WRITE = 0x03
BROADCAST_ID = 0xFE


def _checksum(data):
    """Feetech/Protocol1.0 校验和：~(ID+LEN+INST+PARAMS) & 0xFF"""
    return (~sum(data)) & 0xFF


def _build(servo_id, inst, params):
    body = [servo_id, len(params) + 2, inst] + list(params)
    return bytes([0xFF, 0xFF] + body + [_checksum(body)])


def _read_status(ser, expect_params=0, timeout=0.2):
    """读一个状态返回包，返回 (error, params) 或 None（超时/无响应）。"""
    deadline = time.time() + timeout
    buf = bytearray()
    need = 6 + expect_params  # FF FF ID LEN ERR [params] CHK
    while time.time() < deadline and len(buf) < need:
        chunk = ser.read(need - len(buf))
        if chunk:
            buf.extend(chunk)
    if len(buf) < 6:
        return None
    # 找帧头
    idx = buf.find(b'\xff\xff')
    if idx < 0 or len(buf) - idx < 6:
        return None
    pkt = buf[idx:]
    sid, length, err = pkt[2], pkt[3], pkt[4]
    params = list(pkt[5:5 + (length - 2)])
    return err, params


def ping(ser, servo_id):
    ser.reset_input_buffer()
    ser.write(_build(servo_id, INST_PING, []))
    return _read_status(ser, 0) is not None


def read_byte(ser, servo_id, addr):
    ser.reset_input_buffer()
    ser.write(_build(servo_id, INST_READ, [addr, 1]))
    res = _read_status(ser, 1)
    if res is None or not res[1]:
        return None
    return res[1][0]


def write_byte(ser, servo_id, addr, value):
    ser.reset_input_buffer()
    ser.write(_build(servo_id, INST_WRITE, [addr, value & 0xFF]))
    time.sleep(0.02)
    return _read_status(ser, 0)


def scan(ser, lo=1, hi=20):
    found = []
    for sid in range(lo, hi + 1):
        if ping(ser, sid):
            found.append(sid)
    return found


def set_id(ser, old_id, new_id, unlock=False):
    if not ping(ser, old_id):
        print(f"✗ 找不到 ID={old_id} 的舵机，请检查接线/供电/串口。")
        return False
    if old_id != new_id and ping(ser, new_id):
        print(f"✗ 总线上已存在 ID={new_id} 的舵机，会冲突！请一次只接一个舵机。")
        return False

    if unlock:
        print("  解锁 EEPROM ...")
        write_byte(ser, old_id, ADDR_LOCK, 0)

    print(f"  写入新 ID：{old_id} -> {new_id}")
    write_byte(ser, old_id, ADDR_ID, new_id)
    time.sleep(0.05)

    if unlock:
        print("  重新上锁 EEPROM ...")
        write_byte(ser, new_id, ADDR_LOCK, 1)

    # 回读校验（ID 改完通常立即生效，无需断电；保险起见也提示断电）
    time.sleep(0.1)
    if ping(ser, new_id):
        rid = read_byte(ser, new_id, ADDR_ID)
        if rid == new_id:
            print(f"✓ 成功：舵机现在的 ID = {rid}")
            return True
    print("⚠ 写入指令已发送，但未能用新 ID 回读校验。")
    print("  请将舵机【断电再上电】，然后运行 --scan 确认。")
    return False


def main():
    ap = argparse.ArgumentParser(description="给 Feetech SCS0009 舵机设置 ID")
    ap.add_argument("--port", default="/dev/ttyUSB0", help="串口设备（默认 /dev/ttyUSB0）")
    ap.add_argument("--baud", type=int, default=1000000, help="波特率（默认 1000000）")
    ap.add_argument("--scan", action="store_true", help="扫描总线上的舵机 ID")
    ap.add_argument("--old", type=int, help="当前 ID（出厂默认 1）")
    ap.add_argument("--new", type=int, help="要设置的新 ID")
    ap.add_argument("--unlock", action="store_true", help="写入前解锁 EEPROM（个别舵机需要）")
    args = ap.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
    except serial.SerialException as e:
        sys.exit(f"打开串口失败：{e}\n"
                 f"（Linux 下若提示权限不足，运行：sudo usermod -aG dialout $USER 后重新登录）")

    with ser:
        if args.scan:
            print(f"扫描 {args.port} @ {args.baud} ...")
            ids = scan(ser)
            print("找到的 ID：", ids if ids else "（无）")
            return

        if args.old is None or args.new is None:
            ap.error("请提供 --old 和 --new，或使用 --scan")
        if not (0 <= args.new <= 253):
            ap.error("新 ID 必须在 0~253 之间")

        set_id(ser, args.old, args.new, unlock=args.unlock)


if __name__ == "__main__":
    main()
