
#!/usr/bin/env bash

set -euo pipefail



LOG="/home/pi/n_data/logs/run_main_send.log"

ERR="/home/pi/n_data/logs/run_main_send_error.log"



echo "[HEALTHCHECK] $(date '+%F %T')"



echo "---- last 60 lines (main log) ----"

tail -n 60 "$LOG" || true



echo "---- last 40 lines (error log) ----"

tail -n 40 "$ERR" || true



# 간단 판정(원하면 더 강화 가능)

if tail -n 200 "$LOG" | grep -q "\[MAIN\] === main_send.py END (success=True) ==="; then

  echo "[OK] last run success marker found"

  exit 0

fi



echo "[WARN] success marker not found (check logs)"

exit 1

