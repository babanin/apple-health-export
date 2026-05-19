#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

GATEWAY_PORT="${GRPC_PORT:-50051}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"

primary_ip() {
  local iface

  if command -v route >/dev/null 2>&1; then
    iface="$(route get default 2>/dev/null | awk '/interface:/{print $2; exit}')"
    if [ -n "${iface:-}" ] && command -v ipconfig >/dev/null 2>&1; then
      ipconfig getifaddr "$iface" 2>/dev/null && return 0
    fi
  fi

  if command -v ipconfig >/dev/null 2>&1; then
    ipconfig getifaddr en0 2>/dev/null && return 0
    ipconfig getifaddr en1 2>/dev/null && return 0
  fi

  if command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | awk '{print $1; exit}' && return 0
  fi

  if command -v ifconfig >/dev/null 2>&1; then
    ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" && $2 !~ /^169\.254\./ {print $2; exit}' && return 0
  fi

  return 1
}

all_ips() {
  if command -v ifconfig >/dev/null 2>&1; then
    ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" && $2 !~ /^169\.254\./ {print $2}' | sort -u
  elif command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | tr ' ' '\n' | awk 'NF'
  fi
}

echo "Starting Apple Health Export stack..."
docker compose up -d --build "$@"

LAN_IP="$(primary_ip || true)"

echo ""
echo "Apple Health Export is running."
echo ""
echo "Grafana:"
echo "  URL:      http://localhost:${GRAFANA_PORT}"
echo "  Login:    admin / admin"
echo ""
echo "iPhone app Server settings:"
if [ -n "$LAN_IP" ]; then
  echo "  Host:     ${LAN_IP}"
  echo "  Port:     ${GATEWAY_PORT}"
  echo "  Address:  ${LAN_IP}:${GATEWAY_PORT}"
else
  echo "  Host:     <your Mac LAN IP>"
  echo "  Port:     ${GATEWAY_PORT}"
  echo "  Address:  <your Mac LAN IP>:${GATEWAY_PORT}"
fi
echo ""
echo "Next:"
echo "  1. Open the iPhone app."
echo "  2. Enter the Host and Port above."
echo "  3. Tap Ping, then Sync Now."

OTHER_IPS="$(all_ips | grep -v "^${LAN_IP:-}$" || true)"
if [ -n "$OTHER_IPS" ]; then
  echo ""
  echo "Other detected local IPs:"
  printf '  %s\n' $OTHER_IPS
fi
