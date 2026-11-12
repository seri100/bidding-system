#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# fix_send_guard_sqlite_lock.py

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TARGET = Path("/home/pi/n_data/main_send.py")

if not TARGET.exists():
    print(f"[FATAL] not found: {TARGET}")
    sys.exit(1)

text = TARGET.read_text(encoding="utf-8")

if "SEND_DEDUP_GUARD_PATCH_BEGIN" not in text:
    print("[FATAL] SEND_DEDUP_GUARD_PATCH block not found. 먼저 apply_dedup_guard_patch.py를 적용하세요.")
    sys.exit(1)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_name(f"main_send.py.bak_sqlite_lock_fix_{ts}")
shutil.copy2(TARGET, backup)
print(f"[BACKUP] {backup}")

new_path_func = """
def _dedup_guard_db_path():
    # SQLite는 NAS/NFS/SMB 공유마운트에서 WAL/lock 문제가 자주 생길 수 있으므로
    # 기본 send_guard DB는 main_send.py가 있는 로컬 경로에 둔다.
    # 필요하면 환경변수로 강제 지정 가능:
    #   N_DATA_SEND_GUARD_DB=/some/path/send_guard.sqlite3
    override = _dedup_os.getenv("N_DATA_SEND_GUARD_DB", "").strip()
    if override:
        return _DedupPath(override)

    try:
        local_base = _DedupPath(__file__).resolve().parent
    except Exception:
        local_base = _DedupPath(_dedup_os.getcwd())

    return local_base / "split/history/send_guard.sqlite3"

""".lstrip()

text, n1 = re.subn(
    r'def _dedup_guard_db_path\(\):\n.*?\n(?=def _send_guard_conn\(\):)',
    new_path_func,
    text,
    count=1,
    flags=re.S,
)

if n1 != 1:
    print("[FATAL] _dedup_guard_db_path() replacement failed")
    shutil.copy2(backup, TARGET)
    sys.exit(1)

print("[PATCH] _dedup_guard_db_path -> local runtime DB by default")

new_conn_func = """
def _send_guard_conn():
    # send_guard DB 연결.
    # - NAS WAL 전환을 하지 않는다.
    # - busy_timeout + 짧은 재시도로 일시적 lock을 흡수한다.
    import time as _dedup_time

    db = _dedup_guard_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)

    last_exc = None

    for attempt in range(1, 13):
        conn = None

        try:
            conn = _dedup_sqlite3.connect(str(db), timeout=60)
            conn.execute("PRAGMA busy_timeout=60000")

            # WAL 전환은 lock을 유발할 수 있어 기본적으로 사용하지 않는다.
            # 정말 WAL이 필요하면 명시적으로만 켠다.
            if _dedup_os.getenv("N_DATA_SEND_GUARD_WAL", "").strip().lower() in ("1", "y", "yes", "true"):
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                except Exception as e:
                    _dedup_log(f"[GUARD][WARN] journal_mode=WAL skipped: {e}")

            conn.execute(
                "CREATE TABLE IF NOT EXISTS alimtalk_send_guard ("
                "send_key TEXT PRIMARY KEY, "
                "bid_key TEXT NOT NULL, "
                "phone TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "title TEXT, "
                "created_ts TEXT NOT NULL, "
                "updated_ts TEXT NOT NULL, "
                "raw TEXT)"
            )
            conn.commit()
            return conn

        except _dedup_sqlite3.OperationalError as e:
            last_exc = e
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                if attempt in (1, 6, 12):
                    _dedup_log(f"[GUARD][WAIT] sqlite locked attempt={attempt}/12 db={db}: {e}")
                _dedup_time.sleep(min(0.5 * attempt, 3.0))
                continue

            raise

    raise last_exc

""".lstrip()

text, n2 = re.subn(
    r'def _send_guard_conn\(\):\n.*?\n(?=def make_send_once_key\()',
    new_conn_func,
    text,
    count=1,
    flags=re.S,
)

if n2 != 1:
    print("[FATAL] _send_guard_conn() replacement failed")
    shutil.copy2(backup, TARGET)
    sys.exit(1)

print("[PATCH] _send_guard_conn -> no WAL by default + retry")

TARGET.write_text(text, encoding="utf-8")

res = subprocess.run([sys.executable, "-m", "py_compile", str(TARGET)], text=True, capture_output=True)
if res.returncode != 0:
    print("[FATAL] py_compile failed. restoring backup.")
    print(res.stdout)
    print(res.stderr)
    shutil.copy2(backup, TARGET)
    sys.exit(res.returncode)

print("[OK] py_compile passed")
print(f"[OK] fixed file : {TARGET}")
print(f"[OK] backup file: {backup}")
print("[INFO] guard DB default path is now /home/pi/n_data/split/history/send_guard.sqlite3")
