
#!/bin/bash

set -euo pipefail



HOURS="${1:-72}"



# ✅ 테스트 결과는 무조건 여기로 분리 저장

export N_DATA_BASE="/mnt/vol1/bid/n_data_test"

export NAS_BASE="/mnt/vol1/bid/n_data_test"



# ✅ 테스트는 수신자 강제 (혹시라도 no-send 빠져도 안전장치)

export FORCE_RECV="REDACTED_PRIVATE_VALUE"

export ALLIGO_SENDER="REDACTED_PRIVATE_VALUE"

export RECV_DEBUG="1"



# ✅ 테스트는 "발송 0건" 보장

NO_SEND_ARGS="--no-send"



LOCK_DIR="/home/pi/n_data/.lock"

mkdir -p "$LOCK_DIR"

LOCK_FILE="${MAIN_SEND_LOCK_FILE:-/home/pi/n_data/.lock/main_send_test.lock}"



LOG_DIR="/mnt/vol1/bid/n_data_test/logs"

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/run_main_send_test.log"



NOW_START="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[$NOW_START] [TEST] start hours=$HOURS lock=$LOCK_FILE base=$N_DATA_BASE" >> "$LOG_FILE"



(

  flock -n 9 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TEST] lock busy -> skip ($LOCK_FILE)" >> "$LOG_FILE"; exit 0; }



  /usr/bin/python3 -u /home/pi/n_data/main_send.py --hours "$HOURS" $NO_SEND_ARGS >> "$LOG_FILE" 2>&1

  RC=$?



  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TEST] end (rc=$RC)" >> "$LOG_FILE"

  exit 0

) 9>>"$LOCK_FILE"

