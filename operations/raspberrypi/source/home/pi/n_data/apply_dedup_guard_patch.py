#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_send.py SEND 중복방지 한방 패치

적용 내용:
1) R26BK01522966 / R26BK01522966-000 / R26BK01522966 - 000 을 동일 key로 정규화
2) send_history.csv 읽기/쓰기 정규화
3) report/history 비교용 key variant 확장
4) 발송 직전 SQLite 원자 잠금: 공고번호 + 수신번호 단위 1회만 발송
5) 같은 수신번호 표기 차이(REDACTED_PHONE / REDACTED_PRIVATE_VALUE) 정규화
6) 기존 main_send.py 전체는 유지하고, if __name__ == "__main__" 바로 위에 패치 삽입
"""

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TARGET = Path("/home/pi/n_data/main_send.py")

if not TARGET.exists():
    print("[FATAL] /home/pi/n_data/main_send.py 없음")
    sys.exit(1)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_name(f"main_send.py.bak_dedup_guard_{ts}")
shutil.copy2(str(TARGET), str(backup))
print(f"[BACKUP] {backup}")

PATCH = r'''
# === SEND_DEDUP_GUARD_PATCH_BEGIN ===
# -*- coding: utf-8 -*-
#
# SEND_DEDUP_GUARD_PATCH
# 목적:
#   - 같은 공고 + 같은 수신번호 알림톡 중복 발송 방지
#   - R26BK01522966 / R26BK01522966-000 / R26BK01522966 - 000 키 정규화
#   - send_history.csv / report_keys / 발송 직전 guard 일괄 보강
#
# 이 블록은 main_send.py 하단, if __name__ == "__main__": 바로 위에서
# 기존 함수를 override/wrap 한다.

import os as _dedup_os
import csv as _dedup_csv
import re as _dedup_re
import sqlite3 as _dedup_sqlite3
from pathlib import Path as _DedupPath
from datetime import datetime as _DedupDateTime

_DEDUP_BID_KEY_RE = _dedup_re.compile(
    r"(R\d{2}[A-Z]{2}\d{8})(?:\s*[-_]\s*(\d{3}))?",
    _dedup_re.I,
)

_DEDUP_TRAILING_ORD_RE = _dedup_re.compile(
    r"^([A-Z0-9]{5,})(?:[-_](\d{2,3}))$",
    _dedup_re.I,
)


def _dedup_log(msg):
    try:
        if callable(globals().get("log")):
            globals()["log"](msg)
        else:
            print(msg)
    except Exception:
        try:
            print(msg)
        except Exception:
            pass


def _dedup_norm_ord(v, default="000"):
    s = str(v or "").strip()
    s = _dedup_re.sub(r"\D", "", s)
    if not s:
        s = default
    s = _dedup_re.sub(r"\D", "", str(s or "000")) or "000"
    return s[-3:].zfill(3)


def split_bid_key(bid_no="", bid_ord="000"):
    """
    공고번호/차수를 표준형으로 분리한다.

    예:
      R26BK01522966, 000        -> R26BK01522966 / 000
      R26BK01522966-000, 000    -> R26BK01522966 / 000
      R26BK01522966 - 000, 000  -> R26BK01522966 / 000
      조달청 시설 R26BK01522966-000 호 -> R26BK01522966 / 000
    """
    s_no = str(bid_no or "").strip()
    s_ord = str(bid_ord or "").strip() or "000"

    blob = f"{s_no}-{s_ord}".replace("호", " ")
    m = _DEDUP_BID_KEY_RE.search(blob)

    if m:
        no = m.group(1).upper()
        ordv = m.group(2) or s_ord or "000"
        return no, _dedup_norm_ord(ordv)

    compact = s_no.upper().replace(" ", "").replace("호", "")
    m2 = _DEDUP_TRAILING_ORD_RE.match(compact)
    if m2 and (not s_ord or s_ord == "000"):
        no = m2.group(1).upper()
        ordv = m2.group(2)
        return no, _dedup_norm_ord(ordv)

    no = compact
    ordv = _dedup_norm_ord(s_ord)
    return no, ordv


def make_bid_key(bid_no="", bid_ord="000"):
    no, ordv = split_bid_key(bid_no, bid_ord)
    return f"{no}-{ordv}" if no else ""


def _dedup_bid_key_variants(bid_no="", bid_ord="000"):
    """
    기존 코드가 만들 수 있는 key 변형까지 같이 포함한다.
    예: R26BK01522966-000, R26BK01522966-000-000
    """
    variants = set()
    raw_no = str(bid_no or "").strip()
    raw_ord = str(bid_ord or "").strip() or "000"

    no, ordv = split_bid_key(raw_no, raw_ord)
    if not no:
        return variants

    canonical = make_bid_key(no, ordv)
    variants.add(canonical)

    if raw_no:
        variants.add(raw_no)
        variants.add(f"{raw_no}-{_dedup_norm_ord(raw_ord)}")

    variants.add(f"{canonical}-{ordv}")

    return {v for v in variants if v}


def _clean_phone(phone):
    return _dedup_re.sub(r"\D", "", str(phone or ""))


def normalize_receivers(receivers):
    out = []
    seen = set()

    for p in receivers or []:
        d = _clean_phone(p)
        if not d:
            continue
        if d in seen:
            continue
        seen.add(d)
        out.append(d)

    return out


def _dedup_row_bid_key(row):
    if not isinstance(row, dict):
        return ""

    raw = row.get("원문") or {}
    raw_dict = raw if isinstance(raw, dict) else {}

    bid_no = (
        raw_dict.get("bidNtceNo")
        or raw_dict.get("공고번호")
        or row.get("bidNtceNo")
        or row.get("공고번호")
        or row.get("bid_no")
        or ""
    )
    bid_ord = (
        raw_dict.get("bidNtceOrd")
        or raw_dict.get("차수")
        or row.get("bidNtceOrd")
        or row.get("차수")
        or row.get("bid_ord")
        or "000"
    )

    if not bid_no and raw and not isinstance(raw, dict):
        bid_no = str(raw)

    return make_bid_key(bid_no, bid_ord)


def _dedup_normalize_row_bid_fields(row):
    if not isinstance(row, dict):
        return row

    raw = row.get("원문") or {}
    raw_dict = raw if isinstance(raw, dict) else {}

    bid_no = (
        raw_dict.get("bidNtceNo")
        or row.get("bidNtceNo")
        or row.get("공고번호")
        or row.get("bid_no")
        or ""
    )
    bid_ord = (
        raw_dict.get("bidNtceOrd")
        or row.get("bidNtceOrd")
        or row.get("차수")
        or row.get("bid_ord")
        or "000"
    )

    if not bid_no and raw and not isinstance(raw, dict):
        bid_no = str(raw)

    no, ordv = split_bid_key(bid_no, bid_ord)
    if no:
        row["공고번호"] = no
        row["차수"] = ordv
        if isinstance(raw, dict):
            raw["bidNtceNo"] = no
            raw["bidNtceOrd"] = ordv

    return row


def _dedup_guard_db_path():
    base = globals().get("NAS_BASE")
    if not base:
        base = _DedupPath(_dedup_os.getenv("N_DATA_BASE") or "/mnt/vol1/bid/n_data")
    else:
        base = _DedupPath(str(base))
    return base / "split/history/send_guard.sqlite3"


def _send_guard_conn():
    db = _dedup_guard_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = _dedup_sqlite3.connect(str(db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alimtalk_send_guard (
            send_key   TEXT PRIMARY KEY,
            bid_key    TEXT NOT NULL,
            phone      TEXT NOT NULL,
            status     TEXT NOT NULL,
            title      TEXT,
            created_ts TEXT NOT NULL,
            updated_ts TEXT NOT NULL,
            raw        TEXT
        )
    """)
    conn.commit()
    return conn


