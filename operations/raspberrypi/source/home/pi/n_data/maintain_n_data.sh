
#!/usr/bin/env bash

set -euo pipefail



# === 설정 ===

BASE="/home/pi/n_data"

NOW="$(date +%Y%m%d_%H%M%S)"

BACKUP_DIR="$BASE/.backup_$NOW"

ARCHIVE="/home/pi/n_data_cleanup_$NOW.tar.gz"

LOG_DIR="$BASE/logs"

DRY_RUN=1     # 1=미리보기(삭제/이동 안함), 0=실행

KEEP_DAYS_LOG=30

PY_FILE="$BASE/main_send.py"



say() { echo -e "[`date '+%F %T'`] $*"; }



# === 0. 사전 점검 ===

say "작업 경로: $BASE"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"



# === 1. 현재 상태 요약 ===

say "용량 요약"

du -sh "$BASE" || true



say "상위 용량 디렉터리 Top 20"

du -h --max-depth=1 "$BASE" 2>/dev/null | sort -hr | head -20 || true



say "확장자/파일 유형 분포 Top 20"

( cd "$BASE" && find . -type f -printf "%f\n" | sed 's/.*\.//' | tr '[:upper:]' '[:lower:]' | sort | uniq -c | sort -nr | head -20 ) || true



# === 2. 정리 타깃 규칙(화이트리스트 우선) ===

#   삭제 후보 (안전 규칙):

#   - 파이썬 캐시: __pycache__/ , *.pyc, *.pyo

#   - 노트북 체크포인트: .ipynb_checkpoints/

#   - 임시/백업: *.tmp, *.temp, *.bak, *~ , *.swp, *.swo

#   - 중간 산출물(엑셀 임시): ~\$*.xlsx

#   - 로그: KEEP_DAYS_LOG 일 초과된 *.log, *.stdout.log, *.stderr.log, run_*.log

#   - 단발성 출력 흔적: *.once.log, *.old.log

#   - 중복 생성된 압축: *.zip, *.7z, *.tar, *.tar.gz (단, 최근 2개는 유지)

#

#   보존(화이트리스트 예시):

#   - settings.xlsx, company*.xlsx, *config*.{ini,yml,yaml,json}, .env*, *.key, *.token

#   - main_send.py, *_send.py, *crawling*.py, *gd*.py

#   - 스케줄/서비스 스크립트: *.service, *.timer, *.sh

#

#   실제 삭제 전, DRY_RUN으로 목록을 보여줍니다.



say "정리 대상 후보 수집 중…"



# 공통 find 옵션

FIND_BASE=(find "$BASE" -xdev)



# 2-1) 파이썬 캐시 / 체크포인트

MAP1=$BACKUP_DIR/delete_python_cache.list

"${FIND_BASE[@]}" \( -type d -name "__pycache__" -o -type d -name ".ipynb_checkpoints" \) -print > "$MAP1"



# 2-2) 파이썬 바이트코드 / 편집기 스왑 / 임시/백업 파일

MAP2=$BACKUP_DIR/delete_temp_files.list

"${FIND_BASE[@]}" -type f \( \

  -name "*.pyc" -o -name "*.pyo" -o -name "*.swp" -o -name "*.swo" -o \

  -name "*.tmp" -o -name "*.temp" -o -name "*.bak" -o -name "*~" -o \

  -name "~$*.xlsx" -o -name "*.once.log" -o -name "*.old.log" \

\) -print > "$MAP2"



# 2-3) 오래된 로그

MAP3=$BACKUP_DIR/delete_old_logs.list

"${FIND_BASE[@]}" -type f \

  \( -name "*.log" -o -name "*.stdout.log" -o -name "*.stderr.log" -o -name "run_*.log" \) \

  -mtime +$KEEP_DAYS_LOG -print > "$MAP3"



# 2-4) 오래된 대형 압축(최근 2개 제외)

MAP4=$BACKUP_DIR/delete_old_archives.list

# 확장자 대상

ARCH_PAT='(.*\.zip|.*\.7z|.*\.tar|.*\.tar\.gz)$'

# 정렬하여 최근 2개를 제외하고 목록 생성

( ${FIND_BASE[@]} -type f | grep -Ei "$ARCH_PAT" | sort -r | tail -n +3 ) > "$MAP4" || true



# 2-5) 화이트리스트 제거(남겨둘 파일/패턴은 제외)

say "화이트리스트 적용"

WHITELIST_PAT='(settings\.xlsx|company.*\.xlsx|.*config.*\.(ini|yml|yaml|json)$|\.env.*$|.*\.(key|token)$|(^|/)main_send\.py$|.*crawling.*\.py$|.*gd.*\.py$|.*_send\.py$|.*\.(service|timer|sh)$)'

