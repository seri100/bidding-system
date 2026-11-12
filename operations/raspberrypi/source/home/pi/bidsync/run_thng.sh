
#!/usr/bin/env bash

set -Eeuo pipefail



SCRIPT_DIR="/home/pi/bidsync"

PYTHON_BIN="/usr/bin/python3"

TARGET="${SCRIPT_DIR}/daily_sync_final_insert_thng.py"



LOG_DIR="${SCRIPT_DIR}/logs"

mkdir -p "${LOG_DIR}"



TODAY="$(date +%F)"

LOG_FILE="${LOG_DIR}/run_thng_${TODAY}.log"

LOCK_FILE="/tmp/bidsync_thng.lock"



exec 9>"${LOCK_FILE}"

if ! flock -n 9; then

  echo "$(date '+%F %T') [INFO] thng already running" | tee -a "${LOG_FILE}"

  exit 0

fi



MAX_ATTEMPTS=3

ATTEMPT=1

SLEEP_BASE=30



echo "$(date '+%F %T') [INFO] start run_thng.sh" | tee -a "${LOG_FILE}"



while (( ATTEMPT <= MAX_ATTEMPTS )); do

  echo "$(date '+%F %T') [INFO] attempt=${ATTEMPT}/${MAX_ATTEMPTS}" | tee -a "${LOG_FILE}"



  if "${PYTHON_BIN}" "${TARGET}" >> "${LOG_FILE}" 2>&1; then

    echo "$(date '+%F %T') [INFO] success" | tee -a "${LOG_FILE}"

    exit 0

  fi



  RC=$?

  echo "$(date '+%F %T') [WARN] failed rc=${RC}" | tee -a "${LOG_FILE}"



  if (( ATTEMPT == MAX_ATTEMPTS )); then

    echo "$(date '+%F %T') [ERROR] max attempts reached" | tee -a "${LOG_FILE}"

    exit "${RC}"

  fi



  SLEEP_SEC=$(( SLEEP_BASE * ATTEMPT ))

  echo "$(date '+%F %T') [INFO] sleep ${SLEEP_SEC}s before retry" | tee -a "${LOG_FILE}"

  sleep "${SLEEP_SEC}"



  ATTEMPT=$(( ATTEMPT + 1 ))

done

