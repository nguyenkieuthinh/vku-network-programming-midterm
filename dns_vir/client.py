#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dns_client_gui.py - Giao dien do hoa (Tkinter) cho May C.

Cho phep nguoi dung nhap ten mien, IP/port cua DNS Server (May A),
bam nut de gui truy van UDP tho (tu dong dong goi/giai goi tin DNS,
khong dung thu vien ngoai) va xem ket qua/log ngay tren giao dien.

Chay:
    python3 dns_client_gui.py
"""

import socket
import struct
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox


# ============================================================================
# LOGIC DONG GOI / GIAI GOI TIN DNS (giu nguyen tu ban client dong lenh)
# ============================================================================

def build_query(domain: str) -> bytes:
    transaction_id = struct.pack("!H", random.randint(0, 65535))
    flags = struct.pack("!H", 0x0100)     # Recursion Desired
    qdcount = struct.pack("!H", 1)
    ancount = struct.pack("!H", 0)
    nscount = struct.pack("!H", 0)
    arcount = struct.pack("!H", 0)
    header = transaction_id + flags + qdcount + ancount + nscount + arcount

    qname = b"".join(
        struct.pack("B", len(part)) + part.encode()
        for part in domain.strip(".").split(".")
    ) + b"\x00"
    qtype = struct.pack("!H", 1)   # A record
    qclass = struct.pack("!H", 1)  # IN

    return header + qname + qtype + qclass


def parse_response(data: bytes):
    ancount = struct.unpack("!H", data[6:8])[0]
    if ancount == 0:
        return None

    # Bo qua Question section de tim vi tri bat dau Answer section
    offset = 12
    while data[offset] != 0:
        offset += data[offset] + 1
    offset += 1 + 2 + 2  # byte 0 + QTYPE(2) + QCLASS(2)

    # Answer: NAME(2, con tro) + TYPE(2) + CLASS(2) + TTL(4) + RDLENGTH(2) + RDATA
    offset += 2 + 2 + 2 + 4
    rdlength = struct.unpack("!H", data[offset:offset + 2])[0]
    offset += 2
    ip_bytes = data[offset:offset + rdlength]

    return socket.inet_ntoa(ip_bytes)


# ============================================================================
# GIAO DIEN TKINTER
# ============================================================================

class DnsClientGUI:
    def __init__(self, root):
        self.root = root
        root.title("May C - DNS Client")
        self._set_window_to_screen_fraction(root, fraction=0.75)
        root.minsize(560, 420)

        pad = {"padx": 8, "pady": 6}

        # --- Khung nhap thong tin ---
        form = ttk.Frame(root)
        form.pack(fill="x", **pad)

        ttk.Label(form, text="Ten mien:").grid(row=0, column=0, sticky="w")
        self.domain_var = tk.StringVar(value="abc.dns.vku")
        ttk.Entry(form, textvariable=self.domain_var, width=30).grid(
            row=0, column=1, sticky="we", padx=(4, 20)
        )

        ttk.Label(form, text="IP May A:").grid(row=0, column=2, sticky="w")
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(form, textvariable=self.ip_var, width=16).grid(
            row=0, column=3, sticky="we", padx=4
        )

        ttk.Label(form, text="Port:").grid(row=1, column=2, sticky="w", pady=(6, 0))
        self.port_var = tk.StringVar(value="9898")
        ttk.Entry(form, textvariable=self.port_var, width=8).grid(
            row=1, column=3, sticky="w", padx=4, pady=(6, 0)
        )

        ttk.Label(form, text="Timeout (s):").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.timeout_var = tk.StringVar(value="3")
        ttk.Entry(form, textvariable=self.timeout_var, width=10).grid(
            row=1, column=1, sticky="w", padx=4, pady=(6, 0)
        )

        form.columnconfigure(1, weight=1)

        # --- Nut hanh dong ---
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=(0, 6))

        self.send_btn = ttk.Button(btn_frame, text="Gui truy van", command=self.on_send)
        self.send_btn.pack(side="left")

        ttk.Button(btn_frame, text="Xoa log", command=self.clear_log).pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="San sang.")
        ttk.Label(btn_frame, textvariable=self.status_var, foreground="#555").pack(
            side="right"
        )

        # --- Ket qua noi bat ---
        result_frame = ttk.LabelFrame(root, text="Ket qua")
        result_frame.pack(fill="x", padx=8, pady=(0, 6))
        self.result_var = tk.StringVar(value="(chua co truy van)")
        ttk.Label(
            result_frame, textvariable=self.result_var, font=("Consolas", 13, "bold")
        ).pack(anchor="w", padx=8, pady=6)

        # --- Log ---
        log_frame = ttk.LabelFrame(root, text="Nhat ky")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.log_text = tk.Text(log_frame, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_text.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

        root.bind("<Return>", lambda e: self.on_send())

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
    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    def on_send(self):
        domain = self.domain_var.get().strip()
        server_ip = self.ip_var.get().strip()

        if not domain:
            messagebox.showwarning("Thieu du lieu", "Vui long nhap ten mien.")
            return
        if not server_ip:
            messagebox.showwarning("Thieu du lieu", "Vui long nhap IP cua May A.")
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Loi", "Port khong hop le.")
            return
        try:
            timeout = float(self.timeout_var.get().strip())
        except ValueError:
            timeout = 3.0

        self.send_btn.configure(state="disabled")
        self.status_var.set("Dang gui...")
        self.log(f"Gui truy van '{domain}' -> {server_ip}:{port}")

        threading.Thread(
            target=self._send_worker, args=(domain, server_ip, port, timeout), daemon=True
        ).start()

    def _send_worker(self, domain, server_ip, port, timeout):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            query = build_query(domain)
            t0 = time.time()
            sock.sendto(query, (server_ip, port))
            data, _ = sock.recvfrom(512)
            elapsed = (time.time() - t0) * 1000

            ip = parse_response(data)
            if ip:
                self._report(True, f"{domain} -> {ip}", f"Nhan phan hoi sau {elapsed:.1f} ms: {domain} -> {ip}")
            else:
                self._report(False, f"{domain}: khong tim thay (NXDOMAIN)", f"NXDOMAIN cho '{domain}'")
        except socket.timeout:
            self._report(False, "Timeout - khong nhan duoc phan hoi", "Loi: timeout, khong co phan hoi tu server.")
        except Exception as e:
            self._report(False, f"Loi: {e}", f"Loi ngoai le: {e}")
        finally:
            sock.close()

    def _report(self, ok, result_text, log_text):
        def update():
            self.result_var.set(result_text)
            self.log(log_text)
            self.status_var.set("Hoan tat." if ok else "That bai.")
            self.send_btn.configure(state="normal")
        self.root.after(0, update)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    DnsClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()