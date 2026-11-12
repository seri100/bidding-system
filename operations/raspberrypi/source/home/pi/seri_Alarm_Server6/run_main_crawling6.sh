
#!/bin/bash



BASE_DIR="/home/pi/seri_Alarm_Server6"

cd "$BASE_DIR" || exit 1



# 현재 시간(HHMM)

HM=$(date +%H%M)



# 08:43 ~ 18:23 사이에만 실행

if [ "$HM" -lt 843 ] || [ "$HM" -gt 1823 ]; then

  echo "[$(date '+%F %T')] [SKIP] HM=${HM} (allowed 0843~1823)"

  exit 0

fi



LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"



echo "[$(date '+%F %T')] [RUN] main_crawling.py (HM=${HM})" | tee -a "$LOG_FILE"



# 실제 크롤링 실행

/usr/bin/python3 -u "$BASE_DIR/main_crawling.py" >> "$LOG_FILE" 2>&1

# EXIT_WITH_RC_FROM_MAIN_CRAWLING
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "[$(date '+%F %T')] [ERROR] main_crawling.py failed rc=$rc"
  exit "$rc"
fi

CODE=$?



if [ "$CODE" -ne 0 ]; then

  echo "[$(date '+%F %T')] [WARN] main_crawling.py exited with code ${CODE} (DB 오류 등, systemd에는 성공으로 처리)" | tee -a "$LOG_FILE"

fi



# 여기서는 항상 성공으로 종료 (DB 오류는 로그로만 남김)

exit 0

