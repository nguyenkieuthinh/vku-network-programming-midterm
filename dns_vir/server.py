#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 DNS SERVER ĐƠN GIẢN (Máy A) - Mô phỏng dịch vụ phân giải tên miền
============================================================================
 Chức năng:
   - Lắng nghe truy vấn DNS (loại A - IPv4) qua UDP
   - Tra cứu trong file zone (zone.sh) để trả lời
   - Nếu không có trong zone -> chuyển tiếp (forward) lên DNS công cộng
   - Hỗ trợ nhiều client cùng lúc bằng threading

 Cách chạy:
   python3 server.py

 Test:
   python3 client.py myname.test.dns.vku 127.0.0.1 9898
============================================================================
"""

import socket       # Giao tiếp mạng (UDP socket)
import struct       # Đóng gói/giải gói dữ liệu nhị phân
import os           # Kiểm tra file tồn tại
import threading    # Chạy nhiều client cùng lúc


# ============================================================================
# 1. CẤU HÌNH SERVER
# ============================================================================

HOST = "0.0.0.0"          # Lắng nghe trên mọi interface (LAN, VPN, loopback)
                          # Nếu để "127.0.0.1" thì chỉ máy local truy cập được
PORT = 9898               # Cổng UDP server lắng nghe
                          # (Cổng chuẩn DNS là 53, nhưng cần sudo nên dùng 9898)
TTL  = 300                # Time-To-Live: thời gian client cache kết quả (giây)
ZONE_FILE = "zone.sh"    # File chứa dữ liệu zone (tên miền -> IP)
UPSTREAM  = ("8.8.8.8", 53)   # DNS công cộng để forward khi không có trong zone


# ============================================================================
# 2. ĐỌC FILE ZONE
# ============================================================================

def load_zone():
    """
    Đọc file zone.txt và trả về dict { tên_miền: IP }.

    Định dạng file:
        # Comment
        myname.test.dns.vku.   10.147.18.200
        www.dns.vku.           10.147.18.200

    Lưu ý:
        - Dòng bắt đầu bằng # là comment -> bỏ qua
        - Dòng trống -> bỏ qua
        - Tên miền sẽ được tự động thêm dấu chấm cuối (FQDN)
    """
    zone = {}                                   # Dict rỗng

    # Nếu file không tồn tại -> trả dict rỗng (không crash)
    if not os.path.exists(ZONE_FILE):
        return zone

    # Mở file để đọc (tự đóng khi xong)
    with open(ZONE_FILE, encoding="utf-8") as f:
        for line in f:                          # Đọc từng dòng
            line = line.strip()                 # Bỏ khoảng trắng đầu/cuối

            # Bỏ qua dòng trống hoặc dòng comment
            if not line or line.startswith("#"):
                continue

            # Tách theo khoảng trắng: ["tên_miền", "IP"]
            parts = line.split()

            # Cần ít nhất 2 cột mới hợp lệ
            if len(parts) >= 2:
                name = parts[0]

                # Chuẩn hóa FQDN: thêm dấu chấm cuối nếu thiếu
                if not name.endswith("."):
                    name += "."

                # Gán vào dict
                zone[name] = parts[1]

    return zone


# ============================================================================
# 3. GIẢI MÃ TÊN MIỀN TRONG GÓI TIN DNS
# ============================================================================

def decode_name(data, off):
    """
    Giải mã tên miền từ gói tin DNS (dạng labels).

    DNS mã hóa tên miền như sau:
        "www.google.com" -> [3]www[6]google[3]com[0]
                             ^    ^         ^    ^
                             độ dài 3       độ dài 0 = hết tên

    Tham số:
        data: bytes - nội dung gói tin
        off:  int   - vị trí bắt đầu đọc tên

    Trả về:
        (tên_miền, offset_mới)
    """
    labels = []                                 # Danh sách các phần tên

    while True:
        ln = data[off]                          # Đọc byte độ dài label

        if ln == 0:                             # Byte 0 = hết tên
            off += 1                            # Nhảy qua byte 0
            break

        off += 1                                # Nhảy qua byte độ dài

        # Đọc ln byte tiếp theo, giải mã UTF-8
        labels.append(data[off:off + ln].decode())
        off += ln                               # Nhảy qua label vừa đọc

    # Ghép lại bằng dấu chấm, thêm dấu chấm cuối (FQDN)
    return ".".join(labels) + ".", off


# ============================================================================
# 4. ĐÓNG GÓI PHẢN HỒI DNS
# ============================================================================

def build_answer(query, ip):
    """
    Tạo gói response DNS từ query của client.

    Cấu trúc gói DNS:
        +------------------+
        | Header (12 byte) |  <- Transaction ID, Flags, Counts
        +------------------+
        | Question         |  <- Echo lại y hệt câu hỏi của client
        +------------------+
        | Answer           |  <- Bản ghi A (IP)
        +------------------+
    """
    # --- HEADER ---
    tid = query[:2]                             # Transaction ID (2 byte đầu)
                                                # Phải copy y nguyên từ query
                                                # để client match request/response

    qd = struct.unpack("!H", query[4:6])[0]     # QDCOUNT = số câu hỏi
                                                # "!H" = unsigned short,
                                                #        big-endian (network order)

    # --- QUESTION SECTION ---
    # Bỏ qua question section để tìm offset kết thúc
    off = 12                                    # Bắt đầu sau 12 byte header
    while query[off] != 0:                      # Tìm byte 0 kết thúc tên miền
        off += query[off] + 1                   # Nhảy qua label
    off += 1 + 4                                # +1 (byte 0) +2 (QTYPE) +2 (QCLASS)

    question = query[12:off]                    # Copy nguyên Question section

    # --- HEADER RESPONSE ---
    # Flags 0x8180 = 1000 0001 1000 0000
    #   - QR  = 1 (response)
    #   - RD  = 1 (recursion desired - copy từ query)
    #   - RA  = 1 (recursion available)
    #   - RCODE = 0 (no error)
    flags = 0x8180

    # Đóng gói header: TID + Flags + QD + AN + NS + AR
    # ANCOUNT = 1 (có 1 answer)
    header = tid + struct.pack("!HHHHH", flags, qd, 1, 0, 0)

    # --- ANSWER SECTION ---
    # Dùng compression pointer: 0xC00C = "tên miền ở offset 12"
    # Tiết kiệm dung lượng thay vì ghi lại tên miền đầy đủ
    answer  = b"\xc0\x0c"

    # TYPE = A (1), CLASS = IN (1)
    answer += struct.pack("!HH", 1, 1)

    # TTL (4 byte)
    answer += struct.pack("!I", TTL)

    # RDLENGTH = 4 (IPv4 dài 4 byte)
    answer += struct.pack("!H", 4)

    # RDATA = 4 byte địa chỉ IP
    answer += socket.inet_aton(ip)              # "10.147.18.200" -> bytes

    # Ghép 3 phần: header + question + answer
    return header + question + answer


# ============================================================================
# 5. XỬ LÝ 1 TRUY VẤN
# ============================================================================

def handle(data, addr, sock, zone):
    """
    Xử lý 1 query DNS:
      - Nếu tên có trong zone -> trả lời local
      - Nếu không có          -> forward lên 8.8.8.8

    Tham số:
        data: bytes  - nội dung query từ client
        addr: tuple  - (IP_client, port_client)
        sock: socket - socket chính để gửi response
        zone: dict   - dữ liệu zone hiện tại
    """
    # Đọc tên miền từ query (bắt đầu từ offset 12)
    name, _ = decode_name(data, 12)

    # Tra cứu trong zone
    ip = zone.get(name)

    # --- TRƯỜNG HỢP 1: CÓ TRONG ZONE ---
    if ip:
        print(f"[Local] {name} -> {ip}")
        # Gửi response cho client
        sock.sendto(build_answer(data, ip), addr)
        return                                   # Xong

    # --- TRƯỜNG HỢP 2: KHÔNG CÓ -> FORWARD ---
    print(f"[Forward] {name} -> {UPSTREAM[0]}")

    try:
        # Tạo socket mới để nói chuyện với upstream
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up.settimeout(3)                        # Timeout 3 giây

        # Gửi NGUYÊN gói query của client lên 8.8.8.8
        up.sendto(data, UPSTREAM)

        # Nhận response từ 8.8.8.8 (tối đa 512 byte)
        resp, _ = up.recvfrom(512)

        # Chuyển tiếp response về client
        sock.sendto(resp, addr)

    except Exception as e:
        print(f"[Forward] Lỗi: {e}")

    finally:
        up.close()                              # Đóng socket upstream


# ============================================================================
# 6. HÀM MAIN - KHỞI TẠO VÀ VÒNG LẶP CHÍNH
# ============================================================================

def main():
    """Khởi tạo server, lắng nghe và xử lý truy vấn."""

    # --- TẠO SOCKET UDP ---
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # --- BIND VÀO ĐỊA CHỈ ---
    sock.bind((HOST, PORT))

    # --- IN THÔNG TIN KHỞI ĐỘNG ---
    print(f"=== DNS Server (port {PORT}) + forward {UPSTREAM[0]} ===")

    zone = load_zone()
    for n, i in zone.items():
        print(f"   {n:<30} -> {i}")             # In căn lề trái 30 ký tự

    print("Đang chờ truy vấn...\n")

    # --- VÒNG LẶP CHÍNH ---
    try:
        while True:
            # Chờ 1 gói tin UDP (tối đa 512 byte)
            # Trả về (nội_dung, (IP_client, port_client))
            data, addr = sock.recvfrom(512)

            # Reload zone mỗi query -> sửa file là có hiệu lực ngay
            zone = load_zone()

            # Tạo thread riêng để xử lý query này
            # -> server không bị block, phục vụ nhiều client cùng lúc
            threading.Thread(
                target=handle,
                args=(data, addr, sock, zone),
                daemon=True                     # Thread tự chết khi main thoát
            ).start()

    except KeyboardInterrupt:
        # Bắt Ctrl+C
        print("\nDừng server.")

    finally:
        # Luôn đóng socket khi thoát
        sock.close()


# ============================================================================
# 7. ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Chỉ chạy main() khi file được gọi trực tiếp:
    #   python3 server.py
    # KHÔNG chạy khi file được import: import server
    main()