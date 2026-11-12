
#!/usr/bin/env bash

set -u



HOST="ebid.lh.or.kr"

CERTDIR="/home/pi/seri_Alarm_Server2/certs"

BUNDLE="${CERTDIR}/${HOST}_bundle.pem"

TMP="${CERTDIR}/_sclient.txt"



echo "==[0] start =="

date



mkdir -p "$CERTDIR"

rm -f "$CERTDIR"/cert_*.pem "$BUNDLE" "$TMP" 2>/dev/null || true



echo "==[1] extract cert chain (to file) =="

openssl s_client -showcerts -servername "$HOST" -connect "$HOST:443" </dev/null >"$TMP" 2>/dev/null || true



# cert 분리

awk '

  /BEGIN CERTIFICATE/ {i++; fn=sprintf("'"$CERTDIR"'/cert_%02d.pem", i)}

  { if (i>0) print > fn }

' "$TMP"



echo "==[1-1] list =="

ls -l "$CERTDIR"/cert_*.pem || true



echo "==[2] build bundle(all certs) =="

for f in "$CERTDIR"/cert_*.pem; do

  cat "$f" >> "$BUNDLE"

done

echo "BUNDLE => $BUNDLE"

grep -n "BEGIN CERTIFICATE" "$BUNDLE" | head -n 20 || true



echo "==[3] curl test(with bundle) =="

curl -I --cacert "$BUNDLE" "https://${HOST}" | sed -n '1,12p' || true



echo "==[4] patch main_crawling.py (force verify) =="

cp -a main_crawling.py "main_crawling.py.bak_$(date +%Y%m%d_%H%M%S)"



python3 - <<PY

import re

from pathlib import Path

bundle = r"$BUNDLE"

p = Path("main_crawling.py")

s = p.read_text(encoding="utf-8", errors="ignore")



def patch_call(m):

    call = m.group(0)

    if "verify=" in call:

        return call

    if "timeout=" in call:

        return call[:-1] + f', verify=r"{bundle}")'

    return call[:-1] + f', verify=r"{bundle}", timeout=30)'



s2 = re.sub(r"requests\.(post|get)\(([^)]*)\)", patch_call, s)

p.write_text(s2, encoding="utf-8")

print("patched:", p)

PY



echo "==[5] patch app/lh_collector.py (subprocess env) =="

python3 - <<PY

from pathlib import Path



HOST = "$HOST"

p = Path("app/lh_collector.py")

s = p.read_text(encoding="utf-8", errors="ignore")



if "import os" not in s:

    s = s.replace("from pathlib import Path", "from pathlib import Path\nimport os")



if "LH_CA_BUNDLE" not in s:

    anchor = "DATA_DIR.mkdir(exist_ok=True)"

    s = s.replace(anchor, anchor + f'\n\nLH_CA_BUNDLE = str((BASE_DIR / "certs" / "{HOST}_bundle.pem").resolve())\n')



# env 주입(이미 들어가 있으면 중복 삽입 안 함)

if "REQUESTS_CA_BUNDLE" not in s:

    s = s.replace(

        'print("[LH] start crawling")',

        'print("[LH] start crawling")\n\n    env = os.environ.copy()\n    env["REQUESTS_CA_BUNDLE"] = LH_CA_BUNDLE\n    env["SSL_CERT_FILE"] = LH_CA_BUNDLE'

    )

if "env=env" not in s:

    s = s.replace("cwd=str(BASE_DIR),", "cwd=str(BASE_DIR),\n        env=env,")



p.write_text(s, encoding="utf-8")

print("patched:", p)

PY



echo "==[6] run main.py test =="

python3 main.py || true



echo

echo "==== DONE (press Enter to close) ===="

read -r

