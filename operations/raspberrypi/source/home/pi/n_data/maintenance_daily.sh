
#!/bin/bash

set -e



BASE="/mnt/vol1/bid/n_data"

APP="/home/pi/n_data"



LOG_DIR="$APP/logs"

MAINT_LOG="$LOG_DIR/maintenance_$(date +%Y%m%d).log"



mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] maintenance start" >> "$MAINT_LOG"



# 1. sent_keys.txt 최근 5000개만 유지

if [ -f "$BASE/sent_keys.txt" ]; then

  tail -n 5000 "$BASE/sent_keys.txt" | sort -u > "$BASE/sent_keys.tmp"

  mv "$BASE/sent_keys.tmp" "$BASE/sent_keys.txt"

  echo "[$(date '+%F %T')] sent_keys trimmed" >> "$MAINT_LOG"

fi



# 2. 30일 지난 로그 삭제

find "$LOG_DIR" -type f -name "*.log" -mtime +30 -print -delete >> "$MAINT_LOG" 2>&1 || true



# 4. 2일 지난 엑셀파일 백업

for d in raw split report; do

  SRC="$BASE/$d"

  BAK="$BASE/backup/$d"

  mkdir -p "$BAK"



  if [ -d "$SRC" ]; then

    find "$SRC" -maxdepth 1 -type f \( -name "*.xlsx" -o -name "*.xls" \) -mtime +2 -print -exec mv -n {} "$BAK/" \; >> "$MAINT_LOG" 2>&1 || true

  fi

done



# 3. 30일 지난 엑셀파일 삭제 - 원본/백업 모두

find "$BASE" -type f \( -name "*.xlsx" -o -name "*.xls" \) -mtime +30 -print -delete >> "$MAINT_LOG" 2>&1 || true



echo "[$(date '+%F %T')] maintenance end" >> "$MAINT_LOG"

