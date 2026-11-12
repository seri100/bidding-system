#!/usr/bin/env bash
set -Eeuo pipefail

sudo systemctl disable --now bid-water.timer 2>/dev/null || true
sudo rm -f /etc/systemd/system/bid-water.timer /etc/systemd/system/bid-water.service
sudo systemctl daemon-reload
sudo systemctl reset-failed bid-water.service bid-water.timer 2>/dev/null || true

echo "bid-water systemd 타이머/서비스를 제거했습니다. 데이터 폴더는 삭제하지 않았습니다."
