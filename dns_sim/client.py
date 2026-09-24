import asyncio

HOST = "127.0.0.1"
PORT = 5353


def show_menu():
    print("\n===== DNS-SIM CLIENT =====")
    print("1. Truy vấn tên miền theo IP (QUERY)")
    print("2. Thêm / cập nhật bản ghi (ADD)")
    print("3. Xóa bản ghi (DEL)")
    print("4. Liệt kê tất cả bản ghi (LIST)")
    print("5. Thoát (QUIT)")
    print("===========================")


async def main():
    reader, writer = await asyncio.open_connection(HOST, PORT)

    banner = await reader.readline()
    print(banner.decode(errors="replace").strip())

    while True:
        show_menu()
        choice = (await asyncio.to_thread(input, "Chọn: ")).strip()

        if choice == "1":
            ip = (await asyncio.to_thread(input, "Nhập IP: ")).strip()
            cmd = f"QUERY {ip}"
        elif choice == "2":
            ip = (await asyncio.to_thread(input, "Nhập IP: ")).strip()
            domain = (await asyncio.to_thread(input, "Nhập tên miền: ")).strip()
            cmd = f"ADD {ip} {domain}"
        elif choice == "3":
            ip = (await asyncio.to_thread(input, "Nhập IP: ")).strip()
            cmd = f"DEL {ip}"
        elif choice == "4":
            cmd = "LIST"
        elif choice == "5":
            cmd = "QUIT"
        else:
            print("Lựa chọn không hợp lệ!")
            continue

        writer.write((cmd + "\n").encode())
        await writer.drain()

        resp = await reader.readline()
        if resp:
            print("[Server] " + resp.decode(errors="replace").strip())

        if cmd == "QUIT":
            break

    writer.close()
    await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
