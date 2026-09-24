#!/usr/bin/env python3
"""
Mo phong May C - Client gui truy van DNS toi May A (DNS Server).
Dung socket UDP thuan, tu dong dong goi/giai goi tin DNS (khong can thu vien ngoai).
"""

import socket
import struct
import random
import sys


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


def query_dns(domain: str, dns_server_ip: str, dns_server_port: int = 5353):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)

    query = build_query(domain)
    print(f"[May C] Gui truy van '{domain}' den DNS Server {dns_server_ip}:{dns_server_port} ...")

    try:
        sock.sendto(query, (dns_server_ip, dns_server_port))
        data, _ = sock.recvfrom(512)
        ip = parse_response(data)

        if ip:
            print(f"[May C] Ket qua: {domain} -> {ip}")
        else:
            print(f"[May C] Khong tim thay ban ghi cho '{domain}' (NXDOMAIN)")
    except socket.timeout:
        print("[May C] Loi: Khong nhan duoc phan hoi tu DNS server (timeout).")
    finally:
        sock.close()


if __name__ == "__main__":
    # Cach dung: python3 dns_client.py <ten_mien> <ip_may_A> [port]
    if len(sys.argv) < 3:
        print("Cach dung: python3 dns_client.py <ten_mien> <ip_may_A> [port]")
        print("Vi du:    python3 dns_client.py www.lab.com. 192.168.100.10 5353")
        sys.exit(1)

    domain = sys.argv[1]
    server_ip = sys.argv[2]
    server_port = int(sys.argv[3]) if len(sys.argv) > 3 else 9898

    query_dns(domain, server_ip, server_port)