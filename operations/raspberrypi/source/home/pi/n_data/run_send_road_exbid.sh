#!/bin/bash



BASE_DIR="/home/pi/n_data"

LOG_DIR="$BASE_DIR/logs"

LOG_FILE="$LOG_DIR/send_road_exbid.log"



cd "$BASE_DIR" || exit 1

mkdir -p "$LOG_DIR"



echo "[$(date '+%F %T')] [ROAD] START" >> "$LOG_FILE"



/usr/bin/python3 -u /home/pi/n_data/send_road_exbid.py --send >> "$LOG_FILE" 2>&1

RC_OLD=$?



/usr/bin/python3 -u /home/pi/n_data/send_exroad_ready.py --send >> "$LOG_FILE" 2>&1

RC_NEW=$?



RC=0

if [ "$RC_OLD" -ne 0 ]; then

    RC="$RC_OLD"

fi

if [ "$RC_NEW" -ne 0 ]; then

    RC="$RC_NEW"

fi



echo "[$(date '+%F %T')] [ROAD] END old_rc=$RC_OLD new_rc=$RC_NEW rc=$RC" >> "$LOG_FILE"

exit "$RC"

