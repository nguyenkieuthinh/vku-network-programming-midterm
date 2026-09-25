#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 dns_client_gui.py - GUI DNS Client (Máy C)
============================================================================
 - Nhập tên miền, IP server, port
 - Bấm Tra cứu (hoặc Enter) → gửi query UDP
 - Hiển thị IP kết quả nổi bật
 - Log chi tiết + thời gian phản hồi

 Chạy:
   python3 dns_client_gui.py
============================================================================
"""

import socket
import struct
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox


# ============================================================================
# 1. ĐÓNG GÓI / GIẢI GÓI DNS
# ============================================================================

def build_query(domain: str) -> bytes:
    """
    Tạo gói DNS query loại A (IPv4).
    Cấu trúc: Header(12) + QNAME + QTYPE(2) + QCLASS(2)
    """
    # --- Header ---
    tid    = struct.pack("!H", random.randint(0, 65535))   # Transaction ID
    flags  = struct.pack("!H", 0x0100)                     # RD=1 (đệ quy)
    counts = struct.pack("!HHHH", 1, 0, 0, 0)              # QD=1, AN=NS=AR=0
    header = tid + flags + counts

    # --- QNAME: chia "abc.dns.vku" thành labels ---
    qname = b"".join(
        struct.pack("B", len(p)) + p.encode()
        for p in domain.strip(".").split(".")
    ) + b"\x00"

    # --- QTYPE=A, QCLASS=IN ---
    qtype  = struct.pack("!H", 1)
    qclass = struct.pack("!H", 1)

    return header + qname + qtype + qclass


def parse_response(data: bytes):
    """
    Giải gói DNS response, trả về IP hoặc None.
    Bỏ qua phần Header + Question, đọc bản ghi A đầu tiên.
    """
    ancount = struct.unpack("!H", data[6:8])[0]
    if ancount == 0:
        return None                            # NXDOMAIN

    # Nhảy qua Question section
    off = 12
    while data[off] != 0:
        off += data[off] + 1
    off += 1 + 2 + 2                            # +null +QTYPE +QCLASS

    # Đọc Answer section
    off += 2                                    # NAME (compression pointer)
    off += 2 + 2 + 4                            # TYPE + CLASS + TTL
    rdlength = struct.unpack("!H", data[off:off+2])[0]
    off += 2
    return socket.inet_ntoa(data[off:off+rdlength])


# ============================================================================
# 2. GUI
# ============================================================================

class DnsClientGUI:

    # -------- Cấu hình mặc định --------
    DEFAULT_DOMAIN  = "myname.test.dns.vku"
    DEFAULT_IP      = "10.147.18.200"
    DEFAULT_PORT    = "9898"
    DEFAULT_TIMEOUT = "3"

    def __init__(self, root):
        self.root = root
        root.title("Máy C — DNS Client")
        self._set_window_fraction(root, 0.55)
        root.minsize(560, 480)

        # ---- Style ----
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # ---- Phần nhập liệu ----
        form = ttk.LabelFrame(root, text="Thông tin truy vấn", padding=10)
        form.pack(fill="x", padx=10, pady=(10, 5))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # Tên miền
        ttk.Label(form, text="Tên miền:").grid(row=0, column=0, sticky="w", padx=4)
        self.domain_var = tk.StringVar(value=self.DEFAULT_DOMAIN)
        e = ttk.Entry(form, textvariable=self.domain_var, font=("Arial", 11))
        e.grid(row=0, column=1, columnspan=3, sticky="we", padx=4, pady=4)

        # IP server
        ttk.Label(form, text="IP Server:").grid(row=1, column=0, sticky="w", padx=4)
        self.ip_var = tk.StringVar(value=self.DEFAULT_IP)
        ttk.Entry(form, textvariable=self.ip_var, width=18).grid(
            row=1, column=1, sticky="we", padx=4, pady=4)

        # Port
        ttk.Label(form, text="Port:").grid(row=1, column=2, sticky="w", padx=4)
        self.port_var = tk.StringVar(value=self.DEFAULT_PORT)
        ttk.Entry(form, textvariable=self.port_var, width=10).grid(
            row=1, column=3, sticky="we", padx=4, pady=4)

        # Timeout
        ttk.Label(form, text="Timeout (s):").grid(row=2, column=0, sticky="w", padx=4)
        self.timeout_var = tk.StringVar(value=self.DEFAULT_TIMEOUT)
        ttk.Entry(form, textvariable=self.timeout_var, width=8).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)

        # ---- Hàng nút ----
        btns = ttk.Frame(root)
        btns.pack(fill="x", padx=10, pady=(0, 5))

        self.query_btn = tk.Button(
            btns, text="🔍  Tra cứu", font=("Arial", 11, "bold"),
            bg="#3498db", fg="white", activebackground="#2980b9",
            padx=16, pady=6, relief="flat", cursor="hand2",
            command=self.on_query
        )
        self.query_btn.pack(side="left", padx=2)

        tk.Button(
            btns, text="🗑  Xóa log", font=("Arial", 10),
            bg="#95a5a6", fg="white", activebackground="#7f8c8d",
            padx=12, pady=6, relief="flat", cursor="hand2",
            command=self.clear_log
        ).pack(side="left", padx=2)

        # Status bên phải
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.status_lbl = tk.Label(btns, textvariable=self.status_var,
                                    fg="#7f8c8d", font=("Arial", 10))
        self.status_lbl.pack(side="right", padx=6)

        # ---- Kết quả nổi bật ----
        res = ttk.LabelFrame(root, text="Kết quả", padding=10)
        res.pack(fill="x", padx=10, pady=5)

        self.result_var = tk.StringVar(value="(chưa có truy vấn)")
        self.result_lbl = tk.Label(
            res, textvariable=self.result_var,
            font=("Consolas", 14, "bold"), fg="#7f8c8d",
            anchor="w", justify="left"
        )
        self.result_lbl.pack(fill="x")

        # ---- Log ----
        logf = ttk.LabelFrame(root, text="Nhật ký", padding=6)
        logf.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.log_text = tk.Text(
            logf, wrap="word", state="disabled",
            font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(logf, command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

        # Bind Enter
        root.bind("<Return>", lambda e: self.on_query())

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _set_window_fraction(root, fraction=0.55):
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = int(sw * fraction), int(sh * fraction)
        x, y = (sw - w) // 2, (sh - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def set_status(self, text, color="#7f8c8d"):
        self.status_var.set(text)
        self.status_lbl.configure(fg=color)

    # ------------------------------------------------------------------
    # Xử lý nút Tra cứu
    # ------------------------------------------------------------------

    def on_query(self):
        # --- Validate ---
        domain = self.domain_var.get().strip()
        ip     = self.ip_var.get().strip()

        if not domain:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập tên miền.")
            return
        if ".." in domain:
            messagebox.showerror("Lỗi", "Tên miền không hợp lệ (có '..')")
            return
        if not ip:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập IP server.")
            return

        try:
            port = int(self.port_var.get().strip())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Port không hợp lệ (1–65535).")
            return

        try:
            timeout = float(self.timeout_var.get().strip())
            if timeout <= 0:
                raise ValueError
        except ValueError:
            timeout = 3.0

        # --- Disable nút, chạy thread ---
        self.query_btn.configure(state="disabled")
        self.set_status("Đang tra cứu...", "#f39c12")
        self.result_var.set("Đang chờ phản hồi...")
        self.result_lbl.configure(fg="#f39c12")
        self.log(f"Hỏi '{domain}' → {ip}:{port}")

        threading.Thread(
            target=self._query_worker,
            args=(domain, ip, port, timeout),
            daemon=True
        ).start()

    def _query_worker(self, domain, ip, port, timeout):
        """Chạy trong thread riêng — không block GUI."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            query = build_query(domain)
            t0 = time.time()
            sock.sendto(query, (ip, port))
            data, _ = sock.recvfrom(512)
            elapsed_ms = (time.time() - t0) * 1000

            result = parse_response(data)
            if result:
                self._report_success(domain, result, elapsed_ms)
            else:
                self._report_fail(f"NXDOMAIN — '{domain}' không tồn tại",
                                  f"Nhận NXDOMAIN sau {elapsed_ms:.1f} ms")
        except socket.timeout:
            self._report_fail("⏱ Timeout — server không phản hồi",
                              f"Timeout sau {timeout}s")
        except Exception as e:
            self._report_fail(f"Lỗi: {e}", f"Exception: {e}")
        finally:
            sock.close()

    # ------------------------------------------------------------------
    # Báo kết quả (đẩy về main thread)
    # ------------------------------------------------------------------

    def _report_success(self, domain, ip, ms):
        def update():
            self.result_var.set(f"✓  {domain}  →  {ip}")
            self.result_lbl.configure(fg="#27ae60")
            self.set_status("Thành công", "#27ae60")
            self.log(f"Kết quả: {ip}  ({ms:.1f} ms)")
            self.query_btn.configure(state="normal")
        self.root.after(0, update)

    def _report_fail(self, short_msg, log_msg):
        def update():
            self.result_var.set(f"✗  {short_msg}")
            self.result_lbl.configure(fg="#e74c3c")
            self.set_status("Thất bại", "#e74c3c")
            self.log(log_msg)
            self.query_btn.configure(state="normal")
        self.root.after(0, update)


# ============================================================================
# MAIN
# ============================================================================

def main():
    root = tk.Tk()
    DnsClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()