#!/bin/bash

set -u



BASE="/home/pi/bid_elec"

NAS="/mnt/vol1/bid/bid_elec"

LOG_DIR="$BASE/logs"

LOG_FILE="$LOG_DIR/kepco_srm_$(date +%Y%m%d).log"



mkdir -p "$LOG_DIR"



exec >> "$LOG_FILE" 2>&1



echo

echo "[$(date '+%F %T')] ===== KEPCO SRM 시작 ====="



if ! mountpoint -q /mnt/vol1; then

    echo "[$(date '+%F %T')] [ERROR] NAS /mnt/vol1 마운트 안 됨"

    exit 10

fi



if [ ! -d "$NAS" ]; then

    echo "[$(date '+%F %T')] [ERROR] 저장 폴더 없음: $NAS"

    exit 11

fi



if [ ! -w "$NAS" ]; then

    echo "[$(date '+%F %T')] [ERROR] 저장 폴더 쓰기 불가: $NAS"

    exit 12

fi



cd "$BASE" || exit 13



export N_DATA_ENV=PROD

export N_DATA_BASE=/mnt/vol1/bid/n_data

export PYTHONUNBUFFERED=1



/usr/bin/python3 -u "$BASE/kepco_srm_operate.py" --days 14

RET=$?



if [ "$RET" -eq 0 ]; then

    if [ -f "$BASE/kepco_srm_send_state.sqlite3" ]; then

        # __KEPCO_SQLITE_BACKUP_V1__

        if ! /usr/bin/python3 -c 'import sqlite3,sys; src=sqlite3.connect(sys.argv[1],timeout=30); dst=sqlite3.connect(sys.argv[2],timeout=30); src.backup(dst); dst.close(); src.close()' "$BASE/kepco_srm_send_state.sqlite3" "$NAS/kepco_srm_send_state.backup.sqlite3"; then

            echo "[ERROR] SQLite 백업 실패"

            exit 20

        fi

    fi



    echo "[$(date '+%F %T')] [OK] 정상 완료"

else

    echo "[$(date '+%F %T')] [ERROR] 종료코드=$RET"

fi



echo "[$(date '+%F %T')] ===== KEPCO SRM 종료 ====="

exit "$RET"

