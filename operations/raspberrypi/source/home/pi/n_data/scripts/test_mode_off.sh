#!/usr/bin/env bash

set -euo pipefail



TEST_BASE="/mnt/vol1/bid/n_data_test"

LOCK_FILE="/home/pi/n_data/.lock/main_send_test.lock"

TEST_LOG="${TEST_BASE}/logs/run_main_send_test.log"



rm -f "${LOCK_FILE}" 2>/dev/null || true

sudo systemctl start outbox_sender.timer 2>/dev/null || true



echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TESTMODE] OFF" | sudo tee -a "${TEST_LOG}" >/dev/null

