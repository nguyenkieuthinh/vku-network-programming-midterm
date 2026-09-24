# Demonstration / Case Study: Why the shared-lock pattern (the async equivalent of
# Arc<Mutex<...>>) is problematic for async chat servers.
#
# When engineers transition from single echo to multi-client chat, the first instinct is often:
# clients = {}  # addr -> StreamWriter, guarded by a single asyncio.Lock
#
# Below is code illustrating why this pattern runs into severe issues in asyncio applications.

import asyncio
import socket

clients = {}
lock = asyncio.Lock()


async def handle_client(reader, writer, addr):
    # Insert client writer into shared dict
    async with lock:
        clients[addr] = writer

    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            msg = data.decode(errors="replace")

            # PITFALL 1: Lock contention during broadcast
            # PITFALL 2: A slow client network write inside this lock blocks ALL OTHER CLIENTS!
            # PITFALL 3: Potential deadlocks if client disconnects mid-broadcast.
            async with lock:
                disconnected = []
                for client_addr, client_writer in list(clients.items()):
                    formatted = f"[{addr}] {msg}"
                    # Awaiting write while holding the lock blocks all reads/writes across the server
                    try:
                        client_writer.write(formatted.encode())
                        await client_writer.drain()
                    except Exception as e:
                        print(f"Failed to write to {client_addr}: {e}")
                        disconnected.append(client_addr)

                # Cleanup disconnected sockets
                for dead in disconnected:
                    clients.pop(dead)
    finally:
        # Remove client on exit
        async with lock:
            clients.pop(addr, None)
        print(f"[-] Client disconnected and cleaned up: {addr}")
        writer.close()
        await writer.wait_closed()


async def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 8080))
    sock.listen()
    sock.setblocking(False)

    print("[Shared-Lock Pattern Demo] Listening on 127.0.0.1:8080...")

    loop = asyncio.get_running_loop()

    while True:
        conn, addr = await loop.sock_accept(sock)
        print(f"[+] Client connected: {addr}")
        reader, writer = await asyncio.open_connection(sock=conn)
        asyncio.create_task(handle_client(reader, writer, addr))


if __name__ == "__main__":
    asyncio.run(main())
