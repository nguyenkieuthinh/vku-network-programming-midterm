#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 chat_server_gui.py - Chat TCP server GUI (Tkinter)
============================================================================
 - Bật/tắt server
 - Xem danh sách client đang online
 - Xem log tin nhắn
 - Hỗ trợ NHIỀU client cùng lúc

 Chạy:
   python3 chat_server_gui.py
============================================================================
"""

import socket
import threading
import queue
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox


# ============================================================================
# CẤU HÌNH
# ============================================================================

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9999


# ============================================================================
# ENGINE - Logic chat server (thread-safe)
# ============================================================================

class ChatServerEngine:
    """
    Chat server:
      - Lắng nghe client TCP
      - Mỗi client 1 thread
      - Broadcast tin nhắn
      - Cập nhật danh sách client cho GUI
    """

    def __init__(self, host, port, log_fn, clients_fn):
        """
        log_fn    : callback(str) — ghi log
        clients_fn: callback(list) — cập nhật danh sách client GUI
        """
        self.host = host
        self.port = port
        self.log_fn = log_fn
        self.clients_fn = clients_fn
        self.srv = None
        self.running = False
        self._thread = None
        self.clients = {}                 # { socket: nickname }
        self.lock = threading.Lock()

    # -------------------- TIỆN ÍCH --------------------

    def broadcast(self, msg: str, exclude=None):
        """Gửi msg cho mọi client (trừ exclude)."""
        with self.lock:
            targets = list(self.clients.keys())

        for c in targets:
            if c is exclude:
                continue
            try:
                c.sendall(msg.encode("utf-8"))
            except Exception:
                self.remove_client(c)

    def remove_client(self, c):
        """Xóa client + thông báo."""
        with self.lock:
            if c not in self.clients:
                return
            nick = self.clients.pop(c)
            try:
                c.close()
            except Exception:
                pass

        self.log_fn(f"[Server] {nick} đã rời")
        self.broadcast(f"[System] {nick} đã rời phòng\n")
        self.update_clients_gui()

    def update_clients_gui(self):
        """Gọi callback cập nhật GUI."""
        with self.lock:
            names = list(self.clients.values())
        self.clients_fn(names)

    # -------------------- XỬ LÝ 1 CLIENT --------------------

    def handle_client(self, conn, addr):
        """Mỗi client 1 thread: hỏi nick → nhận tin → broadcast."""
        nick = None
        try:
            # 1. Hỏi nickname
            conn.sendall(b"Nhap nickname: ")
            data = conn.recv(64)
            if not data:
                return
            nick = data.decode("utf-8", errors="ignore").strip() or f"User_{addr[1]}"

            # 2. Thêm vào danh sách
            with self.lock:
                self.clients[conn] = nick

            self.log_fn(f"[Server] {nick} ({addr[0]}:{addr[1]}) đã vào")
            self.broadcast(f"[System] {nick} đã vào phòng\n", exclude=conn)
            self.update_clients_gui()

            # Chào riêng
            conn.sendall(
                f"[System] Chào {nick}! Gõ 'quit' để thoát.\n".encode("utf-8")
            )

            # 3. Vòng lặp nhận tin nhắn
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
                msg = data.decode("utf-8", errors="ignore").strip()
                if not msg:
                    continue

                if msg.lower() in ("quit", "exit", "/quit"):
                    conn.sendall(b"[System] Tam biet!\n")
                    break

                if msg == "/list":
                    with self.lock:
                        names = ", ".join(self.clients.values()) or "(trống)"
                    conn.sendall(f"[System] Đang online: {names}\n".encode("utf-8"))
                    continue

                full = f"[{nick}] {msg}"
                self.log_fn(full)
                self.broadcast(full + "\n", exclude=conn)
                try:
                    conn.sendall(f"[Bạn] {msg}\n".encode("utf-8"))
                except Exception:
                    pass

        except Exception as e:
            self.log_fn(f"[Server] Lỗi client {addr}: {e}")
        finally:
            self.remove_client(conn)

    # -------------------- VÒNG LẶP SERVER --------------------

    def start(self):
        """Khởi động server + thread accept."""
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((self.host, self.port))
        self.srv.listen(10)
        self.srv.settimeout(0.5)          # cho loop check self.running
        self.running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        self.log_fn(f"=== Chat server chạy tại {self.host}:{self.port} ===")

    def _accept_loop(self):
        """Vòng lặp accept client mới."""
        while self.running:
            try:
                conn, addr = self.srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            self.log_fn(f"[Server] Kết nối mới từ {addr}")
            threading.Thread(
                target=self.handle_client,
                args=(conn, addr),
                daemon=True
            ).start()

    def stop(self):
        """Dừng server + đóng mọi client."""
        self.running = False
        with self.lock:
            for c in list(self.clients.keys()):
                try:
                    c.close()
                except Exception:
                    pass
            self.clients.clear()
        if self.srv:
            try:
                self.srv.close()
            except Exception:
                pass
        self.log_fn("=== Chat server đã dừng ===")


# ============================================================================
# GUI
# ============================================================================

class ChatServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("Chat Server - Máy A")
        self._set_window_fraction(root, 0.7)
        root.minsize(700, 500)

        self.log_queue = queue.Queue()
        self.engine = None

        # ---- Cấu hình ----
        cfg = ttk.LabelFrame(root, text="Cấu hình server", padding=10)
        cfg.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(cfg, text="Host:").grid(row=0, column=0, sticky="w", padx=4)
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        ttk.Entry(cfg, textvariable=self.host_var, width=14).grid(row=0, column=1, padx=4)

        ttk.Label(cfg, text="Port:").grid(row=0, column=2, sticky="w", padx=4)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        ttk.Entry(cfg, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=4)

        self.start_btn = ttk.Button(cfg, text="▶ Start", command=self.on_start)
        self.start_btn.grid(row=0, column=4, padx=(16, 4))

        self.stop_btn = ttk.Button(cfg, text="⏹ Stop",
                                   command=self.on_stop, state="disabled")
        self.stop_btn.grid(row=0, column=5, padx=4)

        self.status_var = tk.StringVar(value="⏹ Đã dừng")
        self.status_lbl = ttk.Label(cfg, textvariable=self.status_var,
                                     font=("Arial", 10, "bold"), foreground="red")
        self.status_lbl.grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=(6, 0))

        # ---- Body: 2 cột ----
        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Cột trái: danh sách client
        left = ttk.LabelFrame(body, text="Client đang online", padding=6)
        left.pack(side="left", fill="both", expand=False, padx=(0, 5))

        self.client_listbox = tk.Listbox(left, width=20, font=("Arial", 11))
        self.client_listbox.pack(fill="both", expand=True)

        # Cột phải: log
        right = ttk.LabelFrame(body, text="Log tin nhắn", padding=6)
        right.pack(side="right", fill="both", expand=True)

        self.log_text = tk.Text(right, wrap="word", state="disabled",
                                 font=("Consolas", 11), bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white")
        self.log_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(right, command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

        # Nút xóa log
        ttk.Button(right, text="🗑 Xóa log",
                   command=self.clear_log).place(relx=1.0, x=-25, y=2, anchor="ne")

        # Khởi động
        self.root.after(200, self._drain_log_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    @staticmethod
    def _set_window_fraction(root, fraction=0.7):
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = int(sw * fraction), int(sh * fraction)
        x, y = (sw - w) // 2, (sh - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

    def log_from_thread(self, msg):
        self.log_queue.put(msg)

    def _drain_log_queue(self):
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
        self.root.after(300, self._drain_log_queue)

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def update_clients_gui(self, names):
        """Callback: cập nhật danh sách client (chạy trong main thread)."""
        def _update():
            self.client_listbox.delete(0, "end")
            for n in names:
                self.client_listbox.insert("end", n)
            self.client_count_lbl.config(text=f"Tổng: {len(names)}")
        self.root.after(0, _update)

    # ------------------------------------------------------------------
    def on_start(self):
        if self.engine and self.engine.running:
            return

        host = self.host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi", "Port không hợp lệ")
            return

        self.engine = ChatServerEngine(host, port, self.log_from_thread, self.update_clients_gui)
        try:
            self.engine.start()
        except OSError as e:
            messagebox.showerror("Lỗi khởi động", str(e))
            self.engine = None
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set(f"✅ Đang chạy tại {host}:{port}")
        self.status_lbl.configure(foreground="green")

    def on_stop(self):
        if self.engine:
            self.engine.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("⏹ Đã dừng")
        self.status_lbl.configure(foreground="red")

    def on_close(self):
        if self.engine and self.engine.running:
            self.engine.stop()
        self.root.destroy()


# ============================================================================
# MAIN
# ============================================================================

def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        BASE = 11
        base_font = ("Segoe UI", BASE)
        style.configure(".", font=base_font)
        style.configure("TButton", font=base_font)
        style.configure("TLabel", font=base_font)
        style.configure("TLabelframe.Label", font=(base_font[0], BASE, "bold"))
        root.option_add("*Font", base_font)
    except Exception:
        pass

    ChatServerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()