
#!/bin/bash



BASE_DIR="/home/pi/n_data"

cd "$BASE_DIR" || exit 1



export N_DATA_ENV="${N_DATA_ENV:-PROD}"

export N_DATA_BASE="${N_DATA_BASE:-/mnt/vol1/bid/n_data}"

export NAS_BASE="${NAS_BASE:-/mnt/vol1/bid/n_data}"

export HARD_NO_SEND="${HARD_NO_SEND:-0}"

export FORCE_NO_SEND="${FORCE_NO_SEND:-0}"



echo "[ENV-WRAPPER] N_DATA_ENV=$N_DATA_ENV N_DATA_BASE=$N_DATA_BASE NAS_BASE=$NAS_BASE HARD_NO_SEND=$HARD_NO_SEND FORCE_NO_SEND=$FORCE_NO_SEND pwd=$(pwd)"



LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d).log"

RUN_LOG=$(mktemp /tmp/n_data_main_run.XXXXXX.log)



cleanup_run_log() {

    rm -f "$RUN_LOG"

}

trap cleanup_run_log EXIT



NAS_OK=1

if ! mountpoint -q /mnt/vol1; then

    NAS_OK=0

elif [ ! -d "$N_DATA_BASE" ]; then

    NAS_OK=0

elif [ ! -w "$N_DATA_BASE" ]; then

    NAS_OK=0

fi



echo "[$(date '+%F %T')] START NAS_OK=$NAS_OK" >> "$RUN_LOG"



# NAS_DATA_PREFLIGHT_V1: mount alone does not guarantee the data is present.
if [ "$NAS_OK" -ne 1 ] || [ ! -s "$N_DATA_BASE/bid_api_key.txt" ] || [ ! -s "$N_DATA_BASE/sent_keys.txt" ] || [ ! -d "$N_DATA_BASE/raw" ] || [ ! -d "$N_DATA_BASE/split" ]; then
    NAS_OK=0
    echo "[FATAL][NAS_DATA_MISSING] NAS 운영 데이터 확인 실패: API 키/발송 이력/raw/split 경로 확인 필요" >> "$RUN_LOG"
    RET=73
else
    N_DATA_AUTO_RECOVERY=1 /usr/bin/timeout --signal=TERM --kill-after=30s 30m python3 -u main_send.py >> "$RUN_LOG" 2>&1
    RET=$?
fi



echo "[$(date '+%F %T')] END (RET=$RET NAS_OK=$NAS_OK)" >> "$RUN_LOG"

cat "$RUN_LOG" >> "$LOG_FILE"





python3 "$BASE_DIR/error_alert_monitor.py" --log "$RUN_LOG" --return-code "$RET" --nas-ok "$NAS_OK" >> "$LOG_FILE" 2>&1

ALERT_RET=$?



if [ "$ALERT_RET" -ne 0 ]; then

    echo "[$(date '+%F %T')] ALERT_MONITOR_ERROR RET=$ALERT_RET" >> "$LOG_FILE"

fi



exit "$RET"


# RECOVERY_RUN_LOG_FIX_V1
