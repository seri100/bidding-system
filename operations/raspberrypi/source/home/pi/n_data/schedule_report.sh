
#!/bin/bash

# 공공데이터의 공사공고 가져오기 - 자동실행 스크립트 요약 리포트 생성



OUTDIR="/mnt/vol1/bid/n_data"

mkdir -p "$OUTDIR"



NOW="$(date '+%Y-%m-%d %H:%M:%S')"

STAMP="$(date '+%Y%m%d_%H%M')"

REPORT="$OUTDIR/자동실행_스크립트_요약표_${STAMP}.md"



HOSTNAME="$(hostname)"



{

  echo "# 자동실행 스크립트 요약표"

  echo ""

  echo "- 생성시각 : $NOW"

  echo "- 호스트   : $HOSTNAME"

  echo ""

  echo "## 1. systemd timers (전체)"

  echo ""

  echo '```bash'

  systemctl list-timers --all

  echo '```'

  echo ""



  echo "## 2. 주요 systemd 서비스 목록 (seri, n_data, gd, rclone)"

  echo ""

  echo '```bash'

  systemctl list-units --type=service --all | grep -E 'seri|n_data|gd|rclone' || echo "(관련 서비스 없음 또는 grep 결과 없음)"

  echo '```'

  echo ""



  echo "## 3. 주요 systemd 서비스 상태 요약"

  echo ""

  # 관련 서비스들만 뽑아서 짧게 status 출력

  for s in $(systemctl list-units --type=service --all | grep -E 'seri|n_data|gd|rclone' | awk '{for (i=1;i<=NF;i++) if ($i ~ /\.service$/) print $i}'); do

      echo "### $s"

      echo '```bash'

      systemctl status "$s" --no-pager -n 5 || echo "(status 조회 실패)"

      echo '```'

      echo ""

  done



  echo "## 4. pi 사용자 crontab"

  echo ""

  echo '```bash'

  crontab -l 2>/dev/null || echo "(pi crontab 없음)"

  echo '```'

  echo ""



  echo "## 5. root crontab"

  echo ""

  echo '```bash'

  sudo crontab -l 2>/dev/null || echo "(root crontab 없음 또는 권한 부족)"

  echo '```'

  echo ""



} > "$REPORT"

