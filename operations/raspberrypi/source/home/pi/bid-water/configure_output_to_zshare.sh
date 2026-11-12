#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$HOME/bid-water}"
TARGET_BASE="${1:-${BID_WATER_BASE:-REDACTED_PRIVATE_VALUE}}"
ENV_FILE="$APP_DIR/.env"
RUN_USER="REDACTED_PRIVATE_VALUE"
RUN_GROUP="$(id -gn "$RUN_USER" 2>/dev/null || id -gn)"

if [ ! -d "$APP_DIR" ]; then
  echo "[FATAL] APP_DIR가 없습니다: $APP_DIR" >&2
  exit 2
fi
if [ ! -f "$APP_DIR/run_bid_water.sh" ]; then
  echo "[FATAL] run_bid_water.sh가 없습니다: $APP_DIR/run_bid_water.sh" >&2
  exit 3
fi

mkdir -p "$TARGET_BASE/raw" "$TARGET_BASE/split" "$TARGET_BASE/report" "$TARGET_BASE/logs" "$TARGET_BASE/state" "$TARGET_BASE/debug"
chmod 775 "$TARGET_BASE" "$TARGET_BASE/raw" "$TARGET_BASE/split" "$TARGET_BASE/report" "$TARGET_BASE/logs" "$TARGET_BASE/state" "$TARGET_BASE/debug" 2>/dev/null || true
chown -R "$RUN_USER:$RUN_GROUP" "$TARGET_BASE" 2>/dev/null || true

touch "$ENV_FILE"
TMP_FILE="$(mktemp)"
# Keep unrelated environment settings and replace only output-related values.
grep -vE '^(BID_WATER_BASE|BID_WATER_LOG_FILE|BID_WATER_LOCK_FILE)=' "$ENV_FILE" > "$TMP_FILE" || true
cat >> "$TMP_FILE" <<EOT
BID_WATER_BASE=$TARGET_BASE
BID_WATER_LOG_FILE=$TARGET_BASE/logs/run_bid_water.log
BID_WATER_LOCK_FILE=$TARGET_BASE/state/main_water.lock
EOT
mv "$TMP_FILE" "$ENV_FILE"
chown "$RUN_USER:$RUN_GROUP" "$ENV_FILE" 2>/dev/null || true
chmod 664 "$ENV_FILE" 2>/dev/null || true

# Optional systemd drop-in: keep the target path visible in systemctl cat output.
if command -v systemctl >/dev/null 2>&1; then
  sudo mkdir -p /etc/systemd/system/bid-water.service.d
  sudo tee /etc/systemd/system/bid-water.service.d/10-output-base.conf >/dev/null <<EOT
# Managed by configure_output_to_zshare.sh
# Output path corresponding to Windows Z: drive / NAS mount.
[Service]
Environment=BID_WATER_BASE=$TARGET_BASE
Environment=BID_WATER_LOG_FILE=$TARGET_BASE/logs/run_bid_water.log
Environment=BID_WATER_LOCK_FILE=$TARGET_BASE/state/main_water.lock
EOT
  sudo systemctl daemon-reload
  sudo systemctl restart bid-water.timer 2>/dev/null || true
fi

echo "[OK] bid-water 생성파일 저장 위치를 변경했습니다."
echo "     APP_DIR     : $APP_DIR"
echo "     TARGET_BASE : $TARGET_BASE"
echo "     ENV_FILE    : $ENV_FILE"
echo
if command -v findmnt >/dev/null 2>&1; then
  echo "[INFO] TARGET_BASE 기준 mount 정보"
  findmnt -T "$TARGET_BASE" || true
  echo
fi

echo "[INFO] .env 출력 관련 설정"
grep -E '^(BID_WATER_BASE|BID_WATER_LOG_FILE|BID_WATER_LOCK_FILE)=' "$ENV_FILE" || true
