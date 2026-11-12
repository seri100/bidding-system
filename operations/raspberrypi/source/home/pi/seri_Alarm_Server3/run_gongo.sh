
#!/bin/bash



# 오늘 날짜 기반 로그 파일 이름 설정

TODAY=$(date '+%Y%m%d')

LOG_DIR="/mnt/gon_autoREDACTED_PRIVATE_VALUE"

LOG_PATH="$LOG_DIR/run_log_${TODAY}.txt"

SMS_SUCCESS_LOG="$LOG_DIR/sms_success_${TODAY}.log"

SMS_FAIL_LOG="$LOG_DIR/sms_fail_${TODAY}.log"



# 실행 로그 기록

echo "=== 실행 시작: $(date '+%Y. %m. %d. (%a) %T %Z') ===" >> "$LOG_PATH"

echo "실행 시작" >> "$LOG_PATH"



# 메인 스크립트 실행, 결과를 로그에 저장

/usr/bin/python3 /home/pi/seri_Alarm_Server3/main_gongo.py >> "$LOG_PATH" 2>&1



# 실행 종료 로그 기록

echo "=== 실행 종료: $(date '+%Y. %m. %d. (%a) %T %Z') ===" >> "$LOG_PATH"

echo "" >> "$LOG_PATH"



# 오래된 로그(30일 이상) 자동 삭제

find "$LOG_DIR" -name "run_log_*.txt" -type f -mtime +30 -exec rm {} \;

find "$LOG_DIR" -name "sms_success_*.log" -type f -mtime +30 -exec rm {} \;

find "$LOG_DIR" -name "sms_fail_*.log" -type f -mtime +30 -exec rm {} \;


