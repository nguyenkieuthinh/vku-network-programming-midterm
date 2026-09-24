# DNS-Sim — Giả lập dịch vụ DNS

**Đề tài:** Đề số 23 — Xây dựng chương trình giả lập dịch vụ DNS.

**Ngôn ngữ:** Python (asyncio + socket)

---

## 1. Đề bài & Yêu cầu

Xây dựng chương trình giả lập dịch vụ DNS theo mô hình Client/Server:

1. Tìm hiểu dịch vụ DNS và xây dựng chương trình tương tự.
2. **Client:** cho phép truy vấn tên miền của một địa chỉ IP (reverse lookup).
3. **Server:** cho phép **cập nhật** (thêm/sửa/xóa) và **trả lại tên miền** cho client.

---

## 2. Sơ đồ hoạt động

```
+------------+     QUERY <ip>       +------------+
|            | -------------------> |            |
|   Client   |     ADD/DEL/LIST     |   Server   |
|            | <------------------- |            |
+------------+     200/404 kết quả  +------------+
                                        |  đọc/ghi
                                        v
                                 records.json
                                 (IP -> tên miền)
```

---

## 3. Các chức năng

### Phía Server (`server.py`)
- Lắng nghe kết nối TCP tại `127.0.0.1:5353`.
- Xử lý đồng thời nhiều client (`asyncio`).
- Nạp/lưu bản ghi từ `records.json`.
- Các lệnh hỗ trợ:
  - `QUERY <ip>` — trả tên miền tương ứng.
  - `ADD <ip> <domain>` — thêm/cập nhật bản ghi.
  - `DEL <ip>` — xóa bản ghi.
  - `LIST` — liệt kê toàn bộ bản ghi.
  - `QUIT` — ngắt kết nối.

### Phía Client (`client.py`)
- Kết nối đến server, hiển thị menu tương tác.
- Truy vấn tên miền theo IP.
- Thêm/cập nhật, xóa, liệt kê bản ghi.

---

## 4. Cách tổ chức và quản lý dữ liệu

- Dữ liệu lưu dạng `dict` (IP → tên miền) trong bộ nhớ.
- Đồng bộ xuống file `records.json` sau mỗi thao tác thay đổi.
- Giao thức trao đổi: văn bản thuần, mỗi lệnh/kết quả trên một dòng.

---

## 5. Hướng dẫn chạy

```bash
# Terminal 1 — chạy server
python3 server.py

# Terminal 2 — chạy client
python3 client.py
```

Hoặc dùng lệnh thuần để test nhanh:
```bash
nc 127.0.0.1 5353
# QUERY 8.8.8.8
# ADD 10.0.0.1 mypc.local
# LIST
# QUIT
```

---

## 6. Nhật ký hoàn thành (Log)

- [x] Phân tích đề tài & yêu cầu
- [x] Xây dựng DNS Server (lắng nghe, xử lý đa client)
- [x] Xây dựng DNS Client (menu tương tác, truy vấn/cập nhật)
- [x] Quản lý dữ liệu bằng `records.json`
- [x] Kiểm thử cú pháp & smoke test (QUERY, ADD, DEL, LIST)

**Trạng thái:** Hoàn thành.