def make_send_once_key(bid_key, phone):
    return f"{str(bid_key or '').strip()}|{_clean_phone(phone)}"


def reserve_send_once(bid_key, phone, title=""):
    """
    알림톡 API 호출 직전에 원자적으로 예약한다.
    같은 공고 + 같은 수신번호는 최초 1개 실행만 True.
    """
    bid_key = str(bid_key or "").strip()
    phone = _clean_phone(phone)
    send_key = make_send_once_key(bid_key, phone)

    if not bid_key or not phone:
        return False

    now_s = _DedupDateTime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _send_guard_conn()

    try:
        try:
            conn.execute("""
                DELETE FROM alimtalk_send_guard
                 WHERE send_key = ?
                   AND status = 'reserved'
                   AND created_ts < datetime('now', '-2 hours', 'localtime')
            """, (send_key,))
        except Exception:
            pass

        cur = conn.execute("""
            INSERT OR IGNORE INTO alimtalk_send_guard
            (send_key, bid_key, phone, status, title, created_ts, updated_ts, raw)
            VALUES (?, ?, ?, 'reserved', ?, ?, ?, '')
        """, (send_key, bid_key, phone, str(title or "")[:200], now_s, now_s))
        conn.commit()
        return cur.rowcount == 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_send_guard_sent(bid_key, phone, title="", raw=""):
    bid_key = str(bid_key or "").strip()
    phone = _clean_phone(phone)
    send_key = make_send_once_key(bid_key, phone)

    now_s = _DedupDateTime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _send_guard_conn()

    try:
        conn.execute("""
            UPDATE alimtalk_send_guard
               SET status='sent',
                   title=?,
                   updated_ts=?,
                   raw=?
             WHERE send_key=?
        """, (str(title or "")[:200], now_s, str(raw or "")[:500], send_key))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def release_send_guard_failed(bid_key, phone):
    """
    실패한 발송 예약은 지워서 다음 실행 때 재시도 가능하게 둔다.
    성공 건은 sent 상태로 남겨 영구 중복 방지.
    """
    bid_key = str(bid_key or "").strip()
    phone = _clean_phone(phone)
    send_key = make_send_once_key(bid_key, phone)

    conn = _send_guard_conn()

    try:
        conn.execute(
            "DELETE FROM alimtalk_send_guard WHERE send_key=? AND status='reserved'",
            (send_key,)
        )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _dedup_is_sent_result(res):
    if res is True:
        return True

    if isinstance(res, dict):
        if res.get("sent") is True:
            return True
        if res.get("ok") is True:
            return True
        if str(res.get("ok", "")).strip().lower() in ("true", "1", "y", "yes"):
            return True
        if str(res.get("sent_ok", "")).strip() not in ("", "0", "0.0", "None", "none"):
            return True

        code = str(res.get("code") or res.get("result_code") or "").strip()
        if code in ("0", "1"):
            return True

        raw = res.get("raw")
        if isinstance(raw, dict):
            if str(raw.get("code") or raw.get("result_code") or "").strip() in ("0", "1"):
                return True
            info = raw.get("info")
            if isinstance(info, dict):
                scnt = str(info.get("scnt") or info.get("success_cnt") or "").strip()
                if scnt and scnt not in ("0", "0.0", "None", "none"):
                    return True

    if isinstance(res, str) and res.strip().upper() in ("OK", "SUCCESS"):
        return True

    return False


