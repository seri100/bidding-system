
#!/bin/bash

set -eu

(set -o pipefail) 2>/dev/null || true



ROOT="/mnt/vol1/road/_backup"

LOG="/home/pi/road/cleanup_exbid.log"



mkdir -p "$(dirname "$LOG")"

{

  echo "[$(date '+%F %T')] start cleanup"



  if [[ ! -d "$ROOT" ]]; then

    echo "[WARN] $ROOT 디렉터리가 없어 건너뜁니다."

    exit 0

  fi



  # 45일 지난 엑셀 백업 삭제 (스냅샷/RAW 둘 다 포함)

  nice -n 10 ionice -c3 find "$ROOT" -type f \( -name '*.xlsx' -o -name '*.xls' \) -mtime +45 -print -delete



  # 오래된 임시파일 정리(.part 등, 1일 경과)

  nice -n 10 ionice -c3 find "$ROOT" -type f -name '*.part' -mtime +1 -print -delete



  # 비어 있는 날짜 폴더 정리

  find "$ROOT" -type d -empty -mindepth 1 -print -delete



  echo "[$(date '+%F %T')] done"

} >> "$LOG" 2>&1

