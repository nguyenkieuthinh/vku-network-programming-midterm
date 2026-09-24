import asyncio
import json
import os

HOST = "127.0.0.1"
PORT = 5353
RECORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records.json")


def load_records():
    if os.path.exists(RECORDS_FILE):
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_records(records):
    with open(RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


records = load_records()


def handle_command(line):
    parts = line.strip().split(maxsplit=2)
    if not parts:
        return "400 Empty command"

    cmd = parts[0].upper()

    if cmd == "QUERY":
        if len(parts) < 2:
            return "400 Usage: QUERY <ip>"
        ip = parts[1]
        domain = records.get(ip)
        if domain:
            return f"200 {domain}"
        return f"404 No domain for {ip}"

    if cmd == "ADD":
        if len(parts) < 3:
            return "400 Usage: ADD <ip> <domain>"
        ip, domain = parts[1], parts[2]
        records[ip] = domain
        save_records(records)
        return f"200 Updated {ip} -> {domain}"

    if cmd == "DEL":
        if len(parts) < 2:
            return "400 Usage: DEL <ip>"
        ip = parts[1]
        if ip in records:
            del records[ip]
            save_records(records)
            return f"200 Deleted {ip}"
        return f"404 No record for {ip}"

    if cmd == "LIST":
        if not records:
            return "200 0 records"
        entries = "; ".join(f"{ip} -> {domain}" for ip, domain in records.items())
        return f"200 {len(records)} records: {entries}"

    if cmd == "QUIT":
        return "200 Bye"

    return "400 Unknown command"


async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    print(f"[+] Client connected: {addr}")

    banner = "Welcome to DNS-Sim server. Commands: QUERY <ip>, ADD <ip> <domain>, DEL <ip>, LIST, QUIT"
    writer.write((banner + "\n").encode())
    await writer.drain()

    while True:
        data = await reader.readline()
        if not data:
            break

        line = data.decode(errors="replace").strip()
        if not line:
            continue

        print(f"[{addr}] {line}")
        resp = handle_command(line)
        writer.write((resp + "\n").encode())
        await writer.drain()

        if line.upper().startswith("QUIT"):
            break

    print(f"[-] Client disconnected: {addr}")
    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"[DNS-Sim Server] Listening on {HOST}:{PORT}")
    print(f"[DNS-Sim Server] Records loaded: {len(records)} entries")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
