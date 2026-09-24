import asyncio
import socket


async def handle_client(reader, writer, addr):
    while True:
        data = await reader.read(1024)
        if not data:
            print(f"[-] Client disconnected: {addr}")
            break
        print(f"[Echo to {addr}] {data.decode(errors='replace')}", end="")
        writer.write(data)
        await writer.drain()
    writer.close()
    await writer.wait_closed()


async def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 8080))
    sock.listen()
    sock.setblocking(False)

    print("[Multi-Client Concurrent Echo Server] Listening on 127.0.0.1:8080...")
    print("FIXED: Using asyncio.create_task to process each client in an independent task.\n")

    loop = asyncio.get_running_loop()

    while True:
        conn, addr = await loop.sock_accept(sock)
        print(f"[+] Client connected: {addr}")

        # asyncio.create_task schedules handle_client as an independent coroutine (task).
        # The main accept loop immediately continues to accept the next incoming connection!
        reader, writer = await asyncio.open_connection(sock=conn)
        asyncio.create_task(handle_client(reader, writer, addr))


if __name__ == "__main__":
    asyncio.run(main())
