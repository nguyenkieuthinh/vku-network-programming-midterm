#!/usr/bin/env python3
import http.server
import socketserver

HOST = "0.0.0.0"
PORT = 4343
FILE = "web.html"

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            with open(FILE, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, "web.html not found")

with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
    print(f"=== Web server chạy tại http://{HOST}:{PORT} (phục vụ {FILE}) ===")
    httpd.serve_forever()