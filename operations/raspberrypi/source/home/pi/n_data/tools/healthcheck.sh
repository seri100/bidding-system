
#!/usr/bin/env bash

set -Eeuo pipefail



# ============ 색상 & 로깅 ============

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'

ok(){   echo -e "${GRN}[OK]${NC}  $*"; }

warn(){ echo -e "${YLW}[WARN]${NC} $*"; }

fail(){ echo -e "${RED}[FAIL]${NC} $*"; return 1; }

info(){ echo -e "${BLU}[INFO]${NC} $*"; }



STAMP="$(date '+%F %T %Z')"

echo "================= healthcheck ( $STAMP ) ================="



# ============ 환경 요약 ============

echo "HOST   : $(hostname)"

echo "USER   : $USER"

echo "PWD    : $(pwd)"

echo "PYTHON : $(command -v python3 || true) ($(python3 -V 2>/dev/null || echo 'python3 not found'))"

echo



# ============ 1) systemd / 프로세스 ============

info "systemd 서비스 상태(main_send)"

if systemctl is-enabled main_send &>/dev/null; then ok "enabled"; else warn "disabled(부팅 자동실행 아님)"; fi

if systemctl is-active  main_send &>/dev/null; then ok "active"; else warn "inactive(동작 안함)"; fi

UNIT=$(systemctl cat main_send 2>/dev/null || true)

if grep -q 'flock -n /var/lock/main_send.lock' <<<"$UNIT"; then ok "유닛에 flock 중복방지 적용됨"; else warn "유닛에 flock 미적용"; fi



info "프로세스 점검(main_send.py)"

PGR=$(pgrep -af "python3 .*main_send.py" || true)

CNT=$(printf "%s\n" "$PGR" | sed '/^\s*$/d' | wc -l | awk '{print $1}')

echo "$PGR"

if systemctl is-active main_send &>/dev/null; then

  if [ "$CNT" -eq 2 ]; then ok "프로세스 2개(flock + 자식 python) 정상"; else warn "프로세스 $CNT개 감지(정상: 2)"; fi

else

  if [ "$CNT" -eq 0 ]; then ok "서비스 비활성 & 실행 프로세스 없음"; else warn "서비스 비활성인데 실행 중($CNT)"; fi

fi

echo



# ============ 2) 필수 파일/구성 ============

REQ_FILES=(

  "/home/pi/n_data/main_send.py"

  "/home/pi/n_data/alligo.py"

  "/home/pi/n_data/companys.xlsx"

  "/home/pi/n_data/settings.xlsx"

)

info "필수 파일 존재/정보"

for f in "${REQ_FILES[@]}"; do

  if [ -f "$f" ]; then

    SZ=$(stat -c '%s' "$f" 2>/dev/null || echo -n "?")

    MT=$(date -d "@$(stat -c '%Y' "$f" 2>/dev/null || echo 0)" '+%F %T' 2>/dev/null || echo "?")

    ok "$f (size=${SZ}B, mtime=$MT)"

  else

    fail "$f (없음)" || true

  fi

done

echo



# ============ 3) 파이썬 모듈 ============

info "파이썬 모듈 상태(requests, openpyxl, PyMySQL)"

python3 - <<'PY' || true

import sys

def chk(mod):

    try:

        m=__import__(mod)

        ver=getattr(m,'__version__','(no __version__)')

        print(f"[OK] {mod} {ver}")

    except Exception as e:

        print(f"[MISS] {mod}: {e}")

for m in ["requests","openpyxl","pymysql"]:

    chk(m)

PY

echo



# ============ 4) 네트워크/API ============

info "DNS 확인(apisdomain)"

getent hosts apis.data.go.kr || warn "DNS 조회 실패"



info "공공데이터포털 HTTP/HTTPS 헤더 요청(6초 제한)"

if curl -sS -m 6 -I https://apis.data.go.kr/ >/dev/null; then ok "https://apis.data.go.kr 응답 OK"; else warn "https://apis.data.go.kr 타임아웃/실패"; fi