# ---------------------------------------------------------------------
# history override
# ---------------------------------------------------------------------

def load_send_history(keep_days: int = 30):
    """
    send_history.csv를 정규화해서 읽는다.
    반환 keys에는 canonical key와 기존 코드가 만들 수 있는 변형 key를 모두 넣는다.
    """
    history_file = globals().get("HISTORY_FILE")
    if not history_file:
        history_file = _dedup_guard_db_path().parent / "send_history.csv"
    history_file = _DedupPath(str(history_file))
    history_file.parent.mkdir(parents=True, exist_ok=True)

    if not history_file.exists():
        return set(), []

    rows = []

    try:
        with open(str(history_file), newline="", encoding="utf-8") as f:
            reader = _dedup_csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as e:
        _dedup_log(f"[HISTORY][ERR] load_send_history 실패: {e}")
        return set(), []

    today = _DedupDateTime.now().date()
    filtered = []

    for r in rows:
        s = r.get("sent_date") or r.get("sent_dt") or ""
        keep = True

        if s:
            try:
                d = _DedupDateTime.strptime(str(s).strip(), "%Y%m%d").date()
                keep = (today - d).days <= keep_days
            except Exception:
                keep = True

        if keep:
            bid_no = str(r.get("bid_no") or "").strip()
            bid_ord = str(r.get("bid_ord") or "000").strip() or "000"
            no, ordv = split_bid_key(bid_no, bid_ord)

            if no:
                rr = dict(r)
                rr["bid_no"] = no
                rr["bid_ord"] = ordv
                filtered.append(rr)
            else:
                filtered.append(r)

    keys = set()
    for r in filtered:
        bid_no = str(r.get("bid_no") or "").strip()
        bid_ord = str(r.get("bid_ord") or "000").strip() or "000"
        keys.update(_dedup_bid_key_variants(bid_no, bid_ord))

    return keys, filtered


