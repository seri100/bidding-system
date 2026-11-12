#!/bin/bash
# =============================================
# /home/pi/result/setup_cron.sh
# crontab 자동 등록 스크립트
# 실행: bash /home/pi/result/setup_cron.sh
# =============================================

PYTHON_PATH=$(which python3)
SCRIPT_PATH="/home/pi/result/bid_collector.py"
CRON_LOG="/home/pi/result/logs/cron.log"

# 로그 디렉토리 생성
mkdir -p /home/pi/result/logs

echo "REDACTED_LONG_LITERAL"
echo "  나라장터 수집기 crontab 등록"
echo "REDACTED_LONG_LITERAL"
echo "  Python  : $PYTHON_PATH"
echo "  Script  : $SCRIPT_PATH"
echo "  CronLog : $CRON_LOG"
echo "REDACTED_LONG_LITERAL"

# 기존 bid_collector 관련 cron 제거 후 재등록
(
  crontab -l 2>/dev/null | grep -v "bid_collector"
  echo "# ── 나라장터 입찰공고 수집 (매일 08:00, 14:00) ──"
  echo "0  8 * * * $PYTHON_PATH $SCRIPT_PATH >> $CRON_LOG 2>&1"
  echo "0 14 * * * $PYTHON_PATH $SCRIPT_PATH >> $CRON_LOG 2>&1"
) | crontab -

echo ""
echo "✅ crontab 등록 완료! 현재 설정:"
echo "REDACTED_LONG_LITERAL"
crontab -l
echo "REDACTED_LONG_LITERAL"