if curl -sS -m 6 -I https://apis.data.go.kr/ >/dev/null; then ok "https://apis.data.go.kr 응답 OK"; else warn "https://apis.data.go.kr 타임아웃/실패(서비스 정책상 막혀있을 수 있음)"; fi

echo



# ============ 5) 알리고 토큰/템플릿 ============

info "알리고 토큰/템플릿 상태 확인"

python3 - <<'PY' || true

import importlib.util, json, sys, requests, traceback

PATH="/home/pi/n_data/alligo.py"

try:

    spec = importlib.util.spec_from_file_location("alligo", PATH)

    mod  = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(mod)

except Exception as e:

    print(f"[FAIL] alligo.py import 실패: {e}")

    sys.exit(0)



A = mod.Alligo()

try:

    tok = A.getToken()

    if not tok:

        print("[FAIL] 알리고 토큰 발급 실패")

        sys.exit(0)

    else:

        print("[OK]  알리고 토큰 OK")

except Exception:

    print("[FAIL] 알리고 토큰 예외")

    traceback.print_exc()

    sys.exit(0)



try:

    # 템플릿 목록 원문 요청해서 상태까지 표시

    resp = requests.post(A.templateListUrl, {

        'apikey': A.apikey, 'userid': A.id, 'token': A.token, 'senderkey': A.kakaoSender

    }, timeout=12)

    j = resp.json()

    if j.get("code")!=0:

        print(f"[FAIL] 템플릿 조회 실패: {j}")

    else:

        lst = j.get("list",[])

        print("=== 템플릿 상태 요약 ===")

        for it in lst:

            code = it.get("templtCode")

            name = it.get("templtName")

            stat = it.get("apprvStat") or it.get("status") or "-"

            print(f"- {code:<8} | {name} | status={stat}")

        # TB_0485 필수 체크

        st = None

        for it in lst:

            if it.get("templtCode")=="TB_0485":

                st = it.get("apprvStat") or it.get("status")

                break

        if st is None:

            print("[WARN] TB_0485 템플릿이 목록에 없음")

        elif st!="A":

            print(f"[WARN] TB_0485 status={st} (A가 아니면 알림톡이 문자 대체될 수 있음)")

        else:

            print("[OK]  TB_0485 승인 상태 A")

except Exception:

    print("[FAIL] 템플릿 조회 예외")

    traceback.print_exc()

PY

echo



# ============ 6) 최근 서비스 로그 요약 ============

info "최근 서비스 로그 60줄"

journalctl -u main_send -n 60 --no-pager || true

echo



# ============ 7) (선택) 테스트 발송 ============

if [ "${SEND_TEST:-0}" = "1" ]; then

  PHONE="${PHONE:-REDACTED_PRIVATE_VALUE}"

  info "테스트 발송 시도(TB_0485) -> $PHONE"

  python3 - <<PY || true

import importlib.util, requests, datetime as dt

PATH="/home/pi/n_data/alligo.py"

spec=importlib.util.spec_from_file_location("alligo", PATH)

mod=importlib.util.module_from_spec(spec)

spec.loader.exec_module(mod)

A=mod.Alligo()

A.getToken()

tpl="TB_0485"

sender="$PHONE"

recv=["$PHONE"]



# TB_0485 포맷 맞춰 메시지 구성

msg = (

"[세리공영]\n\n"

f"공고명 : 건강점검 테스트\n"

f"입찰마감일시 :  {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

f"공동도급지역 : 충청북도\n"

f"공동도급비율 : 20%\n"

f"추정금액 : ₩123,456\n"

f"공고번호 : TEST-0000 - 00"

)

ok = A.sendTalk(tpl, sender, "[세리공영] 공사정보 점검", msg, recv)

print("SEND_TEST =", ok)

PY

else

  info "테스트 발송 생략(SEND_TEST=1 로 실행 시 발송)"

fi



echo

ok "healthcheck 완료"

