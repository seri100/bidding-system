#!/usr/bin/env bash

set -euo pipefail

# --- always restore even if test fails ---
cleanup(){
  sudo systemctl start outbox_sender.timer 2>/dev/null || true
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TESTMODE] AUTO-RESTORE" | sudo tee -a "${TEST_LOG}" >/dev/null || true
}
trap cleanup EXIT




# ====== TEST CONFIG ======

TEST_BASE="/mnt/vol1/bid/n_data_test"

LOCK_DIR="/home/pi/n_data/.lock"

LOCK_FILE="${LOCK_DIR}/main_send_test.lock"

TEST_LOG="${TEST_BASE}/logs/run_main_send_test.log"



# REDACTED_PRIVATE_VALUE에게만

FORCE_RECV="REDACTED_PRIVATE_VALUE"

ALLIGO_SENDER="REDACTED_PRIVATE_VALUE"



mkdir -p "${LOCK_DIR}"

sudo install -d -m 775 "${TEST_BASE}" "${TEST_BASE}/logs" "${TEST_BASE}/raw" "${TEST_BASE}/split" "${TEST_BASE}/report"



# API KEY(없으면 운영에서 복사) - 운영 파일은 건드리지 않음

if [ ! -f "${TEST_BASE}/bid_api_key.txt" ]; then

  sudo cp -a /mnt/vol1/bid/n_data/bid_api_key.txt "${TEST_BASE}/bid_api_key.txt"

  sudo chown root:pi "${TEST_BASE}/bid_api_key.txt"

  sudo chmod 640 "${TEST_BASE}/bid_api_key.txt"

fi



# outbox_sender 완전 차단(테스트 동안만)

sudo systemctl stop outbox_sender.timer outbox_sender.service 2>/dev/null || true



echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TESTMODE] ON base=${TEST_BASE}" | sudo tee -a "${TEST_LOG}" >/dev/null



# NAS_BASE를 TEST_BASE로 강제 + --no-send(dry-run) + 수신자 1명 고정

sudo -u pi env \

  NAS_BASE="${TEST_BASE}" \

  MAIN_SEND_LOCK_FILE="${LOCK_FILE}" \

  LOCK_FILE="${LOCK_FILE}" \

  FORCE_RECV="${FORCE_RECV}" \

  ALLIGO_SENDER="${ALLIGO_SENDER}" \

  RECV_DEBUG=1 \

  /bin/bash /home/pi/n_data/run_main_send.sh --hours 72 --no-send \

  >> "${TEST_LOG}" 2>&1

# --- summary ---
RAW_LAST=$(ls -1t "${TEST_BASE}/raw"/*.xlsx 2>/dev/null | head -n 1 || true)
SAFE_CNT=$(grep -c "\[SAFE\] DRY RUN" "${TEST_LOG}" 2>/dev/null || true)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TESTMODE] SUMMARY safe=${SAFE_CNT} raw=${RAW_LAST}" | sudo tee -a "${TEST_LOG}" >/dev/null || true

