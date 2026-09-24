#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 DNS SERVER (Máy A) - Có tính năng AUTO-REGISTER
============================================================================
 Chức năng:
   1. Tra cứu zone.txt để trả lời
   2. Nếu tên thuộc ".dns.vku." mà chưa có -> TỰ ĐỘNG THÊM vào zone.txt
   3. Nếu tên khác (google.com...) -> forward lên 8.8.8.8

 Cách chạy:
   python3 server.py

 Test:
   python3 client.py myname.test.dns.vku 127.0.0.1 9898
   python3 client.py abc.dns.vku 127.0.0.1 9898        # tự đăng ký
============================================================================
"""

import socket
import struct
import os
import threading

# ============================================================================
# 1. CẤU HÌNH
# ============================================================================

HOST = "0.0.0.0"
PORT = 9898
TTL  = 300
ZONE_FILE = "zone.sh"
UPSTREAM  = ("8.8.8.8", 53)

# --- Cấu hình AUTO-REGISTER ---
AUTO_SUFFIX = "dns.vku."      # Chỉ auto-register tên kết thúc bằng suffix này
AUTO_IP_MODE = "client"       # "client" = gán IP của client
                              # "fixed"  = gán IP cố định bên dưới

                              
# Lock để tránh 2 thread ghi file cùng lúc
zone_lock = threading.Lock()


# ============================================================================
# 2. ĐỌC FILE ZONE
# ============================================================================

def load_zone():
    """Đọc zone.txt -> dict { tên_miền: IP }."""
    zone = {}
    if not os.path.exists(ZONE_FILE):
        return zone

    with open(ZONE_FILE, encoding="utf-8") as f:
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


# ============================================================================
# 3. AUTO-REGISTER
# ============================================================================

def auto_register(name, client_ip):
    """
    Tự động thêm tên miền mới vào zone.txt.

    Tham số:
        name      : tên miền cần thêm (đã có dấu chấm cuối)
        client_ip : IP của client (dùng nếu AUTO_IP_MODE = "client")

    Trả về:
        IP được gán, hoặc None nếu không thêm được
    """
    # Kiểm tra tên có thuộc zone cho phép không
    if not name.endswith(AUTO_SUFFIX):
        return None

    # Chọn IP để gán
    ip = client_ip if AUTO_IP_MODE == "client" else AUTO_FIXED_IP

    # Dùng lock để tránh race condition
    with zone_lock:
        # Kiểm tra lại xem tên đã có chưa (có thể thread khác vừa thêm)
        zone = load_zone()
        if name in zone:
            return zone[name]        # Đã có -> trả IP cũ

        # Ghi thêm 1 dòng vào file
        try:
            with open(ZONE_FILE, "a", encoding="utf-8") as f:
                f.write(f"{name:<30} {ip}\n")
            print(f"[Auto-Register] {name} -> {ip} (từ {client_ip})")
            return ip
        except Exception as e:
            print(f"[Auto-Register] Lỗi ghi file: {e}")
            return None


# ============================================================================
# 4. GIẢI MÃ TÊN MIỀN
# ============================================================================

def decode_name(data, off):
    """Giải mã tên miền từ gói DNS -> (tên, offset_mới)."""
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


# ============================================================================
# 5. ĐÓNG GÓI PHẢN HỒI
# ============================================================================

def build_answer(query, ip):
    """Tạo gói response DNS từ query + IP."""
    # Header
    tid = query[:2]
    qd  = struct.unpack("!H", query[4:6])[0]

    # Tìm hết Question section
    off = 12
    while query[off] != 0:
        off += query[off] + 1
    off += 1 + 4
    question = query[12:off]

    # Header response (No error)
    flags = 0x8180
    header = tid + struct.pack("!HHHHH", flags, qd, 1, 0, 0)

    # Answer section
    answer  = b"\xc0\x0c"                      # pointer tới name ở offset 12
    answer += struct.pack("!HH", 1, 1)         # TYPE=A, CLASS=IN
    answer += struct.pack("!I", TTL)           # TTL
    answer += struct.pack("!H", 4)             # RDLENGTH
    answer += socket.inet_aton(ip)             # RDATA

    return header + question + answer


# ============================================================================
# 6. XỬ LÝ 1 TRUY VẤN
# ============================================================================

def handle(data, addr, sock, zone):
    """
    Xử lý 1 query:
      1. Có trong zone     -> trả lời
      2. Thuộc .dns.vku.   -> auto-register + trả lời
      3. Còn lại           -> forward lên 8.8.8.8
    """
    name, _ = decode_name(data, 12)
    client_ip = addr[0]

    # --- 1. Có trong zone ---
    ip = zone.get(name)
    if ip:
        print(f"[Local] {name} -> {ip}")
        sock.sendto(build_answer(data, ip), addr)
        return

    # --- 2. Auto-register ---
    if name.endswith(AUTO_SUFFIX):
        new_ip = auto_register(name, client_ip)
        if new_ip:
            print(f"[Auto-Answer] {name} -> {new_ip}")
            sock.sendto(build_answer(data, new_ip), addr)
            return

    # --- 3. Forward ---
    print(f"[Forward] {name} -> {UPSTREAM[0]}")
    try:
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up.settimeout(3)
        up.sendto(data, UPSTREAM)
        resp, _ = up.recvfrom(512)
        sock.sendto(resp, addr)
    except Exception as e:
        print(f"[Forward] Lỗi: {e}")
    finally:
        up.close()


# ============================================================================
# 7. MAIN
# ============================================================================

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))

    print(f"=== DNS Server (port {PORT}) ===")
    print(f"=== Forward: {UPSTREAM[0]} ===")
    print(f"=== Auto-register zone: *.{AUTO_SUFFIX} ===")
    print(f"=== IP mode: {AUTO_IP_MODE} ===")
    print()

    zone = load_zone()
    for n, i in zone.items():
        print(f"   {n:<30} -> {i}")
    print("\nĐang chờ truy vấn...\n")

    try:
        while True:
            data, addr = sock.recvfrom(512)
            zone = load_zone()

            threading.Thread(
                target=handle,
                args=(data, addr, sock, zone),
                daemon=True
            ).start()

    except KeyboardInterrupt:
        print("\nDừng server.")
    finally:
        sock.close()


# ============================================================================
# 8. ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()