for f in "$MAP1" "$MAP2" "$MAP3" "$MAP4"; do

  if [ -s "$f" ]; then

    grep -Ev "$WHITELIST_PAT" "$f" > "$f.filtered" || true

  else

    : > "$f.filtered"

  fi

done



# === 3. 요약 미리보기 ===

say "삭제 후보 요약 (DRY_RUN=$DRY_RUN)"

for f in "$MAP1.filtered" "$MAP2.filtered" "$MAP3.filtered" "$MAP4.filtered"; do

  kind="$(basename "$f" .filtered)"

  cnt=$(wc -l < "$f" || echo 0)

  say "  - ${kind}: ${cnt}개"

done



say "상위 50개 파일 미리보기:"

cat "$MAP1.filtered" "$MAP2.filtered" "$MAP3.filtered" "$MAP4.filtered" 2>/dev/null | head -50 || true



# === 4. 백업(아카이브) 준비 ===

say "백업 아카이브 생성(삭제 후보만 포함)…"

TO_ARCHIVE_LIST="$BACKUP_DIR/all_delete_targets.list"

cat "$MAP1.filtered" "$MAP2.filtered" "$MAP3.filtered" "$MAP4.filtered" 2>/dev/null | sed 's#^/##' > "$TO_ARCHIVE_LIST"



if [ -s "$TO_ARCHIVE_LIST" ]; then

  ( cd / && tar -czf "$ARCHIVE" -T "$TO_ARCHIVE_LIST" ) || true

  say "백업 아카이브: $ARCHIVE"

else

  say "삭제 후보가 없어 아카이브 생성을 건너뜁니다."

fi



# === 5. 실제 정리 실행(DRY_RUN=0 에서만) ===

if [ "$DRY_RUN" -eq 0 ]; then

  say "삭제 실행 시작…"

  # 디렉터리는 역순 삭제(하위 먼저)

  tac "$MAP1.filtered" 2>/dev/null | xargs -r -I{} bash -lc 'rm -rf "{}"' || true

  # 파일 삭제

  cat "$MAP2.filtered" "$MAP3.filtered" "$MAP4.filtered" 2>/dev/null | xargs -r -I{} bash -lc 'rm -f "{}"' || true

  say "삭제 완료"

else

  say "DRY_RUN 모드이므로 실제 삭제하지 않았습니다. 문제 없으면 DRY_RUN=0 으로 바꿔 재실행하세요."

fi



# === 6. main_send.py 정상화 ===

if [ -f "$PY_FILE" ]; then

  say "main_send.py 백업 -> $BACKUP_DIR/main_send.py.bak"

  cp -a "$PY_FILE" "$BACKUP_DIR/main_send.py.bak"



  say "개행(EOL) 및 인코딩(UTF-8) 표준화"

  # CRLF -> LF

  sed -i 's/\r$//' "$PY_FILE"

  # UTF-8 헤더 보장

  if ! head -n 1 "$PY_FILE" | grep -q "coding: utf-8"; then

    sed -i '1i # -*- coding: utf-8 -*-' "$PY_FILE"

  fi

  # 실행선 언급(없으면 추가)

  if ! head -n 1 "$PY_FILE" | grep -q "^#\!"; then

    sed -i '1i #!/usr/bin/env python3' "$PY_FILE"

  fi



  # 안전 로그 디렉터리 보장

  mkdir -p "$LOG_DIR"



  # 빠른 문법/의존성 기초 점검

  say "파이썬 컴파일 검증(python -m py_compile)…"

  if python3 -m py_compile "$PY_FILE"; then

    say "문법 오류 없음"

  else

    say "경고: 문법 오류가 감지되었습니다. 백업본($BACKUP_DIR/main_send.py.bak)과 비교하세요."

  fi



  # 흔한 문제 포인트 힌트 로그

  say "의심 포인트 그렙:"

  grep -nE "(from\s+dotenv|Alligo|requests|pandas|openpyxl|flock|logging\.|os\.path|sys\.argv)" "$PY_FILE" || true



else

  say "main_send.py가 없습니다: $PY_FILE"

fi



# === 7. 로그 로테이션(선택) 샘플 규칙 안내 파일 생성 ===

cat > "$BASE/logrotate.n_data.sample" <<'ROT'

# /etc/logrotate.d/n_data 로 복사하여 사용하세요(루트 권한).

/home/pi/n_data/logs/*.log {

    weekly

    rotate 8

    missingok

    compress

    delaycompress

    notifempty

    create 0644 pi pi

}

ROT



say "완료. 요약:"

say " - 백업 디렉터리: $BACKUP_DIR"

say " - 아카이브: $ARCHIVE (DRY_RUN이면 비어있을 수 있음)"

say " - 로그 샘플: $BASE/logrotate.n_data.sample"

