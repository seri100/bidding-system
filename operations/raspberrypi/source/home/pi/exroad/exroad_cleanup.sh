#!/bin/bash

set -euo pipefail



BASE="/mnt/vol1/bid/exroad"

BACKUP="$BASE/backup"



KEEP_DAYS="${EXROAD_KEEP_DAYS:-30}"

DELETE_BACKUP_DAYS="${EXROAD_DELETE_BACKUP_DAYS:-90}"



TODAY=$(date +%Y%m%d)

BACKUP_DAY_DIR="$BACKUP/$TODAY"



mkdir -p "$BACKUP_DAY_DIR"



echo "REDACTED_LONG_LITERAL"

echo "[START] EXROAD cleanup $(date '+%Y-%m-%d %H:%M:%S')"

echo "[BASE] $BASE"

echo "[BACKUP] $BACKUP_DAY_DIR"

echo "[KEEP_DAYS] $KEEP_DAYS"

echo "[DELETE_BACKUP_DAYS] $DELETE_BACKUP_DAYS"

echo "REDACTED_LONG_LITERAL"



for DIR in raw target send_ready send_ready_test debug logs; do

    SRC="$BASE/$DIR"



    if [ ! -d "$SRC" ]; then

        echo "[SKIP] not found: $SRC"

        continue

    fi



    mkdir -p "$BACKUP_DAY_DIR/$DIR"



    echo "[BACKUP] $SRC -> $BACKUP_DAY_DIR/$DIR"



    find "$SRC" -type f -mtime +"$KEEP_DAYS" -print -exec mv -n {} "$BACKUP_DAY_DIR/$DIR/" \;

done



echo "[DELETE] old backup files older than $DELETE_BACKUP_DAYS days"

find "$BACKUP" -type f -mtime +"$DELETE_BACKUP_DAYS" -print -delete



echo "[DELETE] empty backup directories"

find "$BACKUP" -type d -empty -print -delete || true



echo "[DONE] EXROAD cleanup $(date '+%Y-%m-%d %H:%M:%S')"

