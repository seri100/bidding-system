
#!/usr/bin/env bash

set -euo pipefail



F="/home/pi/n_data/main_send.py"



# 백업

cp -a "$F" "${F}.bak_$(date +%Y%m%d_%H%M%S)"



python3 - <<'PY'

from pathlib import Path



path = Path("/home/pi/n_data/main_send.py")

lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(True)



# 1) def _read_lock_holder 라인 찾기 (타입힌트 유무/공백 무관)

start = None

for i, ln in enumerate(lines):

    if ln.lstrip().startswith("def _read_lock_holder"):

        start = i

        break



if start is None:

    # 디버그용 힌트 출력

    cand = [ln for ln in lines if "read_lock_holder" in ln]

    print("❌ def _read_lock_holder 를 찾지 못했습니다.")

    if cand:

        print("   (참고) read_lock_holder 포함 라인:")

        for c in cand[:10]:

            print("   ", c.rstrip())

    raise SystemExit(1)



# 함수 들여쓰기(선행 공백) 확보

indent = lines[start].split("def")[0]  # 'def' 앞 공백



# 2) 함수 끝 찾기: 같은 indent에서 'def '가 다시 나오면 종료

end = start + 1

while end < len(lines):

    ln = lines[end]

    if ln.startswith(indent + "def ") and end != start:

        break

    end += 1



# 3) 교체할 함수 본문(항상 마지막 줄만 반환)

new_func = [

    f"{indent}def _read_lock_holder(path):\n",

    f"{indent}    try:\n",

    f"{indent}        txt = open(path, 'r', encoding='utf-8', errors='ignore').read()\n",

    f"{indent}        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]\n",

    f"{indent}        return lines[-1] if lines else ''\n",

    f"{indent}    except Exception:\n",

    f"{indent}        return ''\n",

    "\n",

]



out = lines[:start] + new_func + lines[end:]

path.write_text("".join(out), encoding="utf-8")



print("✅ patched: _read_lock_holder -> last line only")

PY



python3 -m py_compile "$F" >/dev/null

echo "✅ PY SYNTAX OK"

