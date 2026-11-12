
#!/usr/bin/env bash

set -euo pipefail



UNIT="main_send.service"

BASE="/home/pi/n_data"

REPORTS="$BASE/reports"

NOTIFY_RECV="${NOTIFY_RECV:-REDACTED_PRIVATE_VALUE}"



# 알림 스크립트 후보(있으면 사용)

CAND_SCRIPTS=(

  "/home/pi/n_data/kakao_send_tb0485.py"

  "/home/pi/g2b_db/kakao_send_tb0485.py"

  "/home/pi/g2b_db/app/kakao_send_tb0485.py"

)



_pick_notify_script() {

  local p

  for p in "${CAND_SCRIPTS[@]}"; do

    if [ -f "$p" ]; then

      echo "$p"

      return 0

    fi

  done

  return 1

}



_notify_fail() {

  local title="$1"

  local detail="$2"

  local report_path="$3"



  local py

  if py="$(_pick_notify_script)"; then

    # ⚠️ 아래 호출 방식은 “스크립트가 message/receiver 인자를 받는 경우”에 맞춰져 있음.

    # 너희 스크립트가 다른 인터페이스면, 여기만 실제 인터페이스에 맞게 1줄 수정하면 됨.

    #

    # - 인자형(권장): python3 kakao_send_tb0485.py "<message>" "<receiver>"

    # - 또는 환경변수형을 쓰는 구조면, 그에 맞게 바꾸면 됨.

    local msg="[세리공영][AUTO-CHECK] ${title}\n${detail}\nREPORT=${report_path}"

    python3 -u "$py" "$msg" "$NOTIFY_RECV" >/dev/null 2>&1 || true

    echo "[NOTIFY] attempted via: $py -> $NOTIFY_RECV"

  else

    echo "[NOTIFY][SKIP] no kakao_send_tb0485.py found in candidates"

  fi

}



ts="$(date +%Y%m%d_%H%M%S)"

out="$REPORTS/main_send_autocheck_${ts}.log"



rc=0

title="PASS"

detail=""



{

  echo "===== MAIN_SEND AUTO CHECK ====="

  echo "Time: $(date)"

  echo "Unit: ${UNIT}"

  echo "NotifyReceiver: ${NOTIFY_RECV}"

  echo



  echo "[STEP] wait 60 seconds to accumulate logs..."

  sleep 60

  echo



  echo "[STEP] last 200 lines of ${UNIT}"

  journalctl -u "$UNIT" -n 200 --no-pager -o cat || true

  echo



  echo "[STEP] error pattern scan (error|fail|traceback)"

  if journalctl -u "$UNIT" -n 400 --no-pager -o cat | egrep -i "error|fail|traceback" >/dev/null; then

    echo "[RESULT] ERROR pattern detected"

    journalctl -u "$UNIT" -n 400 --no-pager -o cat | egrep -in "error|fail|traceback" || true

    rc=2

    title="FAIL"

    detail="error pattern detected in journalctl"

  else

    echo "[RESULT] No error pattern detected"

  fi

  echo



  echo "[STEP] success markers scan (Succeeded / success=True)"

  ok1=0; ok2=0

  if journalctl -u "$UNIT" -n 200 --no-pager -o cat | grep -q "Succeeded"; then ok1=1; fi

  if journalctl -u "$UNIT" -n 400 --no-pager -o cat | grep -q "success=True"; then ok2=1; fi

  echo "Succeeded marker: $ok1"

  echo "success=True marker: $ok2"



  if [ "$rc" -eq 0 ]; then

    if [ "$ok1" -eq 1 ] || [ "$ok2" -eq 1 ]; then

      echo "[RESULT] PASS"

      rc=0

      title="PASS"

      detail="success markers found"

    else

      echo "[RESULT] WARN: could not find explicit success markers (check logs above)"

      rc=1

      title="WARN"

      detail="no explicit success markers found"

    fi

  fi



  echo

  echo "[FINAL] rc=$rc title=$title detail=$detail"

} | tee "$out"



# WARN/FAIL이면 알림 시도

if [ "$rc" -ne 0 ]; then

  _notify_fail "$title" "$detail" "$out" | tee -a "$out" || true

fi



exit "$rc"

