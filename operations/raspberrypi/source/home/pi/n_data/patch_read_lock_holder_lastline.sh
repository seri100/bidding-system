
#!/usr/bin/env bash

set -euo pipefail



F="/home/pi/n_data/main_send.py"

cp -a "$F" "${F}.bak_$(date +%Y%m%d_%H%M%S)"



python3 - <<'PY'

import io, re



path = "/home/pi/n_data/main_send.py"

with open(path, "r", encoding="utf-8") as f:

    s = f.read()



# _read_lock_holder() 함수 본문을 "마지막 줄만" 반환하도록 교체

pattern = r"def _read_lock_holder\(path: str\) -> str:\n(?:[ \t].*\n)+?\n"

m = re.search(pattern, s)

if not m:

    raise SystemExit("❌ _read_lock_holder 함수 블록을 찾지 못했습니다.")



new = """def _read_lock_holder(path: str) -> str:

    try:

        txt = open(path, "r", encoding="utf-8", errors="ignore").read()

        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]

        return lines[-1] if lines else ""

    except Exception:

        return ""

\n

"""

s2 = s[:m.start()] + new + s[m.end():]



with open(path, "w", encoding="utf-8") as f:

    f.write(s2)



print("✅ patched: _read_lock_holder -> last line only")

PY



python3 -m py_compile "$F" >/dev/null

echo "✅ PY SYNTAX OK"