def save_send_history(rows: list):
    """
    send_history.csv 저장 시에도 공고번호/차수 정규화.
    동시 실행 lost-update 방지용 lock + tmp replace 유지.
    """
    history_file = globals().get("HISTORY_FILE")
    if not history_file:
        history_file = _dedup_guard_db_path().parent / "send_history.csv"
    history_file = _DedupPath(str(history_file))
    history_file.parent.mkdir(parents=True, exist_ok=True)

    tmp = history_file.with_suffix(".tmp")
    lock_path = history_file.with_suffix(history_file.suffix + ".lock")
    fieldnames = ["bid_no", "bid_ord", "sent_date", "sent_ts"]

    lock_fd = None

    try:
        try:
            lock_fd = _dedup_os.open(str(lock_path), _dedup_os.O_CREAT | _dedup_os.O_RDWR, 0o644)
            fcntl_mod = globals().get("fcntl")
            if fcntl_mod is not None:
                fcntl_mod.lockf(lock_fd, fcntl_mod.LOCK_EX)
        except Exception:
            lock_fd = None

        merged = []
        keys = set()

        def _add_row(r):
            if not isinstance(r, dict):
                return

            bid_no = str(r.get("bid_no") or r.get("공고번호") or "").strip()
            bid_ord = str(r.get("bid_ord") or r.get("차수") or "000").strip() or "000"

            no, ordv = split_bid_key(bid_no, bid_ord)
            if not no:
                return

            k = make_bid_key(no, ordv)
            if k in keys:
                return

            keys.add(k)
            merged.append({
                "bid_no": no,
                "bid_ord": ordv,
                "sent_date": str(r.get("sent_date") or ""),
                "sent_ts": str(r.get("sent_ts") or ""),
            })

        if history_file.exists():
            try:
                with open(str(history_file), newline="", encoding="utf-8") as f:
                    reader = _dedup_csv.DictReader(f)
                    for r in reader:
                        _add_row(r)
            except Exception:
                pass

        for r in (rows or []):
            _add_row(r)

        with open(str(tmp), "w", newline="", encoding="utf-8") as f:
            writer = _dedup_csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in merged:
                writer.writerow(r)

        tmp.replace(history_file)
        _dedup_log(f"[HISTORY] save_send_history OK -> {history_file} (rows={len(merged)})")

    except Exception as e:
        _dedup_log(f"[HISTORY][ERR] save_send_history 실패: {e}")

    finally:
        if lock_fd is not None:
            try:
                fcntl_mod = globals().get("fcntl")
                if fcntl_mod is not None:
                    fcntl_mod.lockf(lock_fd, fcntl_mod.LOCK_UN)
            except Exception:
                pass
            try:
                _dedup_os.close(lock_fd)
            except Exception:
                pass


# ---------------------------------------------------------------------
# 기존 report key loader를 감싸서 key variant 확장
# ---------------------------------------------------------------------

try:
    _DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS
except NameError:
    _DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS = globals().get("load_existing_report_keys")


def load_existing_report_keys(*args, **kwargs):
    keys = set()

    try:
        if callable(_DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS):
            original_keys = _DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS(*args, **kwargs) or set()
            for k in original_keys:
                keys.update(_dedup_bid_key_variants(k, "000"))
    except Exception as e:
        _dedup_log(f"[REPORT][WARN] original load_existing_report_keys 실패: {e}")

    return keys


# ---------------------------------------------------------------------
# bid dedupe override
# ---------------------------------------------------------------------

def _dedup_rows_by_bid(rows):
    seen = set()
    out = []

    for row in rows or []:
        try:
            _dedup_normalize_row_bid_fields(row)
            k = _dedup_row_bid_key(row)

            if not k:
                out.append(row)
                continue

            if k in seen:
                continue

            seen.add(k)
            out.append(row)
        except Exception:
            out.append(row)

    return out


def dedup_by_bid(rows):
    return _dedup_rows_by_bid(rows)


def dedupe_by_bid(rows):
    return _dedup_rows_by_bid(rows)


# ---------------------------------------------------------------------
# TB0485 fields 정규화 wrapper
# ---------------------------------------------------------------------

try:
    _DEDUP_ORIG_BUILD_TB0485_FIELDS
except NameError:
    _DEDUP_ORIG_BUILD_TB0485_FIELDS = globals().get("build_tb0485_fields")


