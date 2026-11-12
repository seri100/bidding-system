#!/bin/bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "sudo ./install.sh 로 실행하세요."
  exit 1
fi

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="/home/pi/khnp_auto"

install -d -o pi -g pi "$DEST_DIR"
if [[ "$SRC_DIR" != "$DEST_DIR" ]]; then
  cp -a "$SRC_DIR"/. "$DEST_DIR"/
fi
rm -rf "$DEST_DIR/venv"
sudo -u pi python3 -m venv "$DEST_DIR/venv"
sudo -u pi "$DEST_DIR/venv/bin/pip" install -r "$DEST_DIR/requirements.txt"
install -m 0644 "$DEST_DIR/khnp-auto.service" /etc/systemd/system/khnp-auto.service
install -m 0644 "$DEST_DIR/khnp-auto.timer" /etc/systemd/system/khnp-auto.timer
systemctl daemon-reload
# 검증 후 수동 활성화
echo "설치 완료. /home/pi/khnp_auto/.env 설정 후 --dry-run으로 확인하세요."
