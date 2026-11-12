
#!/bin/bash

set -euo pipefail



BASE="REDACTED_PRIVATE_VALUE/exports"

LOG="/home/pi/seri_Alarm_Server6/logs/organize_exports.log"



TODAY=$(date +%F)

DOW=$(date +%u)   # 1=월 ... 6=토 7=일



if [ "$DOW" -ge 6 ]; then

  TYPE="weekend"

else

  TYPE="weekday"

fi



DEST="$BASE/$TYPE/$TODAY"

mkdir -p "$DEST"



shopt -s nullglob

for f in "$BASE"/LH_*.csv; do

  mv "$f" "$DEST/"

done



echo "[$(date '+%F %T')] moved to $DEST" >> "$LOG"

