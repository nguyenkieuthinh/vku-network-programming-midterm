╔══════════════════════════════════════════════════════════════════════════╗
║                      DnsServerEngine (LOGIC DNS)                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║  load_zone()          ← Nhiệm vụ 3: Đọc file zone → dict {tên: IP}       ║
║  add_record()         ← Quản lý zone: Thêm bản ghi thủ công              ║
║  delete_record()      ← Quản lý zone: Xóa bản ghi thủ công               ║
║  auto_register()      ← Nhiệm vụ 4: Tự động thêm tên mới *.dns.vku.      ║
║  decode_name()        ← Nhiệm vụ 2: Dịch tên miền từ gói DNS             ║
║  build_answer()       ← Nhiệm vụ 5: Đóng gói response DNS                ║
║  handle()             ← Điều phối nhiệm vụ 3, 4, 5, 6                    ║
║  start()              ← Nhiệm vụ 1: Khởi động socket UDP                 ║
║  _loop()              ← Nhiệm vụ 1: Vòng lặp nhận query                  ║
║  stop()               ← Tắt server                                       ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║                       DnsServerGUI (GIAO DIỆN)                           ║
╠══════════════════════════════════════════════════════════════════════════╣
║  __init__()           ← Tạo widget, bố cục cửa sổ                        ║
║  log_from_thread()    ← Nhận log từ engine (thread-safe qua queue)       ║
║  _drain_log_queue()   ← Hiện log lên GUI mỗi 400ms                       ║
║  refresh_zone_table() ← Hiện zone lên bảng Treeview                      ║
║  on_start()           ← Nút BẬT server                                   ║
║  on_stop()            ← Nút TẮT server                                   ║
║  on_add()             ← Nút Thêm bản ghi                                 ║
║  on_delete()          ← Nút Xóa bản ghi                                  ║
║  on_close()           ← Đóng cửa sổ                                      ║
╚══════════════════════════════════════════════════════════════════════════╝