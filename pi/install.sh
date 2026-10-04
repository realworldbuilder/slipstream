#!/usr/bin/env bash
# Run on the Pi from ~/slipstream: installs ffmpeg and MediaMTX, then enables the services.
set -euo pipefail
cd "$(dirname "$0")"

sudo apt-get update -q
sudo apt-get install -y -q ffmpeg

if ! command -v mediamtx >/dev/null; then
  url=$(curl -fsSL https://api.github.com/repos/bluenviron/mediamtx/releases/latest \
    | grep -o 'https://[^"]*linux_arm64\.tar\.gz' | head -1)
  tmp=$(mktemp -d)
  curl -fsSL "$url" | tar -xz -C "$tmp" mediamtx
  sudo install -m 755 "$tmp/mediamtx" /usr/local/bin/mediamtx
  rm -rf "$tmp"
fi

sudo install -m 644 systemd/slipstream-mediamtx.service systemd/slipstream-health.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slipstream-mediamtx.service slipstream-health.service
sudo systemctl restart slipstream-mediamtx.service slipstream-health.service
