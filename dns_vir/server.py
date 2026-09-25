#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dns_server_gui.py - Giao dien do hoa (Tkinter) cho May A (DNS Server).

Bao goc logic cua server.py (tra loi tu zone.sh, tu dong dang ky ten
thuoc *.dns.vku., forward cac ten khac len 8.8.8.8) va hien thi:
    - Bang du lieu zone (ten mien -> IP)
    - Nhat ky truy van theo thoi gian thuc
    - Nut Start/Stop server, them/xoa ban ghi thu cong

Chay:
    python3 dns_server_gui.py
"""

import socket
import struct
import os
import threading
import queue
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox


# ============================================================================
# CAU HINH MAC DINH
# ============================================================================

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9898
TTL = 300
ZONE_FILE = "zone.sh"
UPSTREAM = ("8.8.8.8", 53)

AUTO_SUFFIX = "dns.vku."
AUTO_IP_MODE = "client"        # "client" hoac "fixed"
AUTO_FIXED_IP = "10.147.18.200"


# ============================================================================
# LOGIC ZONE / DNS (giu nguyen tu server.py, dua vao lop de de quan ly)
# ============================================================================

class DnsServerEngine:
    def __init__(self, zone_file, host, port, log_fn):
        self.zone_file = zone_file
        self.host = host
        self.port = port
        self.log_fn = log_fn          # callback(str) -> ghi log ra GUI (thread-safe qua queue)
        self.zone_lock = threading.Lock()
        self.sock = None
        self.running = False
        self._thread = None

    # -------- ZONE --------
    def load_zone(self):
        zone = {}
        if not os.path.exists(self.zone_file):
            return zone
        with open(self.zone_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    if not name.endswith("."):
                        name += "."
                    zone[name] = parts[1]
        return zone

    def add_record(self, name, ip):
        if not name.endswith("."):
            name += "."
        with self.zone_lock:
            zone = self.load_zone()
            if name in zone:
                return False
            with open(self.zone_file, "a", encoding="utf-8") as f:
                f.write(f"{name:<30} {ip}\n")
        return True

    def delete_record(self, name):
        if not name.endswith("."):
            name += "."
        with self.zone_lock:
            zone = self.load_zone()
            if name not in zone:
                return False
            del zone[name]
            with open(self.zone_file, "w", encoding="utf-8") as f:
                f.write("# Zone file - quan ly boi dns_server_gui.py\n")
                for n, i in zone.items():
                    f.write(f"{n:<30} {i}\n")
        return True

    def auto_register(self, name, client_ip):
        if not name.endswith(AUTO_SUFFIX):
            return None
        ip = client_ip if AUTO_IP_MODE == "client" else AUTO_FIXED_IP
        with self.zone_lock:
            zone = self.load_zone()
            if name in zone:
                return zone[name]
            try:
                with open(self.zone_file, "a", encoding="utf-8") as f:
                    f.write(f"{name:<30} {ip}\n")
                self.log_fn(f"[Auto-Register] {name} -> {ip} (tu {client_ip})")
                return ip
            except Exception as e:
                self.log_fn(f"[Auto-Register] Loi ghi file: {e}")
                return None

    # -------- GOI TIN DNS --------
    @staticmethod
    def decode_name(data, off):
        labels = []
        while True:
            ln = data[off]
            if ln == 0:
                off += 1
                break
            off += 1
            labels.append(data[off:off + ln].decode())
            off += ln
        return ".".join(labels) + ".", off

    @staticmethod
    def build_answer(query, ip):
        tid = query[:2]
        qd = struct.unpack("!H", query[4:6])[0]

        off = 12
        while query[off] != 0:
            off += query[off] + 1
        off += 1 + 4
        question = query[12:off]

        flags = 0x8180
        header = tid + struct.pack("!HHHHH", flags, qd, 1, 0, 0)

        answer = b"\xc0\x0c"
        answer += struct.pack("!HH", 1, 1)
        answer += struct.pack("!I", TTL)
        answer += struct.pack("!H", 4)
        answer += socket.inet_aton(ip)

        return header + question + answer

    # -------- XU LY 1 TRUY VAN --------
    def handle(self, data, addr, zone):
        name, _ = self.decode_name(data, 12)
        client_ip = addr[0]

        ip = zone.get(name)
        if ip:
            self.log_fn(f"[Local] {name} -> {ip} (hoi tu {client_ip})")
            self.sock.sendto(self.build_answer(data, ip), addr)
            return

        if name.endswith(AUTO_SUFFIX):
            new_ip = self.auto_register(name, client_ip)
            if new_ip:
                self.log_fn(f"[Auto-Answer] {name} -> {new_ip}")
                self.sock.sendto(self.build_answer(data, new_ip), addr)
                return

        self.log_fn(f"[Forward] {name} -> {UPSTREAM[0]} (hoi tu {client_ip})")
        try:
            up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            up.settimeout(3)
            up.sendto(data, UPSTREAM)
            resp, _ = up.recvfrom(512)
            self.sock.sendto(resp, addr)
            up.close()
        except Exception as e:
            self.log_fn(f"[Forward] Loi: {e}")

    # -------- VONG LAP SERVER --------
    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.5)
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log_fn(f"=== Server dang chay tai {self.host}:{self.port} ===")

    def _loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            zone = self.load_zone()
            threading.Thread(target=self.handle, args=(data, addr, zone), daemon=True).start()

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.log_fn("=== Server da dung ===")


# ============================================================================
# GIAO DIEN TKINTER
# ============================================================================

class DnsServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("May A - DNS Server")
        self._set_window_to_screen_fraction(root, fraction=0.75)
        root.minsize(660, 480)

        self.log_queue = queue.Queue()
        self.engine = None

        pad = {"padx": 8, "pady": 6}

        # --- Cau hinh server ---
        cfg = ttk.LabelFrame(root, text="Cau hinh server")
        cfg.pack(fill="x", **pad)

        ttk.Label(cfg, text="Zone file:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.zone_file_var = tk.StringVar(value=ZONE_FILE)
        ttk.Entry(cfg, textvariable=self.zone_file_var, width=20).grid(row=0, column=1, sticky="w")

        ttk.Label(cfg, text="Host:").grid(row=0, column=2, sticky="w", padx=6)
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(cfg, textvariable=self.host_var, width=14).grid(row=0, column=3, sticky="w")

        ttk.Label(cfg, text="Port:").grid(row=0, column=4, sticky="w", padx=6)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(cfg, textvariable=self.port_var, width=8).grid(row=0, column=5, sticky="w")

        self.start_btn = ttk.Button(cfg, text="Start server", command=self.on_start)
        self.start_btn.grid(row=0, column=6, padx=(16, 4))
        self.stop_btn = ttk.Button(cfg, text="Stop server", command=self.on_stop, state="disabled")
        self.stop_btn.grid(row=0, column=7, padx=4)

        self.status_var = tk.StringVar(value="Da dung.")
        ttk.Label(cfg, textvariable=self.status_var, foreground="#555").grid(
            row=1, column=0, columnspan=8, sticky="w", padx=6, pady=(2, 4)
        )

        # --- Body: zone table (trai) + log (phai) ---
        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Zone table
        zone_frame = ttk.LabelFrame(body, text="Zone (ten mien -> IP)")
        zone_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.tree = ttk.Treeview(zone_frame, columns=("ip",), show="headings", height=14)
        self.tree.heading("ip", text="IP")
        self.tree.column("ip", width=140)
        self.tree["columns"] = ("name", "ip")
        self.tree.heading("name", text="Ten mien")
        self.tree.heading("ip", text="IP")
        self.tree.column("name", width=220)
        self.tree.column("ip", width=140)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        add_frame = ttk.Frame(zone_frame)
        add_frame.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(add_frame, text="Ten:").grid(row=0, column=0, sticky="w")
        self.new_name_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_name_var, width=18).grid(row=0, column=1, padx=4)
        ttk.Label(add_frame, text="IP:").grid(row=0, column=2, sticky="w")
        self.new_ip_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_ip_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Button(add_frame, text="Them", command=self.on_add).grid(row=0, column=4, padx=(6, 2))
        ttk.Button(add_frame, text="Xoa muc chon", command=self.on_delete).grid(row=0, column=5, padx=2)
        ttk.Button(add_frame, text="Lam moi", command=self.refresh_zone_table).grid(row=0, column=6, padx=2)

        # Log
        log_frame = ttk.LabelFrame(body, text="Nhat ky truy van")
        log_frame.pack(side="right", fill="both", expand=True)

        self.log_text = tk.Text(log_frame, wrap="word", state="disabled", font=("Consolas", 13))
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        self.refresh_zone_table()
        self.root.after(150, self._drain_log_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    @staticmethod
    def _set_window_to_screen_fraction(root, fraction=0.75):
        """Dat kich thuoc cua so = ty le (fraction) man hinh chinh, can giua man hinh."""
        root.update_idletasks()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        w = int(screen_w * fraction)
        h = int(screen_h * fraction)
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    def log_from_thread(self, msg: str):
        """Goi tu thread nen: chi day vao queue, khong dong cham Tk truc tiep."""
        self.log_queue.put(msg)

    def _drain_log_queue(self):
        drained = False
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            ts = time.strftime("%H:%M:%S")
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"[{ts}] {msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            drained = True
        if drained:
            self.refresh_zone_table()
        self.root.after(400, self._drain_log_queue)

    def refresh_zone_table(self):
        zone_file = self.zone_file_var.get().strip() or ZONE_FILE
        self.tree.delete(*self.tree.get_children())
        if not os.path.exists(zone_file):
            return
        try:
            with open(zone_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        self.tree.insert("", "end", values=(parts[0], parts[1]))
        except Exception as e:
            self.log_from_thread(f"Loi doc zone file: {e}")

    # ------------------------------------------------------------------
    def on_start(self):
        if self.engine and self.engine.running:
            return
        zone_file = self.zone_file_var.get().strip() or ZONE_FILE
        host = self.host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Loi", "Port khong hop le.")
            return

        self.engine = DnsServerEngine(zone_file, host, port, self.log_from_thread)
        try:
            self.engine.start()
        except OSError as e:
            messagebox.showerror("Loi khi khoi dong", str(e))
            self.engine = None
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set(f"Dang chay tai {host}:{port}")

    def on_stop(self):
        if self.engine:
            self.engine.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("Da dung.")

    def on_add(self):
        name = self.new_name_var.get().strip()
        ip = self.new_ip_var.get().strip()
        if not name or not ip:
            messagebox.showwarning("Thieu du lieu", "Nhap ten mien va IP.")
            return
        zone_file = self.zone_file_var.get().strip() or ZONE_FILE
        engine = self.engine or DnsServerEngine(zone_file, "", 0, self.log_from_thread)
        ok = engine.add_record(name, ip)
        if ok:
            self.log_from_thread(f"[Thu cong] Them {name} -> {ip}")
            self.new_name_var.set("")
            self.new_ip_var.set("")
            self.refresh_zone_table()
        else:
            messagebox.showinfo("Thong bao", "Ten mien da ton tai.")

    def on_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Thong bao", "Chon 1 dong trong bang de xoa.")
            return
        name = self.tree.item(sel[0])["values"][0]
        zone_file = self.zone_file_var.get().strip() or ZONE_FILE
        engine = self.engine or DnsServerEngine(zone_file, "", 0, self.log_from_thread)
        if engine.delete_record(str(name)):
            self.log_from_thread(f"[Thu cong] Xoa {name}")
            self.refresh_zone_table()

    def on_close(self):
        if self.engine and self.engine.running:
            self.engine.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # --- Chinh co chu toan cuc o day: tang/giam so nay de doi kich thuoc ---
        BASE_FONT_SIZE = 13
        base_font = ("Segoe UI", BASE_FONT_SIZE)

        style.configure(".", font=base_font)
        style.configure("TButton", font=base_font)
        style.configure("TLabel", font=base_font)
        style.configure("TLabelframe.Label", font=(base_font[0], BASE_FONT_SIZE, "bold"))
        root.option_add("*Font", base_font)

        # Do chieu cao thuc te cua font (co tinh den DPI scaling cua he thong)
        # de khong bi chong chu giua cac dong trong Treeview.
        row_font = tkfont.Font(family=base_font[0], size=BASE_FONT_SIZE)
        row_height = row_font.metrics("linespace") + 16

        style.configure("Treeview", font=row_font, rowheight=row_height)
        style.configure("Treeview.Heading", font=(base_font[0], BASE_FONT_SIZE, "bold"))
    except Exception:
        pass
    DnsServerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()