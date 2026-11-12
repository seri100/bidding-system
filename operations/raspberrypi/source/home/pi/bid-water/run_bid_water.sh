#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

BASE_DIR="${BID_WATER_BASE:-$APP_DIR}"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"
LOCK_FILE="${BID_WATER_LOCK_FILE:-REDACTED_PRIVATE_VALUE}"
LOG_FILE="${BID_WATER_LOG_FILE:-$BASE_DIR/logs/run_bid_water.log}"

mkdir -p "$BASE_DIR/raw" "$BASE_DIR/split" "$BASE_DIR/report" "$BASE_DIR/logs" "$BASE_DIR/state" "$BASE_DIR/debug"
mkdir -p "$(dirname "$LOCK_FILE")"

exec >> "$LOG_FILE" 2>&1

echo "REDACTED_LONG_LITERAL"
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] bid-water wrapper START"
echo "APP_DIR=$APP_DIR"
echo "BASE_DIR=$BASE_DIR"
echo "PYTHON_BIN=$PYTHON_BIN"
echo "ARGS=$*"

if [ ! -f "$APP_DIR/main_water.py" ]; then
  echo "[FATAL] $APP_DIR/main_water.py 파일이 없습니다."
  exit 2
fi

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [ -z "${PYTHON_BIN:-}" ]; then
  echo "[FATAL] python3를 찾지 못했습니다."
  exit 3
fi

cd "$APP_DIR"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] 이미 실행 중이므로 이번 회차는 건너뜁니다."
    exit 0
  fi
fi

"$PYTHON_BIN" -u "$APP_DIR/main_water.py" --base "$BASE_DIR" "$@"
RC=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] bid-water wrapper END rc=$RC"
exit "$RC"
