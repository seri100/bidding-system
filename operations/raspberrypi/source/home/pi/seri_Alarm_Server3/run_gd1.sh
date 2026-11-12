
#!/usr/bin/env bash

# --------------------------------------------------

# run_gd1.sh - gd-1 (2).py 자동 실행 래퍼 (안전버전)

#   - TARGET: REDACTED_PRIVATE_VALUE

#   - fallback: /home/pi/seri_Alarm_Server3/out_gon_auto

#   - 나중에 필요하면 "최근 파일" 기능은 따로 다시 추가

# --------------------------------------------------



set -e



NOW="$(date '+%Y-%m-%d %H:%M:%S')"



TARGET="REDACTED_PRIVATE_VALUE"

FALLBACK="/home/pi/seri_Alarm_Server3/out_gon_auto"

SCRIPT="/home/pi/seri_Alarm_Server3/gd-1 (2).py"

PYTHON="/usr/bin/python3"



echo "[$NOW] [BOOT] 시작: gd-1 (2).py"



# TARGET 디렉토리 준비

if [ ! -d "$TARGET" ]; then

    echo "[$NOW] [WARN] TARGET 디렉토리가 없어 생성 시도: $TARGET"

    mkdir -p "$TARGET" || true

fi



# TARGET에 쓰기 불가하면 fallback 사용

if [ ! -w "$TARGET" ]; then

    echo "[$NOW] [WARN] TARGET에 쓸 수 없음, fallback으로 변경: $FALLBACK"

    mkdir -p "$FALLBACK"

    TARGET="$FALLBACK"

fi



NOW2="$(date '+%Y-%m-%d %H:%M:%S')"

echo "[$NOW2] [INFO] TARGET: $TARGET (fallback: $FALLBACK)"



# 파이썬 스크립트 존재 확인

if [ ! -f "$SCRIPT" ]; then

    echo "[$NOW2] [ERR] 스크립트를 찾을 수 없음: $SCRIPT"

    exit 1

fi



echo "[$NOW2] [RUN] $PYTHON -u \"$SCRIPT\""

$PYTHON -u "$SCRIPT"

RET=$?



NOW_END="$(date '+%Y-%m-%d %H:%M:%S')"



if [ $RET -eq 0 ]; then

    echo "[$NOW_END] [DONE] gd-1 (2).py 정상 종료"

else

    echo "[$NOW_END] [ERR] gd-1 (2).py 종료 코드: $RET"

fi



exit $RET

