#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zone_manager.py - Quản lý zone.txt: thêm, xóa, sửa, đọc.

Dùng như module:
    from zone_manager import ZoneManager
    zm = ZoneManager("zone.txt")
    zm.add("abc.dns.vku", "10.0.0.1")
    zm.update("abc.dns.vku", "10.0.0.2")
    zm.delete("abc.dns.vku")
    print(zm.list_all())
"""

import os
import threading

class ZoneManager:
    def __init__(self, path="zone.sh"):
        self.path = path
        self.lock = threading.Lock()

    # -------- ĐỌC --------
    def load(self):
        """Đọc toàn bộ zone -> dict { name: ip }"""
        zone = {}
        if not os.path.exists(self.path):
            return zone
        with open(self.path, encoding="utf-8") as f:
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

    def get(self, name):
        """Lấy IP của 1 tên."""
        if not name.endswith("."):
            name += "."
        return self.load().get(name)

    def list_all(self):
        """Trả về list các (name, ip)."""
        return list(self.load().items())

    # -------- THÊM --------
    def add(self, name, ip):
        """Thêm bản ghi mới. Trả về True/False."""
        if not name.endswith("."):
            name += "."
        with self.lock:
            zone = self.load()
            if name in zone:
                return False            # đã tồn tại
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(f"{name:<30} {ip}\n")
                return True
            except Exception as e:
                print(f"[ZoneManager] Lỗi add: {e}")
                return False

    # -------- SỬA --------
    def update(self, name, ip):
        """Cập nhật IP cho tên. Nếu chưa có -> thêm mới."""
        if not name.endswith("."):
            name += "."
        with self.lock:
            zone = self.load()
            zone[name] = ip
            return self._write_all(zone)

    # -------- XÓA --------
    def delete(self, name):
        """Xóa bản ghi. Trả về True/False."""
        if not name.endswith("."):
            name += "."
        with self.lock:
            zone = self.load()
            if name not in zone:
                return False
            del zone[name]
            return self._write_all(zone)

    # -------- GHI LẠI TOÀN BỘ --------
    def _write_all(self, zone):
        """Ghi lại toàn bộ zone ra file (dùng cho update/delete)."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("# Zone file - quan ly boi zone_manager.py\n")
                for name, ip in zone.items():
                    f.write(f"{name:<30} {ip}\n")
            return True
        except Exception as e:
            print(f"[ZoneManager] Lỗi ghi: {e}")
            return False

if __name__ == "__main__":
    import sys
    zm = ZoneManager("zone.txt")

    if len(sys.argv) < 2:
        print("Dùng:")
        print("  python3 zone_manager.py list")
        print("  python3 zone_manager.py get <tên>")
        print("  python3 zone_manager.py add <tên> <ip>")
        print("  python3 zone_manager.py update <tên> <ip>")
        print("  python3 zone_manager.py delete <tên>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        for name, ip in zm.list_all():
            print(f"{name:<30} {ip}")

    elif cmd == "get" and len(sys.argv) >= 3:
        ip = zm.get(sys.argv[2])
        print(ip if ip else "Không tìm thấy")

    elif cmd == "add" and len(sys.argv) >= 4:
        ok = zm.add(sys.argv[2], sys.argv[3])
        print("Đã thêm" if ok else "Đã tồn tại")

    elif cmd == "update" and len(sys.argv) >= 4:
        ok = zm.update(sys.argv[2], sys.argv[3])
        print("Đã cập nhật" if ok else "Lỗi")

    elif cmd == "delete" and len(sys.argv) >= 3:
        ok = zm.delete(sys.argv[2])
        print("Đã xóa" if ok else "Không tìm thấy")

    else:
        print("Lệnh không hợp lệ")