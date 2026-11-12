#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="/home/pi/n_data/main_send.py"
BASE="/home/pi/n_data"
STAMP="$(date +%Y%m%d_%H%M%S)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${BASE}/tools/change_notice_patch_20260714"
PRE_BACKUP="${TARGET}.pre_change_notice_${STAMP}"
DRYRUN="${BASE}/change_notice_patch_dryrun_${STAMP}.diff"

log() {
  printf '[DEPLOY] %s\n' "$*"
}

fail() {
  printf '[DEPLOY][ERROR] %s\n' "$*" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3가 설치되어 있지 않습니다."
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum 명령을 찾지 못했습니다."
[[ -f "${TARGET}" ]] || fail "대상 파일이 없습니다: ${TARGET}"
[[ -r "${TARGET}" ]] || fail "대상 파일을 읽을 수 없습니다: ${TARGET}"
[[ -w "${TARGET}" ]] || fail "대상 파일을 수정할 권한이 없습니다: ${TARGET}"

log "호스트=$(hostname) 사용자=$(id -un)"
log "대상=${TARGET}"

install -d -m 0755 "${INSTALL_DIR}"
install -m 0755 "${HERE}/apply_n_data_change_notice_patch.py" \
  "${INSTALL_DIR}/apply_n_data_change_notice_patch.py"
install -m 0755 "${HERE}/test_n_data_change_notice_patch.py" \
  "${INSTALL_DIR}/test_n_data_change_notice_patch.py"

PATCHER="${INSTALL_DIR}/apply_n_data_change_notice_patch.py"
TESTER="${INSTALL_DIR}/test_n_data_change_notice_patch.py"

log "배포 파일 SHA-256 확인"
sha256sum "${PATCHER}" "${TESTER}"

log "패처 자체 테스트"
python3 "${PATCHER}" --self-test

log "현재 main_send.py 구문 검사"
python3 -m py_compile "${TARGET}"

log "원본 사전 백업"
cp -a "${TARGET}" "${PRE_BACKUP}"
log "사전 백업=${PRE_BACKUP}"

log "적용 전 diff 생성"
python3 "${PATCHER}" --file "${TARGET}" --dry-run > "${DRYRUN}"
log "diff=${DRYRUN}"

log "변경공고 알림톡 패치 적용"
python3 "${PATCHER}" --file "${TARGET}"

log "적용 후 main_send.py 구문 검사"
python3 -m py_compile "${TARGET}"

log "필수 패치 마커 검증"
grep -q '__CHANGE_NOTICE_ALIMTALK_V1__' "${TARGET}" \
  || fail "변경공고 패치 마커가 없습니다."
grep -q 'raw.get("bdgtAmt")' "${TARGET}" \
  || fail "bdgtAmt 금액 fallback이 없습니다."
grep -q '\[CHANGE_NOTICE\]' "${TARGET}" \
  || fail "변경공고 로그 코드가 없습니다."
grep -q '\[변경공고\]' "${TARGET}" \
  || fail "알림톡 변경공고 표시 코드가 없습니다."

python3 - "${TARGET}" <<'PY'
from pathlib import Path
import ast
import sys

target = Path(sys.argv[1])
source = target.read_text(encoding="utf-8")
ast.parse(source)

required = [
    "def _is_change_notice(",
    "def _fr_get_presmpt_price(",
    "def _fr_apply_final_rule(",
    "__CHANGE_NOTICE_ALIMTALK_V1__",
    'raw.get("bdgtAmt")',
    'row["_is_change_notice"]',
    "[CHANGE_NOTICE]",
    "[변경공고]",
]
missing = [item for item in required if item not in source]
if missing:
    raise SystemExit("누락된 검증 항목: " + ", ".join(missing))

print("[DEPLOY][VERIFY] AST 및 필수 코드 검증 PASS")
PY

log "실행 중인 main_send 프로세스 확인(중단하지 않음)"
pgrep -af 'python3.*main_send\.py' || true

printf '\n[DEPLOY][OK] 변경공고 알림톡 패치 적용 및 검증 완료\n'
printf '[DEPLOY][OK] 대상: %s\n' "${TARGET}"
printf '[DEPLOY][OK] 사전 백업: %s\n' "${PRE_BACKUP}"
printf '[DEPLOY][OK] 적용 전 diff: %s\n' "${DRYRUN}"
printf '[DEPLOY][OK] 다음 정기 실행부터 R26BK01622372-001 같은 변경공고가 별도 알림 대상입니다.\n'
