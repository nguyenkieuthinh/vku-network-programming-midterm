#!/usr/bin/env python3
import socket, struct, os, threading

HOST = "0.0.0.0"
PORT = 9898
TTL  = 300
ZONE_FILE = "zone.sh"
UPSTREAM  = ("8.8.8.8", 53)   # DNS công cộng để forward

def load_zone():
    zone = {}
    if not os.path.exists(ZONE_FILE):
        return zone
    with open(ZONE_FILE) as f:
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

def decode_name(data, off):
    labels = []
    while True:
        ln = data[off]
        if ln == 0:
            off += 1
            break
        off += 1
        labels.append(data[off:off+ln].decode())
        off += ln
    return ".".join(labels) + ".", off

def build_answer(query, ip):
    tid = query[:2]
    qd  = struct.unpack("!H", query[4:6])[0]
    # tìm hết question section
    off = 12
    while query[off] != 0:
        off += query[off] + 1
    off += 1 + 4
    question = query[12:off]

    flags = 0x8180
    header = tid + struct.pack("!HHHHH", flags, qd, 1, 0, 0)
    answer  = b"\xc0\x0c"
    answer += struct.pack("!HH", 1, 1)
    answer += struct.pack("!I", TTL)
    answer += struct.pack("!H", 4)
    answer += socket.inet_aton(ip)
    return header + question + answer

def handle(data, addr, sock, zone):
    name, _ = decode_name(data, 12)
    ip = zone.get(name)
    if ip:
        print(f"[Local] {name} -> {ip}")
        sock.sendto(build_answer(data, ip), addr)
        return
    # Forward lên 8.8.8.8
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

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"=== DNS Server (port {PORT}) + forward {UPSTREAM[0]} ===")
    zone = load_zone()
    for n, i in zone.items():
        print(f"   {n:<30} -> {i}")
    print("Đang chờ truy vấn...\n")
    try:
        while True:
            data, addr = sock.recvfrom(512)
            zone = load_zone()
            threading.Thread(target=handle, args=(data, addr, sock, zone), daemon=True).start()
    except KeyboardInterrupt:
        print("\nDừng server.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()