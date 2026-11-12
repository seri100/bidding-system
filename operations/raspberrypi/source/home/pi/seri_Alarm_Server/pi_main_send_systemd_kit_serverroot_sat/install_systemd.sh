#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "[+] Installing run script to /home/pi/seri_Alarm_Server/run_main_send.sh"
install -m 0755 "$KIT_DIR/run_main_send.sh" /home/pi/seri_Alarm_Server/run_main_send.sh

echo "[+] Installing systemd units"
sudo install -m 0644 "$KIT_DIR/systemd/seri-main-send.service" "$SYSTEMD_DIR/seri-main-send.service"
sudo install -m 0644 "$KIT_DIR/systemd/seri-main-send.timer"   "$SYSTEMD_DIR/seri-main-send.timer"

echo "[+] daemon-reload && enable --now timer"
sudo systemctl daemon-reload
sudo systemctl enable --now seri-main-send.timer

echo "[+] Status:"
systemctl status --no-pager seri-main-send.timer || true