if callable(_DEDUP_ORIG_BUILD_TB0485_FIELDS):
    def build_tb0485_fields(row: dict) -> dict:
        fields = _DEDUP_ORIG_BUILD_TB0485_FIELDS(row)

        if not isinstance(fields, dict):
            fields = {}

        raw = row.get("원문") or {} if isinstance(row, dict) else {}
        raw_dict = raw if isinstance(raw, dict) else {}

        bid_no = (
            fields.get("bid_no")
            or raw_dict.get("bidNtceNo")
            or (row.get("공고번호") if isinstance(row, dict) else "")
            or ""
        )
        bid_ord = (
            fields.get("bid_ord")
            or raw_dict.get("bidNtceOrd")
            or (row.get("차수") if isinstance(row, dict) else "")
            or "000"
        )

        no, ordv = split_bid_key(bid_no, bid_ord)

        if no:
            fields["bid_no"] = no
            fields["bid_ord"] = ordv

            try:
                if callable(globals().get("build_detail_url")):
                    detail_url = str(fields.get("detail_url") or "")
                    if (not detail_url) or ("-000-000" in detail_url):
                        fields["detail_url"] = globals()["build_detail_url"](no, ordv)
            except Exception:
                pass

        return fields


# ---------------------------------------------------------------------
# 발송 직전 atomic guard wrapper
# ---------------------------------------------------------------------

try:
    _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG
except NameError:
    _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG = globals().get("send_tb0485_retry_and_log")


if callable(_DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG):
    def send_tb0485_retry_and_log(phone: str, fields: dict, key: str, title: str, max_retry: int = 3) -> dict:
        """
        기존 send_tb0485_retry_and_log 호출을 감싸서
        알림톡 API 호출 전에 공고번호+수신번호 단위로 SQLite 선점한다.
        """
        if _dedup_os.getenv("N_DATA_DISABLE_SEND_GUARD", "").strip().lower() in ("1", "y", "yes", "true"):
            return _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG(
                phone=phone,
                fields=fields,
                key=key,
                title=title,
                max_retry=max_retry,
            )

        if not isinstance(fields, dict):
            fields = {}

        bid_no = fields.get("bid_no") or key or ""
        bid_ord = fields.get("bid_ord") or "000"

        no, ordv = split_bid_key(bid_no, bid_ord)
        bid_key = make_bid_key(no, ordv)

        if no:
            fields["bid_no"] = no
            fields["bid_ord"] = ordv

        phone_norm = _clean_phone(phone)

        if not bid_key or not phone_norm:
            _dedup_log(f"[SEND][SKIP][GUARD-EMPTY] key={bid_key!r} phone={phone!r} title={title}")
            return {
                "sent": False,
                "blocked": True,
                "guard_empty": True,
                "key": bid_key,
                "phone": phone_norm,
            }

        if not reserve_send_once(bid_key, phone_norm, title):
            _dedup_log(f"[SEND][SKIP][GUARD-DUP] {make_send_once_key(bid_key, phone_norm)} / {title}")
            return {
                "sent": False,
                "blocked": True,
                "guard_dup": True,
                "key": bid_key,
                "phone": phone_norm,
            }

        try:
            res = _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG(
                phone=phone_norm,
                fields=fields,
                key=bid_key,
                title=title,
                max_retry=max_retry,
            )

            if _dedup_is_sent_result(res):
                mark_send_guard_sent(bid_key, phone_norm, title, res)
            else:
                release_send_guard_failed(bid_key, phone_norm)

            return res

        except Exception:
            release_send_guard_failed(bid_key, phone_norm)
            raise


_dedup_log("[PATCH] SEND_DEDUP_GUARD_PATCH loaded: canonical bid key + sqlite send guard")
# === SEND_DEDUP_GUARD_PATCH_END ===
'''

text = TARGET.read_text(encoding="utf-8")

# 기존 같은 패치가 있으면 제거 후 재삽입
text = re.sub(
    r"\n?# === SEND_DEDUP_GUARD_PATCH_BEGIN ===.*?# === SEND_DEDUP_GUARD_PATCH_END ===\n?",
    "\n",
    text,
    flags=re.S,
)

m = re.search(r'(?m)^if\s+__name__\s*==\s*[\'\"]__main__[\'\"]\s*:', text)

if m:
    text = text[:m.start()] + "\n\n" + PATCH + "\n\n" + text[m.start():]
else:
    text = text.rstrip() + "\n\n" + PATCH + "\n"

TARGET.write_text(text, encoding="utf-8")
print("[PATCH] inserted SEND_DEDUP_GUARD_PATCH")

res = subprocess.run([sys.executable, "-m", "py_compile", str(TARGET)], text=True, capture_output=True)

if res.returncode != 0:
    print("[FATAL] py_compile 실패. 백업으로 복구합니다.")
    print(res.stdout)
    print(res.stderr)
    shutil.copy2(str(backup), str(TARGET))
    sys.exit(res.returncode)

print("[OK] py_compile 통과")
print(f"[OK] patched file: {TARGET}")
print(f"[OK] backup file : {backup}")
