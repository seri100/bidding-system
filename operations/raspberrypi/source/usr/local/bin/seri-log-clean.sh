
#!/usr/bin/env bash

set -eu
(set -o pipefail) 2>/dev/null || true

LOG_DIR="/home/pi/seri_Alarm_Server"

# 15일 지난 로컬 로그만 정리 (공유폴더는 아님)

find "$LOG_DIR" -type f \( -name '*.log' -o -name 'main_send.log*' -o -name 'error_week_*.log' -o -name 'errlog.txt' -o -name 'normlog.txt' -o -name 'tobeSend*.txt' \) -mtime +30 -print -delete

