
#!/bin/bash

set -e



source /home/pi/venv-bidsync/bin/activate

cd /home/pi/bidsync



LOG_FILE=/home/pi/logs/daily_sync_cnstwk_retry.log

LOCK_FILE=/home/pi/bidsync/.run_cnstwk.lock



echo "===== [CNSTWK RETRY START] $(date '+%F %T') =====" >> "$LOG_FILE"



exec 9>"$LOCK_FILE"

if ! flock -n 9; then

    echo "===== [CNSTWK RETRY SKIP - LOCKED] $(date '+%F %T') =====" >> "$LOG_FILE"

    exit 0

fi



python /home/pi/bidsync/daily_sync_final_insert_cnstwk.py >> "$LOG_FILE" 2>&1



echo "===== [CNSTWK RETRY END] $(date '+%F %T') =====" >> "$LOG_FILE"

