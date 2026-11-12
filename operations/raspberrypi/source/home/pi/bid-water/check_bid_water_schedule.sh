#!/usr/bin/env bash
set -Eeuo pipefail

echo "[1] systemd calendar 해석 결과"
if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze calendar 'Mon..Sat *-*-* 08,10,12,14,16,18:28:00'
else
  echo "systemd-analyze 명령을 찾지 못했습니다."
fi

echo
echo "[2] 등록된 bid-water 타이머"
systemctl list-timers --all 'bid-water.timer' || true

echo
echo "[3] 최근 서비스 로그"
journalctl -u bid-water.service -n 80 --no-pager || true
