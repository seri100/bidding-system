
#!/usr/bin/env bash

set -euo pipefail



F="/home/pi/n_data/run_main_send.sh"

MARK="keep only last 20 holder lines (prevent lock file from growing forever)"



if [ ! -f "$F" ]; then

  echo "❌ 파일 없음: $F"

  exit 1

fi



# 이미 패치되어 있으면 종료

if grep -q "$MARK" "$F"; then

  echo "✅ 이미 패치되어 있음 (skip)"

  exit 0

fi



# 백업

cp -a "$F" "${F}.bak_$(date +%Y%m%d_%H%M%S)"



python3 - <<'PY'

from pathlib import Path

import re, sys



f = Path("/home/pi/n_data/run_main_send.sh")

text = f.read_text(encoding="utf-8", errors="ignore").splitlines(True)



marker = "keep only last 20 holder lines (prevent lock file from growing forever)"



# holder echo 라인 찾기 (너가 현재 run_main_send.sh에 넣어둔 '>> "$LOCK_FILE"' 라인)

pat = re.compile(r'^\s*echo\s+"pid=.*cmd=/usr/bin/python3 -u /home/pi/n_data/main_send\.py"\s*>>\s*"\$LOCK_FILE"\s*$')



out = []

inserted = False



for line in text:

    out.append(line)

    if (not inserted) and pat.search(line):

        out.append("\n")

        out.append(f"  # {marker}\n")

        out.append('  tail -n 20 "$LOCK_FILE" > "${LOCK_FILE}.tmp" 2>/dev/null && mv "${LOCK_FILE}.tmp" "$LOCK_FILE" || true\n')

        out.append("\n")

        inserted = True



if not inserted:

    print("❌ 패치 실패: 대상 holder echo 라인을 못 찾았습니다.", file=sys.stderr)

    print("   run_main_send.sh 안의 holder echo(>> \"$LOCK_FILE\") 줄을 먼저 확인하세요.", file=sys.stderr)

    sys.exit(1)



f.write_text("".join(out), encoding="utf-8")

print("✅ holder tail 삽입 완료")

PY



chmod +x "$F"

echo "✅ DONE: $F"

