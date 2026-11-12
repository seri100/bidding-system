
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



# def log(...) 블록을 찾아서 통째로 교체 (가장 먼저 나오는 log 함수 1개만)

pat = re.compile(r"def\s+log\s*\(\s*msg\s*:\s*str\s*\)\s*->\s*None\s*:\s*\n(?:[ \t].*\n)+", re.M)



m = pat.search(s)

if not m:

    raise SystemExit("❌ def log(msg: str) -> None: 블록을 찾지 못했습니다.")



new_block = """def log(msg: str) -> None:

    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    line = f"{ts} {msg}"



    # stdout이 깨져도 죽지 않게

    try:

        print(line, flush=True)

    except Exception:

        pass



    try:

        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:

            f.write(line + "\\n")

    except Exception:

        pass



"""



s2 = s[:m.start()] + new_block + s[m.end():]

p.write_text(s2, encoding="utf-8")



print("✅ log() 함수 교체 완료")

PY



python3 -m py_compile /home/pi/n_data/main_send.py && echo "✅ PY SYNTAX OK"

