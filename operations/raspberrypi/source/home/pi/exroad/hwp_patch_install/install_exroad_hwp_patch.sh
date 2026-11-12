#!/bin/bash
set -eu

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PATCH_DIR="$HERE/patched"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/home/pi/exroad/patch_backup_hwp_${TS}"

EXROAD_SRC="$PATCH_DIR/exroad_notify.py"
SENDER_SRC="$PATCH_DIR/send_exroad_ready.py"
EXROAD_DST="/home/pi/exroad/exroad_notify.py"
SENDER_DST="/home/pi/n_data/send_exroad_ready.py"
HWP5TXT="/home/pi/exroad/.venv_hwp/bin/hwp5txt"

echo "===== EXROAD HWP 보완 패치 설치 ====="

if systemctl is-active --quiet exroad-notify.service; then
    echo "[ERR] exroad-notify.service가 실행 중입니다. 종료 후 다시 실행하세요."
    exit 1
fi

if systemctl is-active --quiet send_road_exbid.service; then
    echo "[ERR] send_road_exbid.service가 실행 중입니다. 종료 후 다시 실행하세요."
    exit 1
fi

test -f "$EXROAD_SRC"
test -f "$SENDER_SRC"
test -f "$EXROAD_DST"
test -f "$SENDER_DST"
test -x "$HWP5TXT"

mkdir -p "$BACKUP_DIR"
cp -p "$EXROAD_DST" "$BACKUP_DIR/exroad_notify.py"
cp -p "$SENDER_DST" "$BACKUP_DIR/send_exroad_ready.py"
cp -p /home/pi/n_data/kakao_send_tb0485.py "$BACKUP_DIR/kakao_send_tb0485.py"

cp "$EXROAD_SRC" "$EXROAD_DST"
cp "$SENDER_SRC" "$SENDER_DST"
chmod 755 "$EXROAD_DST" "$SENDER_DST"

python3 -m py_compile "$EXROAD_DST" "$SENDER_DST" /home/pi/n_data/kakao_send_tb0485.py
bash -n /home/pi/n_data/run_send_road_exbid.sh

python3 - <<'PY'
import sys
sys.path.insert(0, "/home/pi/exroad")
import exroad_notify as ex

sample = """
5.1 이행방식 : 공동이행방식(지역의무공동도급)
5.3 대표자를 제외한 구성원은 최소지분율이 10%이상이어야 합니다.
5.4 공사현장 관할지역은 경기도입니다.
5.5.2 지역업체의 최소지분율은 30%이상이어야 합니다.
"""

parsed = ex.parse_exroad_notice_text(sample)
expected = {
    "joint_region": "경기도",
    "joint_rate": "30% 이상",
    "joint_method": "공동이행방식(지역의무공동도급)",
    "joint_member_min_rate": "10% 이상",
}

if parsed != expected:
    raise SystemExit("[ERR] 공고문 파서 검사 실패: %r" % parsed)

if ex.format_exroad_datetime("202609011040") != "2026-09-01 10:40":
    raise SystemExit("[ERR] 마감일시 변환 검사 실패")

print("[OK] 공고문 파서 검사 통과:", parsed)
print("[OK] 마감일시 변환 검사 통과")
PY

if test -f /mnt/vol1/bid/exroad/documents/202607203/입찰공고문.txt; then
    python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "/home/pi/exroad")
import exroad_notify as ex

p = Path("/mnt/vol1/bid/exroad/documents/202607203/입찰공고문.txt")
parsed = ex.parse_exroad_notice_text(p.read_text(encoding="utf-8", errors="replace"))
print("[OK] 실제 공고문 재검사:", parsed)
if parsed.get("joint_region") != "경기도" or parsed.get("joint_rate") != "30% 이상":
    raise SystemExit("[ERR] 실제 공고문 값 불일치")
PY
fi

cd /home/pi/n_data
python3 -u /home/pi/n_data/send_exroad_ready.py

echo "===== 설치 완료 ====="
echo "백업: $BACKUP_DIR"
echo "기존 delivered_keys는 유지되므로 이미 발송된 공고는 재발송되지 않습니다."
echo "다음 exroad-notify.timer 실행부터 신규 공고에 자동 적용됩니다."
