#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AmazingHand_GUI.py — Amazing Hand 图形控制台（零依赖，Tkinter）

小白友好的一站式界面：连接舵机、设置 ID、逐指标定、跑花样/猜拳、启动手势控制。
底层复用 AmazingHand_Calib.py / AmazingHand_SetID.py（零依赖串口协议）。

运行：  python3 AmazingHand_GUI.py     （或双击）
依赖：  只需 Python3 标准库（Tkinter 系统自带）。
"""

import os
import sys
import glob
import time
import threading
import subprocess

import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import AmazingHand_Calib as ah          # 控制底层
import AmazingHand_SetID as sidmod      # 设 ID 底层

DEMO_DIR = os.path.normpath(os.path.join(HERE, "..", "Demo"))
CALIB_FILE = os.path.join(HERE, "calibration.txt")

# (中文名, key, (id1,id2), 默认flip)
FINGERS = [
    ("食指", "index", (1, 2), True),
    ("中指", "middle", (3, 4), True),
    ("无名指", "ring", (5, 6), True),
    ("拇指", "thumb", (7, 8), False),
]


# ---------- 工具函数 ----------
def detect_ports():
    """列出可能的串口，优先 by-id 固定路径。"""
    ports = []
    byid = "/dev/serial/by-id"
    if os.path.isdir(byid):
        for f in sorted(os.listdir(byid)):
            ports.append(os.path.join(byid, f))
    ports += sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*"))
    return ports


def default_port(ports):
    for p in ports:                       # 优先 Waveshare CH343
        if "Single_Serial" in p:
            return p
    return ports[0] if ports else ""


def load_calib():
    cfg = {k: {"flip": fl, "off1": 0.0, "off2": 0.0} for _, k, _, fl in FINGERS}
    if os.path.exists(CALIB_FILE):
        cur = None
        for line in open(CALIB_FILE, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1].strip()
            elif "=" in line and cur in cfg:
                k, v = [x.strip() for x in line.split("=", 1)]
                if k == "flip":
                    cfg[cur]["flip"] = (v.lower() == "true")
                elif k in ("off1", "off2"):
                    try:
                        cfg[cur][k] = float(v)
                    except ValueError:
                        pass
    return cfg


def save_calib(cfg):
    lines = ["# Amazing Hand 手指标定记录（由 GUI 保存）", "#"]
    for name, key, ids, _ in FINGERS:
        c = cfg[key]
        lines += [
            f"[{key}]   # {name}",
            f"ids  = {ids[0]}, {ids[1]}",
            f"flip = {'true' if c['flip'] else 'false'}",
            f"off1 = {c['off1']:g}",
            f"off2 = {c['off2']:g}",
            "",
        ]
    open(CALIB_FILE, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def gui_set_id(fd, old, new, unlock):
    """返回 (成功?, 消息)。逻辑同 SetID.set_id，但返回字符串给界面。"""
    if not sidmod.ping(fd, old):
        return False, f"✗ 找不到 ID={old} 的舵机（检查只接了一个、已上电）"
    if old != new and sidmod.ping(fd, new):
        return False, f"✗ 总线上已存在 ID={new}，会冲突！请一次只接一个舵机"
    if unlock:
        sidmod.write_byte(fd, old, sidmod.ADDR_LOCK, 0); time.sleep(0.05)
    sidmod.write_byte(fd, old, sidmod.ADDR_ID, new); time.sleep(0.1)
    if unlock:
        sidmod.write_byte(fd, new, sidmod.ADDR_LOCK, 1); time.sleep(0.05)
    time.sleep(0.1)
    if sidmod.ping(fd, new) and sidmod.read_byte(fd, new, sidmod.ADDR_ID) == new:
        return True, f"✓ 成功：舵机现在的 ID = {new}（建议断电重启再扫描确认）"
    return False, "⚠ 指令已发送但回读失败，请断电重启后扫描确认"


# ---------- 主应用 ----------
class App:
    def __init__(self, root):
        self.root = root
        self.fd = None
        self.proc = None                 # 外部子进程（Demo/手势控制）
        root.title("Amazing Hand 控制台")
        root.geometry("640x560")

        self.cfg = load_calib()

        # 顶部：串口连接
        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="串口:").pack(side="left")
        ports = detect_ports()
        self.port_var = tk.StringVar(value=default_port(ports))
        self.port_cb = ttk.Combobox(top, textvariable=self.port_var, values=ports, width=42)
        self.port_cb.pack(side="left", padx=4)
        ttk.Button(top, text="刷新", width=5, command=self.refresh_ports).pack(side="left")
        self.conn_btn = ttk.Button(top, text="连接", width=6, command=self.toggle_connect)
        self.conn_btn.pack(side="left", padx=4)

        # 在线舵机指示
        onl = ttk.Frame(root, padding=(8, 0))
        onl.pack(fill="x")
        ttk.Label(onl, text="在线:").pack(side="left")
        self.dots = {}
        for i in range(1, 9):
            lb = tk.Label(onl, text=f"●{i}", fg="#bbb", font=("", 11, "bold"))
            lb.pack(side="left", padx=1)
            self.dots[i] = lb
        ttk.Button(onl, text="扫描", width=6, command=lambda: self.run_bg(self.scan)).pack(side="left", padx=8)

        # 选项卡
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=6)
        self._tab_setid()
        self._tab_calib()
        self._tab_play()
        self._tab_track()

        # 状态栏
        self.status = ttk.Label(root, text="未连接。先选串口点【连接】。", anchor="w",
                                relief="sunken", padding=4)
        self.status.pack(fill="x", side="bottom")

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if os.environ.get("AH_GUI_SELFTEST") == "1":
            root.after(700, root.destroy)     # 自测：自动关闭

    # ----- 通用 -----
    def set_status(self, msg, err=False):
        self.root.after(0, lambda: self.status.config(
            text=msg, foreground="#c0392b" if err else "#1e8449"))

    def run_bg(self, fn):
        def wrap():
            try:
                fn()
            except Exception as e:
                self.set_status(f"出错: {e}", err=True)
        threading.Thread(target=wrap, daemon=True).start()

    def need_fd(self):
        if self.fd is None:
            self.set_status("请先【连接】串口", err=True)
            return False
        return True

    # ----- 连接 -----
    def refresh_ports(self):
        ports = detect_ports()
        self.port_cb["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(default_port(ports))

    def toggle_connect(self):
        if self.fd is not None:
            self.disconnect()
            return
        port = self.port_var.get().strip()
        if not port:
            self.set_status("没有可用串口", err=True); return
        try:
            ah.configure_port(port, 1000000)
            self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except Exception as e:
            self.set_status(f"连接失败: {e}", err=True); return
        self.conn_btn.config(text="断开")
        self.set_status(f"已连接 {port}")
        self.run_bg(self.scan)

    def disconnect(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        self.conn_btn.config(text="连接")
        for i in range(1, 9):
            self.dots[i].config(fg="#bbb")
        self.set_status("已断开")

    def scan(self):
        if not self.need_fd():
            return
        found = []
        for i in range(1, 9):
            ok = ah.ping(self.fd, i)
            self.root.after(0, lambda i=i, ok=ok: self.dots[i].config(fg="#27ae60" if ok else "#bbb"))
            if ok:
                found.append(i)
        self.set_status(f"扫描完成，在线: {found if found else '无'}")

    # ----- 设 ID 选项卡 -----
    def _tab_setid(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="设置 ID")
        tip = ("① 一次只接【一个】新舵机（出厂 ID=1），其余全拔掉、上电\n"
               "② 点【扫描确认】应只看到 1 个\n"
               "③ 选目标 ID，点【设置】（默认解锁，永久写入）\n"
               "④ 设完断电重启，再扫描确认")
        ttk.Label(f, text=tip, justify="left", foreground="#555").pack(anchor="w")
        row = ttk.Frame(f); row.pack(anchor="w", pady=10)
        ttk.Label(row, text="当前ID").grid(row=0, column=0)
        self.old_var = tk.IntVar(value=1)
        ttk.Spinbox(row, from_=1, to=253, width=5, textvariable=self.old_var).grid(row=0, column=1, padx=4)
        ttk.Label(row, text="→ 新ID").grid(row=0, column=2)
        self.new_var = tk.IntVar(value=2)
        ttk.Spinbox(row, from_=1, to=253, width=5, textvariable=self.new_var).grid(row=0, column=3, padx=4)
        self.unlock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="解锁写入(推荐)", variable=self.unlock_var).grid(row=0, column=4, padx=8)
        btns = ttk.Frame(f); btns.pack(anchor="w")
        ttk.Button(btns, text="扫描确认", command=lambda: self.run_bg(self.scan)).pack(side="left")
        ttk.Button(btns, text="设置 ID", command=lambda: self.run_bg(self.do_set_id)).pack(side="left", padx=6)
        ttk.Label(f, text="ID 约定：食指1/2  中指3/4  无名5/6  拇指7/8",
                  foreground="#888").pack(anchor="w", pady=(12, 0))

    def do_set_id(self):
        if not self.need_fd():
            return
        old, new = self.old_var.get(), self.new_var.get()
        online = [i for i in range(1, 9) if ah.ping(self.fd, old if False else i)]
        # 安全检查：总线上舵机数
        if len(online) > 1:
            self.set_status(f"⛔ 检测到多个舵机 {online}！设ID时只能接一个，先拔掉其余", err=True)
            return
        ok, msg = gui_set_id(self.fd, old, new, self.unlock_var.get())
        self.set_status(msg, err=not ok)
        self.scan()

    # ----- 标定选项卡 -----
    def _tab_calib(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="标定")
        ttk.Label(f, text="装摇臂前点【中位】；【闭合】看方向/对称；调 off 补偿；【保存】记录",
                  foreground="#555").grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 6))
        hdr = ["手指", "", "", "", "off1", "off2", "翻转", ""]
        self.cal_vars = {}
        r = 1
        for name, key, ids, _ in FINGERS:
            c = self.cfg[key]
            ttk.Label(f, text=f"{name}\n{ids[0]},{ids[1]}", width=6).grid(row=r, column=0, padx=2)
            ttk.Button(f, text="中位", width=5,
                       command=lambda k=key: self.run_bg(lambda: self.pose(k, "middle"))).grid(row=r, column=1)
            ttk.Button(f, text="闭合", width=5,
                       command=lambda k=key: self.run_bg(lambda: self.pose(k, "close"))).grid(row=r, column=2)
            ttk.Button(f, text="循环", width=5,
                       command=lambda k=key: self.run_bg(lambda: self.cycle(k))).grid(row=r, column=3)
            o1 = tk.DoubleVar(value=c["off1"]); o2 = tk.DoubleVar(value=c["off2"])
            fl = tk.BooleanVar(value=c["flip"])
            self.cal_vars[key] = (o1, o2, fl)
            ttk.Spinbox(f, from_=-40, to=40, increment=1, width=5, textvariable=o1).grid(row=r, column=4, padx=2)
            ttk.Spinbox(f, from_=-40, to=40, increment=1, width=5, textvariable=o2).grid(row=r, column=5, padx=2)
            ttk.Checkbutton(f, variable=fl).grid(row=r, column=6)
            r += 1
        bar = ttk.Frame(f); bar.grid(row=r, column=0, columnspan=8, sticky="w", pady=8)
        ttk.Button(bar, text="💾 保存标定", command=self.save_all).pack(side="left")
        ttk.Button(bar, text="松开全部扭矩", command=lambda: self.run_bg(self.relax_all)).pack(side="left", padx=6)

    def _finger(self, key):
        for name, k, ids, _ in FINGERS:
            if k == key:
                o1, o2, fl = self.cal_vars[key]
                return ids, (o1.get(), o2.get()), fl.get()
        return None

    def pose(self, key, which):
        if not self.need_fd():
            return
        ids, offs, flip = self._finger(key)
        ah.goto_pose(self.fd, ids, offs, which, 250, flip)
        self.set_status(f"{key} → {which}（offs {offs[0]:g}/{offs[1]:g}, flip={flip}）")

    def cycle(self, key):
        if not self.need_fd():
            return
        ids, offs, flip = self._finger(key)
        self.set_status(f"{key} 开合循环中…")
        for _ in range(2):
            ah.goto_pose(self.fd, ids, offs, "close", 250, flip); time.sleep(1.6)
            ah.goto_pose(self.fd, ids, offs, "open", 250, flip); time.sleep(1.2)
        ah.goto_pose(self.fd, ids, offs, "middle", 250, flip)
        self.set_status(f"{key} 循环完成")

    def relax_all(self):
        if not self.need_fd():
            return
        for i in range(1, 9):
            ah.torque(self.fd, i, False)
        self.set_status("已松开全部舵机扭矩")

    def save_all(self):
        for _, key, _, _ in FINGERS:
            o1, o2, fl = self.cal_vars[key]
            self.cfg[key] = {"off1": o1.get(), "off2": o2.get(), "flip": fl.get()}
        save_calib(self.cfg)
        self.set_status(f"已保存到 {os.path.basename(CALIB_FILE)}")

    # ----- 玩一玩选项卡 -----
    def _tab_play(self):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="玩一玩")
        ttk.Label(f, text="点按钮跑动作（会先断开串口让子程序独占，运行时别同时手动控制）",
                  foreground="#555").pack(anchor="w", pady=(0, 10))
        ttk.Button(f, text="🖐 整手花样 Demo", width=22,
                   command=lambda: self.launch_py("AmazingHand_Demo_NoDeps.py")).pack(anchor="w", pady=3)
        ttk.Button(f, text="✊✌✋ 剪刀石头布", width=22,
                   command=lambda: self.launch_py("AmazingHand_RPS.py")).pack(anchor="w", pady=3)
        ttk.Button(f, text="🎲 随机猜拳 5 局", width=22,
                   command=lambda: self.launch_py("AmazingHand_RPS.py", ["--random", "--rounds", "5"])).pack(anchor="w", pady=3)
        ttk.Button(f, text="⏹ 停止", width=22, command=self.stop_ext).pack(anchor="w", pady=(12, 3))

    def launch_py(self, script, extra=None):
        port = self.port_var.get().strip()
        if not port:
            self.set_status("没有串口", err=True); return
        self.disconnect()                 # 让子程序独占串口
        self.stop_ext()
        cmd = [sys.executable, os.path.join(HERE, script), "--port", port] + (extra or [])
        self.proc = subprocess.Popen(cmd)
        self.set_status(f"运行中: {script} （点停止结束）")

    # ----- 手势控制选项卡 -----
    def _tab_track(self):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="手势控制")
        ttk.Label(f, text="MediaPipe 摄像头 → 仿真/真手实时跟随。首次点【构建】装依赖。",
                  foreground="#555").pack(anchor="w", pady=(0, 10))
        ttk.Button(f, text="▶ 启动仿真（不碰硬件）", width=26,
                   command=lambda: self.launch_sh("sim")).pack(anchor="w", pady=3)
        ttk.Button(f, text="▶ 启动真手（仿真+真机械手）", width=26,
                   command=lambda: self.launch_sh("real")).pack(anchor="w", pady=3)
        ttk.Button(f, text="🔧 首次构建 (build real)", width=26,
                   command=lambda: self.launch_sh("build", "real")).pack(anchor="w", pady=3)
        ttk.Button(f, text="⏹ 停止手势控制", width=26, command=self.stop_track).pack(anchor="w", pady=(12, 3))
        ttk.Label(f, text="提示：摄像头序号变了要改 HandTracking/main.py 里的 VideoCapture(N)",
                  foreground="#888").pack(anchor="w", pady=(10, 0))

    def launch_sh(self, *args):
        script = os.path.join(DEMO_DIR, "run_handtracking.sh")
        if not os.path.exists(script):
            self.set_status("找不到 run_handtracking.sh", err=True); return
        self.disconnect()                 # 释放串口给 AHControl
        self.stop_ext()
        env = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0"))
        self.proc = subprocess.Popen(["bash", script, *args], cwd=DEMO_DIR, env=env)
        self.set_status(f"手势控制启动中: {' '.join(args)} …（窗口稍后弹出）")

    def stop_track(self):
        script = os.path.join(DEMO_DIR, "run_handtracking.sh")
        try:
            subprocess.run(["bash", script, "stop"], cwd=DEMO_DIR, timeout=30)
        except Exception:
            pass
        self.stop_ext()
        self.set_status("手势控制已停止")

    # ----- 子进程/退出 -----
    def stop_ext(self):
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None

    def on_close(self):
        self.stop_ext()
        self.disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
