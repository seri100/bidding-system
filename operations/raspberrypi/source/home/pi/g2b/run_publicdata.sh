
#!/bin/bash

# ===================================================

# run_publicdata.sh : 공공데이터포털 입찰공고 자동수집

# 로그 → /home/pi/g2b/logs/publicdata_YYYYMMDD.log

# ===================================================



cd /home/pi/g2b



NOW=$(date '+%Y%m%d_%H%M%S')

LOGFILE="/home/pi/g2b/logs/publicdata_${NOW}.log"



echo "[START] $(date '+%F %T')" | tee -a "$LOGFILE"



/usr/bin/python3 -u /home/pi/g2b/publicdata_notice.py \

  --ind 0040,0039 \

  --regions "경상북도,인천광역시,서울특별시" \

  --due_to $(date -d '+30 day' '+%Y-%m-%d') \

  >> "$LOGFILE" 2>&1



RC=$?

echo "[END] $(date '+%F %T') RC=$RC" | tee -a "$LOGFILE"



# 오류 감지 시 알림톡 전송

if [ $RC -ne 0 ]; then

    MSG="[세리공영]\n공공데이터 자동실행 오류 발생!\n시간: $(date '+%F %T')\nRC=$RC"

    curl -s -X POST REDACTED_PRIVATE_VALUE \

      -d "apikey=REDACTED_PRIVATE_VALUE" \

      -d "userid=seri825" \

      -d "senderkey=REDACTED_PRIVATE_VALUE" \

      -d "tpl_code=UC_8365" \

      -d "sender=029302266" \

      -d "receiver_1=REDACTED_PRIVATE_VALUE" \

      -d "message_1=${MSG}" \

      -d "subject_1=공공데이터오류" > /dev/null

fi

