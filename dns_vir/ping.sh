#!/bin/bash
# dns_ping.sh - "ping" bang truy van DNS lap lai, giong lenh ping icmp.
#
# Dung:
#   ./dns_ping.sh <ten_mien> <ip_server> [port=9898] [interval_giay=1]
#
# Vi du:
#   ./dns_ping.sh abc.dns.vku 10.147.18.200
#   ./dns_ping.sh abc.dns.vku 10.147.18.200 9898 0.5
#
# Dung Ctrl+C de dung.

DOMAIN="$1"
SERVER="$2"
PORT="${3:-9898}"
INTERVAL="${4:-1}"

if [ -z "$DOMAIN" ] || [ -z "$SERVER" ]; then
    echo "Dung: $0 <ten_mien> <ip_server> [port=9898] [interval_giay=1]"
    exit 1
fi

if ! command -v dig >/dev/null 2>&1; then
    echo "Loi: chua cai 'dig'. Cai bang: sudo apt install dnsutils"
    exit 1
fi

echo "DNS-PING toi $DOMAIN qua $SERVER:$PORT (moi ${INTERVAL}s, Ctrl+C de dung)"
echo

seq=0
ok=0
fail=0

trap 'echo; echo "--- thong ke ---"; echo "$seq goi da gui, $ok thanh cong, $fail that bai"; exit 0' INT

while true; do
    seq=$((seq + 1))
    t0=$(date +%s%N)
    result=$(dig +time=2 +tries=1 @"$SERVER" -p "$PORT" "$DOMAIN" +short 2>/dev/null)
    t1=$(date +%s%N)
    ms=$(((t1 - t0) / 1000000))

    if [ -n "$result" ]; then
        ok=$((ok + 1))
        echo "seq=$seq $DOMAIN -> $result   time=${ms}ms"
    else
        fail=$((fail + 1))
        echo "seq=$seq $DOMAIN -> khong nhan duoc phan hoi (timeout/refused)"
    fi

    sleep "$INTERVAL"
done