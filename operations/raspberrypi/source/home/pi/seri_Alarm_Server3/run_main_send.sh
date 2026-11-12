
#!/usr/bin/env bash

# 공공데이터의 공사공고 가져오기

set -Eeuo pipefail



SRCDIR="/home/pi/n_data"                # ★ main_send.py 실제 위치

PYTHON="/usr/bin/python3"

LOCK="/tmp/seri3.lock"



ts() { date "+%F %T"; }

LOG="/home/pi/seri_Alarm_Server3/logs/run_$(date +%Y%m%d).log"



{

  echo "[$(ts)] [BOOT] seri3 wrapper start (cwd=$(pwd))"

  cd "$SRCDIR"



  if [ ! -f ./main_send.py ]; then

    echo "[$(ts)] [ERR] $SRCDIR/main_send.py 없음"

    exit 2

  fi



  # 겹침 방지

  if /usr/bin/flock -n "$LOCK" true; then

    :

  else

    echo "[$(ts)] [SKIP] already running (lock: $LOCK)"

    exit 0

  fi



  # 실제 실행

  echo "[$(ts)] [RUN] $PYTHON -u $SRCDIR/main_send.py"

  /usr/bin/flock -n "$LOCK" $PYTHON -u "$SRCDIR/main_send.py"

  echo "[$(ts)] [DONE] exit=$?"

} | tee -a "$LOG"

