#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# fix_dedup_no_send_guard.py
#
# 목적:
# - 기존 SEND_DEDUP_GUARD_PATCH가 --no-send 드라이런 결과를 sent로 저장할 가능성을 차단
# - 드라이런/blocked 결과는 send_guard DB에서 중복발송 이력으로 남기지 않도록 정리

import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TARGET = Path("/home/pi/n_data/main_send.py")
BASE = Path(os.getenv("N_DATA_BASE") or "/mnt/vol1/bid/n_data")
DB = BASE / "split/history/send_guard.sqlite3"

if not TARGET.exists():
    print(f"[FATAL] not found: {TARGET}")
    sys.exit(1)

text = TARGET.read_text(encoding="utf-8")

if "SEND_DEDUP_GUARD_PATCH_BEGIN" not in text:
    print("[FATAL] SEND_DEDUP_GUARD_PATCH block not found. 먼저 apply_dedup_guard_patch.py를 적용하세요.")
    sys.exit(1)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_name(f"main_send.py.bak_no_send_guard_fix_{ts}")
shutil.copy2(TARGET, backup)
print(f"[BACKUP] {backup}")

helper = r"""
def _dedup_is_no_send_context():
    # --no-send / dry-run 실행에서는 send_guard 예약/확정을 하지 않는다.
    # 드라이런 결과가 sent=True 형태로 반환되더라도 실제 발송 이력으로 남기지 않기 위함.
    try:
        import sys as _dedup_sys
        if "--no-send" in _dedup_sys.argv:
            return True

        for _name in ("NO_SEND", "DRY_RUN", "no_send", "dry_run"):
            _v = globals().get(_name)
            if isinstance(_v, bool) and _v:
                return True
            if str(_v).strip().lower() in ("1", "true", "y", "yes"):
                return True
    except Exception:
        pass

    return False

"""

if "def _dedup_is_no_send_context()" not in text:
    marker = "# ---------------------------------------------------------------------\n# 발송 직전 atomic guard wrapper"
    if marker not in text:
        print("[FATAL] atomic guard wrapper marker not found")
        shutil.copy2(backup, TARGET)
        sys.exit(1)
    text = text.replace(marker, helper + marker, 1)
    print("[PATCH] inserted _dedup_is_no_send_context()")
else:
    print("[SKIP] _dedup_is_no_send_context() already exists")

# Insert no-send bypass after N_DATA_DISABLE_SEND_GUARD branch in wrapper.
bypass = r"""
        if _dedup_is_no_send_context():
            return _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG(
                phone=phone,
                fields=fields,
                key=key,
                title=title,
                max_retry=max_retry,
            )
"""

wrapper_start = text.find("def send_tb0485_retry_and_log")
wrapper_window = text[wrapper_start:wrapper_start + 3000] if wrapper_start >= 0 else ""

if "if _dedup_is_no_send_context():" not in wrapper_window:
    pattern = re.compile(
        r'(        if _dedup_os\.getenv\("N_DATA_DISABLE_SEND_GUARD", ""\)\.strip\(\)\.lower\(\) in \("1", "y", "yes", "true"\):\n'
        r'            return _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG\(\n'
        r'                phone=phone,\n'
        r'                fields=fields,\n'
        r'                key=key,\n'
        r'                title=title,\n'
        r'                max_retry=max_retry,\n'
        r'            \)\n)'
    )
    text, n = pattern.subn(r"\1" + bypass, text, count=1)
    if n != 1:
        print("[FATAL] no-send bypass insertion failed")
        shutil.copy2(backup, TARGET)
        sys.exit(1)
    print("[PATCH] inserted no-send bypass in send wrapper")
else:
    print("[SKIP] no-send bypass already exists in wrapper")

old = r"""            if _dedup_is_sent_result(res):
                mark_send_guard_sent(bid_key, phone_norm, title, res)
            else:
                release_send_guard_failed(bid_key, phone_norm)

            return res
"""

new = r"""            if isinstance(res, dict) and res.get("blocked") is True:
                # --no-send / 강제차단 / 실제 미발송 결과는 중복발송 이력으로 확정하지 않는다.
                release_send_guard_failed(bid_key, phone_norm)
            elif _dedup_is_sent_result(res):
                mark_send_guard_sent(bid_key, phone_norm, title, res)
            else:
                release_send_guard_failed(bid_key, phone_norm)

            return res
"""

if new not in text:
    if old not in text:
        print("[FATAL] sent-result block not found")
        shutil.copy2(backup, TARGET)
        sys.exit(1)
    text = text.replace(old, new, 1)
    print("[PATCH] blocked result now releases guard")
else:
    print("[SKIP] blocked result guard release already applied")

TARGET.write_text(text, encoding="utf-8")

res = subprocess.run([sys.executable, "-m", "py_compile", str(TARGET)], text=True, capture_output=True)
if res.returncode != 0:
    print("[FATAL] py_compile failed. restoring backup.")
    print(res.stdout)
    print(res.stderr)
    shutil.copy2(backup, TARGET)
    sys.exit(res.returncode)

print("[OK] py_compile passed")

# Clean possible dry-run/blocked records from the guard DB.
deleted = 0
if DB.exists():
    try:
        con = sqlite3.connect(str(DB))
        cur = con.execute("""
            DELETE FROM alimtalk_send_guard
             WHERE status='sent'
               AND (
                    lower(raw) LIKE '%blocked%'
                 OR lower(raw) LIKE '%dry%'
                 OR lower(raw) LIKE '%safe%'
               )
        """)
        deleted = cur.rowcount if cur.rowcount is not None else 0
        con.commit()
        con.close()
        print(f"[CLEAN] deleted possible dry-run guard rows: {deleted}")
    except Exception as e:
        print(f"[WARN] guard DB cleanup skipped: {e}")
else:
    print(f"[CLEAN] guard DB not found yet: {DB}")

print(f"[OK] fixed file : {TARGET}")
print(f"[OK] backup file: {backup}")
