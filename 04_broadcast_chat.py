import asyncio
import socket


class Broadcast:
    def __init__(self, capacity=10):
        self._capacity = capacity
        self._subscribers = set()

    def subscribe(self):
        q = asyncio.Queue(maxsize=self._capacity)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        self._subscribers.discard(q)

    def publish(self, msg):
        for q in list(self._subscribers):
            # Drop oldest message if the subscriber is lagging (mirrors tokio broadcast Lagged)
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass


async def handle_client(reader, writer, addr, bus):
    q = bus.subscribe()

    # Announce new client arrival to all existing users
    bus.publish((f"*** Client [{addr}] joined the chat ***\n", addr))

    # Branch 1: read input lines from the client's TCP socket
    async def read_from_socket():
        while True:
            line = await reader.readline()
            if not line:
                print(f"[-] Client disconnected: {addr}")
                bus.publish((f"*** Client [{addr}] left the chat ***\n", addr))
                return
            formatted_msg = f"[{addr}]: {line.decode(errors='replace')}"
            bus.publish((formatted_msg, addr))

    # Branch 2: receive broadcast messages from other clients
    async def write_to_socket():
        while True:
            msg, sender_addr = await q.get()
            if sender_addr != addr:
                writer.write(msg.encode())
                await writer.drain()

    read_task = asyncio.create_task(read_from_socket())
    write_task = asyncio.create_task(write_to_socket())

    await read_task
    write_task.cancel()
    try:
        await write_task
    except asyncio.CancelledError:
        pass

    bus.unsubscribe(q)
    writer.close()
    await writer.wait_closed()


async def main():
    bus = Broadcast(capacity=10)

    async def on_client(reader, writer):
        await handle_client(reader, writer, writer.get_extra_info("peername"), bus)

    server = await asyncio.start_server(on_client, "127.0.0.1", 8080)

    print("====================================================")
    print(" TCP Broadcast Chat Server (asyncio + Broadcast Queue)")
    print(" Listening on 127.0.0.1:8080")
    print(" Connect with: nc 127.0.0.1 8080  or  telnet 127.0.0.1 8080")
    print("====================================================\n")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
