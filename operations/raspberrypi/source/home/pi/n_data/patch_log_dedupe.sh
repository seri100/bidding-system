
#!/usr/bin/env bash

set -euo pipefail



FILE="/home/pi/n_data/main_send.py"

BK="/home/pi/n_data/main_send.py.bak_$(date +%Y%m%d_%H%M%S)"



sudo cp -a "$FILE" "$BK"



python3 - <<'PY'

import re

from pathlib import Path



p = Path("/home/pi/n_data/main_send.py")

s = p.read_text(encoding="utf-8", errors="ignore")



# log() 함수 블록 1개를 찾아 교체

pat = re.compile(r"def\s+log\s*\(\s*msg\s*:\s*str\s*\)\s*->\s*None\s*:\s*\n(?:[ \t].*\n)+", re.M)

m = pat.search(s)

if not m:

    raise SystemExit("❌ def log(msg: str) -> None: 블록을 찾지 못했습니다.")



new_block = """def log(msg: str) -> None:

    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    line = f"{ts} {msg}"



    # 1) stdout 출력 (wrapper가 stdout을 로그파일로 리다이렉트 중)

    try:

        print(line, flush=True)

    except Exception:

        pass



    # 2) wrapper로 실행 중이면 파일 write는 하지 않음(중복 방지)

    #    - wrapper 없는 단독 실행(예: 수동 python main_send.py)일 때만 파일에 추가 기록

    try:

        if os.environ.get("MAIN_SEND_LOCKED", "").strip() == "1":

            return

    except Exception:

        return



    try:

        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:

            f.write(line + "\\n")

    except Exception:

        pass



"""



s2 = s[:m.start()] + new_block + s[m.end():]

p.write_text(s2, encoding="utf-8")

print("✅ log() dedupe 패치 완료")

PY



python3 -m py_compile /home/pi/n_data/main_send.py && echo "✅ PY SYNTAX OK"

