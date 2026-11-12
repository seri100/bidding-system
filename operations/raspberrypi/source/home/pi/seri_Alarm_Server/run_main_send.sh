
#!/usr/bin/env bash

set -euo pipefail



LOGDIR="/home/pi/seri_Alarm_Server/logs"

mkdir -p "$LOGDIR"



PY="/home/pi/seri_Alarm_Server/.venv/bin/python"

[ -x "$PY" ] || PY="/usr/bin/python3"



# ===== 환경파일 주입 (SERVICE_KEY 등) =====

set -a

[ -f /etc/seri-main-send.env ] && . /etc/seri-main-send.env || true

set +a



echo "[WRAP] $(date +'%F %T') start pid=$$ PY=$PY" | tee -a "$LOGDIR/run_$(date +%Y%m%d).log"



cd /home/pi/n_data

echo "[WRAP] CWD=$(pwd)" | tee -a "$LOGDIR/run_$(date +%Y%m%d).log"

echo "[ENV] SERVICE_KEY len=${#SERVICE_KEY}" | tee -a "$LOGDIR/run_$(date +%Y%m%d).log"

echo "[WRAP] FILE=$(readlink -f main_send.py)" | tee -a "$LOGDIR/run_$(date +%Y%m%d).log"

[ -f settings.xlsx ] && \

  echo "[WRAP] settings.xlsx OK ($(stat -c %s settings.xlsx) bytes)" | tee -a "$LOGDIR/run_$(date +%Y%m%d).log" || \

  echo "[WRAP] settings.xlsx MISSING" | tee -a "$LOGDIR/run_$(date +%Y%m%d).log"



exec "$PY" -u main_send.py 2>&1 | tee -a "$LOGDIR/main_send.stdout.log"

