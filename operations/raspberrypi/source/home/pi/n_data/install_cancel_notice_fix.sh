#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-main_send_clean.py}"
FIXED="${2:-main_send_clean_cancel_fixed.py}"

if [[ ! -f "$SOURCE" ]]; then
  echo "[ERROR] 기존 실행 파일을 찾을 수 없습니다: $SOURCE" >&2
  exit 1
fi

if [[ ! -f "$FIXED" ]]; then
  echo "[ERROR] 수정본을 찾을 수 없습니다: $FIXED" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="${SOURCE}.bak.${STAMP}"
TMP="${SOURCE}.new.${STAMP}"

python3 -m py_compile "$FIXED"
cp -a "$SOURCE" "$BACKUP"
cp "$FIXED" "$TMP"
chmod --reference="$SOURCE" "$TMP" 2>/dev/null || true
mv "$TMP" "$SOURCE"
python3 -m py_compile "$SOURCE"

echo "[OK] 적용 완료: $SOURCE"
echo "[OK] 백업 파일: $BACKUP"
echo
echo "안전 확인:"
echo "  ONLY_BID=R26BK01552481 ONLY_CANCEL=1 HARD_NO_SEND=1 DBG_BID=R26BK01552481 python3 $SOURCE --hours 1 --no-send"
echo
echo "실제 발송:"
echo "  ONLY_BID=R26BK01552481 ONLY_CANCEL=1 python3 $SOURCE --hours 1"
