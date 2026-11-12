#!/usr/bin/env bash
set -Eeuo pipefail

# Raspberry Pi용 bid-water 설치/등록 스크립트
# 기본 설치 폴더: /home/<사용자>/bid-water
# 기본 저장 폴더: /home/<사용자>/bid-water
# 예: BID_WATER_BASE=REDACTED_PRIVATE_VALUE ./setup_raspberrypi.sh

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="REDACTED_PRIVATE_VALUE"
RUN_GROUP="$(id -gn "$RUN_USER")"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
APP_DIR="${APP_DIR:-$RUN_HOME/bid-water}"
BASE_DIR="${BID_WATER_BASE:-$APP_DIR}"
INSTALL_APT_DEPS="${INSTALL_APT_DEPS:-1}"
INSTALL_PLAYWRIGHT_BROWSER="${INSTALL_PLAYWRIGHT_BROWSER:-1}"

render_template() {
  local src="$1"
  sed \
    -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__APP_USER__|$RUN_USER|g" \
    -e "s|__APP_GROUP__|$RUN_GROUP|g" \
    "$src"
}

echo "[INFO] RUN_USER=$RUN_USER"
echo "[INFO] APP_DIR=$APP_DIR"
echo "[INFO] BASE_DIR=$BASE_DIR"

mkdir -p "$APP_DIR"
if [ "$(realpath "$SRC_DIR")" != "$(realpath "$APP_DIR")" ]; then
  echo "[INFO] 패키지 파일을 $APP_DIR 로 복사합니다."
  (
    cd "$SRC_DIR"
    tar \
      --exclude='./.venv' \
      --exclude='./raw' \
      --exclude='./split' \
      --exclude='./report' \
      --exclude='./logs' \
      --exclude='./state' \
      --exclude='./debug' \
      -cf - .
  ) | (
    cd "$APP_DIR"
    tar -xf -
  )
fi

mkdir -p "$BASE_DIR/raw" "$BASE_DIR/split" "$BASE_DIR/report" "$BASE_DIR/logs" "$BASE_DIR/state" "$BASE_DIR/debug"
sudo chown -R "$RUN_USER:$RUN_GROUP" "$APP_DIR" 2>/dev/null || true
sudo chown -R "$RUN_USER:$RUN_GROUP" "$BASE_DIR" 2>/dev/null || true
chmod +x "$APP_DIR/run_bid_water.sh" "$APP_DIR/check_bid_water_schedule.sh" "$APP_DIR/uninstall_bid_water_timer.sh" 2>/dev/null || true

if [ "$INSTALL_APT_DEPS" = "1" ]; then
  echo "[INFO] Raspberry Pi OS 기본 패키지를 확인/설치합니다."
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip ca-certificates curl fonts-noto-cjk
  sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium || true
  sudo apt-get install -y chromium-chromedriver || sudo apt-get install -y chromium-driver || true
fi

if [ ! -d "$APP_DIR/.venv" ]; then
  echo "[INFO] Python 가상환경을 생성합니다."
  sudo -u "$RUN_USER" python3 -m venv "$APP_DIR/.venv"
fi

sudo -u "$RUN_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$RUN_USER" "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

CHROMIUM_PATH="$(command -v chromium || command -v chromium-browser || true)"
if [ "$INSTALL_PLAYWRIGHT_BROWSER" = "1" ]; then
  if sudo -u "$RUN_USER" "$APP_DIR/.venv/bin/python" -c "import playwright" >/dev/null 2>&1; then
    echo "[INFO] Playwright Chromium 설치를 시도합니다. Raspberry Pi ARM 환경에서는 실패할 수 있으며, 실패 시 시스템 Chromium을 사용합니다."
    set +e
    sudo -u "$RUN_USER" "$APP_DIR/.venv/bin/python" -m playwright install chromium
    PW_RC=$?
    set -e
    if [ "$PW_RC" -ne 0 ]; then
      echo "[WARN] Playwright Chromium 설치가 실패했습니다. 시스템 Chromium 경로를 사용합니다: ${CHROMIUM_PATH:-없음}"
    fi
  else
    echo "[INFO] Playwright가 설치되지 않은 환경입니다. Selenium + 시스템 Chromium으로 실행합니다."
  fi
fi

if [ ! -f "$APP_DIR/.env" ]; then
  echo "[INFO] $APP_DIR/.env 생성"
  {
    echo "APP_DIR=$APP_DIR"
    echo "BID_WATER_BASE=$BASE_DIR"
    echo "PYTHON_BIN=$APP_DIR/.venv/bin/python"
    echo "BID_WATER_MAX_DETAILS=80"
    echo "BID_WATER_LOCK_FILE=REDACTED_PRIVATE_VALUE"
    echo "BID_WATER_LOG_FILE=$BASE_DIR/logs/run_bid_water.log"
    echo "BROWSER_ENGINE=auto"
    CHROMEDRIVER_PATH="$(command -v chromedriver || true)"
    if [ -n "$CHROMEDRIVER_PATH" ]; then
      echo "CHROMEDRIVER_PATH=$CHROMEDRIVER_PATH"
    fi
    if [ -n "$CHROMIUM_PATH" ]; then
      echo "CHROMIUM_EXECUTABLE_PATH=$CHROMIUM_PATH"
    else
      echo "# CHROMIUM_EXECUTABLE_PATH=REDACTED_PRIVATE_VALUE"
    fi
    echo "CHROMIUM_ARGS=REDACTED_PRIVATE_VALUE"
  } > "$APP_DIR/.env"
  sudo chown "$RUN_USER:$RUN_GROUP" "$APP_DIR/.env" 2>/dev/null || true
else
  echo "[INFO] 기존 .env를 유지합니다: $APP_DIR/.env"
fi

SERVICE_TEMPLATE="$APP_DIR/templates/raspberrypi/systemd/bid-water.service.template"
TIMER_TEMPLATE="$APP_DIR/templates/raspberrypi/systemd/bid-water.timer.template"
if [ ! -f "$SERVICE_TEMPLATE" ] || [ ! -f "$TIMER_TEMPLATE" ]; then
  echo "[FATAL] systemd 템플릿을 찾지 못했습니다. $APP_DIR/templates/raspberrypi/systemd 확인 필요"
  exit 10
fi

echo "[INFO] systemd 서비스/타이머 등록"
render_template "$SERVICE_TEMPLATE" | sudo tee /etc/systemd/system/bid-water.service >/dev/null
render_template "$TIMER_TEMPLATE" | sudo tee /etc/systemd/system/bid-water.timer >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now bid-water.timer

echo
echo "[DONE] bid-water 자동 실행 등록 완료"
echo "       폴더: $APP_DIR"
echo "       저장: $BASE_DIR"
echo "       일정: 월~토 08:28, 10:28, 12:28, 14:28, 16:28, 18:28"
echo
echo "[확인 명령]"
echo "  systemctl list-timers --all 'bid-water.timer'"
echo "  $APP_DIR/check_bid_water_schedule.sh"
echo "  sudo systemctl start bid-water.service   # 즉시 1회 실행"
echo "  tail -f $BASE_DIR/logs/run_bid_water.log"
