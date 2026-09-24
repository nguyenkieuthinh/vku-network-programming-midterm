#!/usr/bin/env python3
"""
Mo phong dich vu DNS Server (May A) bang Python thuan (khong can thu vien ngoai).
Ho tro truy van loai A (IPv4) qua UDP, dinh dang goi tin DNS chuan (RFC 1035 rut gon).
"""

import socket
import struct

# ---- "Zone data" - co so du lieu DNS gia lap cua May A ----
DNS_ZONE = {
    "www.lab.demo.vir": "192.168.100.10",
    "mail.lab.com.": "192.168.100.15",
    "ftp.lab.com.": "192.168.100.20",
}

HOST = "0.0.0.0"
PORT = 9898          # Dung port 5353 de khong can quyen root (port 53 mac dinh can sudo/admin)
TTL = 300             # Time To Live (giay)


def decode_dns_name(data: bytes, offset: int):
    """Giai ma ten mien tu goi tin DNS (dang labels), tra ve (ten, offset moi)."""
    labels = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        offset += 1
        labels.append(data[offset:offset + length].decode())
        offset += length
    return ".".join(labels) + "", offset


def build_response(query: bytes) -> bytes:
    # ---- Header ----
    transaction_id = query[:2]
    qdcount = struct.unpack("!H", query[4:6])[0]

    # ---- Question section ----
    qname, offset = decode_dns_name(query, 12)
    qtype, qclass = struct.unpack("!HH", query[offset:offset + 4])
    offset += 4

    print(f"[Query] Client hoi ten mien: {qname} (type={qtype})")

    ip = DNS_ZONE.get(qname)

    # ---- Response Header ----
    flags_response = 0x8180 if ip else 0x8183  # 8180 = No error, 8183 = NXDOMAIN
    ancount = 1 if ip else 0

    header = transaction_id
    header += struct.pack("!H", flags_response)
    header += struct.pack("!H", qdcount)
    header += struct.pack("!H", ancount)
    header += struct.pack("!H", 0)  # NSCOUNT
    header += struct.pack("!H", 0)  # ARCOUNT

    # ---- Question section (echo lai nguyen ven) ----
    question = query[12:offset]

    # ---- Answer section (neu tim thay trong zone) ----
    answer = b""
    if ip:
        answer += b"\xc0\x0c"            # con tro tro ve ten mien trong Question (offset 12)
        answer += struct.pack("!H", 1)   # TYPE = A
        answer += struct.pack("!H", 1)   # CLASS = IN
        answer += struct.pack("!I", TTL)  # TTL
        answer += struct.pack("!H", 4)    # RDLENGTH = 4 bytes (IPv4)
        answer += socket.inet_aton(ip)     # RDATA = dia chi IP

    return header + question + answer


def start_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"=== May A: DNS Server dang chay tren {HOST}:{PORT} ===")
    print("Zone du lieu hien co:")
    for name, ip in DNS_ZONE.items():
        print(f"   {name:<20} -> {ip}")
    print("Dang cho truy van tu client (Ctrl+C de dung)...\n")

    try:
        while True:
            data, client_addr = sock.recvfrom(512)
            response = build_response(data)
            sock.sendto(response, client_addr)
            print(f"[Response] Da tra loi cho {client_addr}\n")
    except KeyboardInterrupt:
        print("\nDung DNS Server.")
    finally:
        sock.close()


if __name__ == "__main__":
    start_server()