# Building a TCP Chat Server in Python with asyncio

This project demonstrates the step-by-step evolution of a network server in async Python, starting from a naive single-client echo server to a high-concurrency TCP broadcast chat server using `asyncio`.

---

## Project Structure

- `01_single_client_echo.py`: **Single-Client Echo Server**
  Demonstrates how processing connections sequentially blocks the main accept loop, causing secondary clients to hang.
- `02_multiclient_spawn.py`: **Multi-Client Echo Server with `asyncio.create_task`**
  Offloads each connection onto an independent task, enabling concurrent TCP handling.
- `03_arc_mutex_pitfall.py`: **Case Study: The Shared-Lock (`Arc<Mutex<...>>`) Pitfall**
  Illustrates why shared state with a single lock is anti-pattern in async network streaming.
- `04_broadcast_chat.py`: **Multi-Client Broadcast Chat Server**
  Combines a broadcast queue and concurrent read/write tasks for an elegant, lock-free MPMC broadcast architecture.

---

## 1. Single-Client Echo Server (`01_single_client_echo.py`)

### Code Overview
```python
loop = asyncio.get_running_loop()
while True:
    conn, addr = await loop.sock_accept(sock)
    # Sequential read/write loop...
    while True:
        data = await reader.read(1024)
        writer.write(data)
        await writer.drain()
```

### Why It Breaks
In this initial version, `loop.sock_accept()` waits for Client 1. Once connected, execution enters the inner reading/writing loop. Because this loop runs on the main task, **`sock_accept()` is never called again** until Client 1 terminates their socket connection. Client 2's TCP handshake completes at the OS level (SYN/ACK in TCP backlog queue), but the application never accepts it. Client 2 hangs indefinitely.

---

## 2. Fixing Concurrency with `asyncio.create_task` (`02_multiclient_spawn.py`)

### Code Overview
```python
while True:
    conn, addr = await loop.sock_accept(sock)
    reader, writer = await asyncio.open_connection(sock=conn)
    asyncio.create_task(handle_client(reader, writer, addr))
```

### How It Works
`asyncio.create_task` schedules `handle_client` as an independent coroutine (task). The main loop immediately loops back to `sock_accept()`. Hundreds or thousands of clients can now echo concurrently without blocking one another.

---

## 3. The Shared-Lock Trap vs. Queues

When engineers try to convert an Echo server into a **Chat server** (where Client A's messages are broadcast to Client B, C, D), their initial instinct is often OOP/thread-style shared memory:

```python
# ❌ WRONG INSTINCT
clients = {}            # addr -> StreamWriter
lock = asyncio.Lock()   # single lock guarding the whole map
```

### Why a single shared lock fails in Async Python:
1. **Lock Contention across `await` points:** If a task holds the lock while awaiting network writes (`await writer.drain()`), **a single slow or unresponsive client blocks the entire chat server** for all other users.
2. **Deadlocks & Lifetime Leaks:** Cleanup on disconnect requires acquiring the lock again, creating race conditions and deadlock vectors.
3. **Blocking the Event Loop:** Serializing every broadcast under one lock effectively kills concurrency — the whole point of using `asyncio`.

---

## 4. The Broadcast Solution (`04_broadcast_chat.py`)

Rather than sharing socket handles via a lock, async idioms recommend: **"Do not communicate by sharing memory; share memory by communicating."**

```python
# MPMC Broadcast via per-subscriber queues
class Broadcast:
    def __init__(self, capacity=10): ...
```

### How concurrent read/write tasks multiplex I/O

Each client task owns its own socket reader and writer, and subscribes to the broadcast via `bus.subscribe()`. Two concurrent tasks are run for each client:

```python
read_task = asyncio.create_task(read_from_socket())   # Event 1: read lines from TCP socket
write_task = asyncio.create_task(write_to_socket())   # Event 2: receive broadcast from queue
```

- `read_from_socket` reads a line via `reader.readline()`, formats it as `[addr]: line`, and publishes it with `bus.publish(...)`.
- `write_to_socket` awaits `q.get()`, then writes the message out to the client socket (excluding echo to self).

---

## Running the Servers

### Run Step 1 (Single-Client Echo)
```bash
python3 01_single_client_echo.py
```
*Test in two terminals:* `nc 127.0.0.1 8080` (Client 1 works; Client 2 hangs).

### Run Step 2 (Multi-Client Spawn)
```bash
python3 02_multiclient_spawn.py
```
*Test in two terminals:* Both clients echo simultaneously!

### Run Step 3 (Shared-Lock Pitfall Case Study)
```bash
python3 03_arc_mutex_pitfall.py
```

### Run Step 4 (Broadcast Chat Server)
```bash
python3 04_broadcast_chat.py
```
*Test in multiple terminals:*
```bash
nc 127.0.0.1 8080
```
Messages typed in Terminal 1 instantly broadcast to Terminal 2, Terminal 3, etc.!
# vku-network-programming-midterm
