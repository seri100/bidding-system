
#!/bin/bash

set -euo pipefail



SRC="REDACTED_PRIVATE_VALUE"

DST="REDACTED_PRIVATE_VALUE/exports"

LOG="/home/pi/seri_Alarm_Server6/logs/sync_exports_to_nas.log"



mkdir -p "$DST"



rsync -av --ignore-existing "$SRC"/LH_*.csv "$DST"/ >> "$LOG" 2>&1 || true



# 평일/주말 자동 정리

/home/pi/seri_Alarm_Server6/organize_exports_by_day.sh || true



echo "[$(date '+%F %T')] sync done" >> "$LOG"

