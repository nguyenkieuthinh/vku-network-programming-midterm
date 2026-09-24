import asyncio
import socket


async def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 8080))
    sock.listen()
    sock.setblocking(False)

    print("[Single-Client Echo Server] Listening on 127.0.0.1:8080...")
    print("NOTE: This server handles connections sequentially!")
    print("Try connecting Client 1, then Client 2. Client 2 will hang until Client 1 disconnects.\n")

    loop = asyncio.get_running_loop()

    while True:
        # Blocks the accept loop until a client connects
        conn, addr = await loop.sock_accept(sock)
        print(f"[+] Client connected: {addr}")

        reader, writer = await asyncio.open_connection(sock=conn)

        # Sequential read-write loop for the active socket.
        # Because we do not create a task, sock_accept() won't be called again until this loop ends!
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


if __name__ == "__main__":
    asyncio.run(main())
