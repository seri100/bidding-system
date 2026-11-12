# -*- coding: utf-8 -*-

"""
main_send.py

- Fetch bid notices from data.go.kr (construction work, several industry codes)
- Save result to Excel under /mnt/vol1/n_data
- Insert raw data into kakao.ntcedata (if needed in future)
- Send Kakao AlimTalk via local alligo.py (Alligo class) with de-duplication
"""

import os
import sys
import json
import time
import math
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
from pathlib import Path
from typing import List

import requests
import pandas as pd
import pymysql

# local alligo module (in /home/pi/n_data/alligo.py)
try:
    from alligo import Alligo
except ImportError:
    Alligo = None

# =====================================================
# Load environment file (/etc/seri-main-send.env -> os.environ)
# =====================================================

ENV_FILE = "/etc/seri-main-send.env"


def load_env_file(path: str = ENV_FILE) -> None:
    """Load simple KEY=VALUE pairs into os.environ (only if not already set)."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and (k not in os.environ):
                    os.environ[k] = v
    except Exception:
        # do not crash even if env file has issues
        pass


load_env_file()

# =====================================================
# DB config (MariaDB kakao)
# =====================================================

DB_CONFIG = {
    "host": "REDACTED_PRIVATE_VALUE",
    "user": 'REDACTED_PRIVATE_VALUE',
    "password": 'REDACTED_PRIVATE_VALUE',
    "db": "kakao",
    "charset": "utf8",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def get_db_conn():
    """Return a new DB connection for kakao DB."""
    return pymysql.connect(**DB_CONFIG)


def _db_conn():
    """Alias for DB connection (for ntcedata / sendlog)."""
    return get_db_conn()


def recv_upsert_db(conn, bid_no: str, bid_ord: str, receivers: List[str]):
    """
    Upsert record into kakao.recvdata

    PK: (bidNtceCode, bidNtceOrd)
    recvPhone : first receiver (main)
    receivers : CSV string of all receivers
    sent_at   : NOW()
    """
    bid_no = str(bid_no).strip()
    bid_ord = str(bid_ord).strip()

    main_phone = receivers[0] if receivers else ""
    recv_str = ",".join([x for x in receivers if x])

    sql = """
    INSERT INTO recvdata
        (bidNtceCode, bidNtceOrd, recvPhone, sent_at, receivers)
    VALUES
        (%s, %s, %s, NOW(), %s)
    ON DUPLICATE KEY UPDATE
        recvPhone = VALUES(recvPhone),
        sent_at   = VALUES(sent_at),
        receivers = VALUES(receivers)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (bid_no, bid_ord, main_phone, recv_str))


def ensure_tables():
    """
    Ensure kakao.ntcedata and kakao.sendlog tables exist.
    If they already exist, nothing happens.
    """
    sql1 = """
    CREATE TABLE IF NOT EXISTS ntcedata (
      bid_no      varchar(40) NOT NULL,
      bid_ord     varchar(8)  NOT NULL DEFAULT '0',
      ind         varchar(10) DEFAULT NULL,
      ind_nm      varchar(50) DEFAULT NULL,
      title       varchar(255) DEFAULT NULL,
      region_text text,
      raw_json    json DEFAULT NULL,
      created_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (bid_no, bid_ord)
    ) CHARSET=utf8mb4;
    """

    sql2 = """
    CREATE TABLE IF NOT EXISTS sendlog (
      bid_no   varchar(40) NOT NULL,
      bid_ord  varchar(8)  NOT NULL DEFAULT '0',
      receiver varchar(20) NOT NULL,
      tpl      varchar(32) NOT NULL DEFAULT 'TB_0485',
      sent_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (bid_no, bid_ord, receiver, tpl)
    ) CHARSET=utf8mb4;
    """

    cn = _db_conn()
    try:
        with cn.cursor() as c:
            c.execute(sql1)
            c.execute(sql2)
    finally:
        cn.close()


def already_sent(bid_no: str, bid_ord: str, receiver: str, tpl: str) -> bool:
    """Check if this (bid_no, bid_ord, receiver, tpl) is already in sendlog."""
    cn = _db_conn()
    try:
        with cn.cursor() as c:
            sql = """
            SELECT 1
              FROM sendlog
             WHERE bid_no=%s
               AND bid_ord=%s
               AND receiver=%s
               AND tpl=%s
             LIMIT 1
            """
            c.execute(sql, (bid_no, bid_ord, receiver, tpl))
            row = c.fetchone()
            return bool(row)
    finally:
        cn.close()


def mark_sent(bid_no: str, bid_ord: str, receiver: str, tpl: str) -> None:
    """Insert a record into sendlog, ignoring duplicates."""
    cn = _db_conn()
    try:
        with cn.cursor() as c:
            sql = """
            INSERT IGNORE INTO sendlog (bid_no, bid_ord, receiver, tpl)
            VALUES (%s, %s, %s, %s)
            """
            c.execute(sql, (bid_no, bid_ord, receiver, tpl))
    finally:
        cn.close()


# =====================================================
# API / Excel / basic constants
# =====================================================

API_BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"
KEY_PATH = "/home/pi/n_data/bid_api_key.txt"

# Industry codes
TARGET_INDS = [
    "6202",  # mechanical facility
    "0040",  # firefighting
    "0037",  # electric
    "0038",  # firefighting (mechanical)
    "0039",  # firefighting (electric)
]

OUTDIR = Path("/mnt/vol1/n_data")
OUTDIR.mkdir(parents=True, exist_ok=True)

# Default receivers (CSV list)
RECEIVERS = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

# Template and sender for AlimTalk
TEMPLATE_CODE = os.getenv("ALLIGO_TPL_CODE", "TB_0485")
SENDER_NUM = "REDACTED_PRIVATE_VALUE"


# =====================================================
# Utility
# =====================================================

def _norm(x):
    """Normalize any value to a stripped string."""
    if isinstance(x, list):
        return " ".join(_norm(v) for v in x)
    if isinstance(x, dict):
        return " ".join(_norm(v) for v in x.values())
    if x is None:
        return ""
    return str(x).strip()


def log(msg: str) -> None:
    """Simple timestamped logger."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_key():
    """
    Load API service key.

    Priority:
    1) ENV SERVICE_KEY (decoded if URL-encoded)
    2) KEY_PATH file
    """
    env_key = os.getenv("SERVICE_KEY")
    if env_key:
        # If value looks URL-encoded, decode; both forms usually work,
        # but we prefer raw.
        if "%" in env_key:
            raw = unquote(env_key)
        else:
            raw = env_key.strip()
    else:
        raw = Path(KEY_PATH).read_text(encoding="utf-8").strip()

    return raw, quote(raw, safe="")


def clamp_len(s: str, n: int = 80) -> str:
    """Clamp string length to n, with ellipsis."""
    s = _norm(s)
    return s if len(s) <= n else s[: n - 1] + "&"


# =====================================================
# Fetch from API
# =====================================================

def fetch_ind(ind: str, bgn_dt: str, end_dt: str, retries: int = 3, timeout: int = 15):
    """
    Fetch bid list for a single industry code.

    Returns list of row dicts ready for filtering.
    """
    raw_key, _ = load_key()

    params = {
        "serviceKey": raw_key,
        "type": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "inqryDiv": 1,
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
        "indstrytyCd": ind,
    }

    tries = 0

    while True:
        tries += 1
        try:
            resp = requests.get(API_BASE, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()

            response = data.get("response") if isinstance(data, dict) else {}
            body = (response or {}).get("body") if isinstance(response, dict) else {}
            items = (body or {}).get("items")

            if items is None:
                items = []
            if isinstance(items, dict):
                src_rows = [items]
            elif isinstance(items, list):
                src_rows = items
            else:
                src_rows = []

            rows = []
            for it in src_rows:
                if not isinstance(it, dict):
                    continue

                region_join = _norm(it.get("prtcptLmtRgnNm")) + _norm(
                    it.get("dmndInsttLocplcNm")
                )

                row = {
                    "��ŅT�": ind,
                    "���8": _norm(it.get("bidNtceNo")),
                    "(": _norm(it.get("bidNtceOrd")),
                    "���": _norm(it.get("bidNtceNm")),
                    "�0�|�": _norm(it.get("bidClseDt")),
                    "���	��": _norm(it.get("prtcptLmtRgnNm")),
                    "���": _norm(it.get("dmndInsttLocplcNm")),
                    "�8": it,
                    "_region_concat": region_join,
                }
                rows.append(row)

            print(f"[HTTP] {API_BASE} ind={ind} count={len(rows)}")
            return rows

        except Exception as e:
            if tries >= retries:
                log(f"[ERR] fetch ind={ind} failed: {e}")
                return []
            time.sleep(1.2 * tries)


# =====================================================
# Filter rows (industry only)
# =====================================================

def filter_rows(rows):
    """
    Filter rows by industry codes only.

    Future: region filter can be added here.
    """
    filtered = []

    for r in rows:
        ind = _norm(r.get("��ŅT�"))
        if not ind:
            continue
        if ind in TARGET_INDS:
            filtered.append(r)

    print(f"[FILTER] filtered rows = {len(filtered)} (inds={','.join(TARGET_INDS)})")
    return filtered


# =====================================================
# Save Excel
# =====================================================

def save_excel(rows):
    """Save filtered rows to an Excel file and return file path string."""
    if not rows:
        return None

    now = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUTDIR / f"�0��_{now}.xlsx"

    def normalize_row(row):
        base = {
            "��ŅT�": row.get("��ŅT�", ""),
            "���8": row.get("���8", ""),
            "(": row.get("(", ""),
            "���": row.get("���", ""),
            "�0�|�": row.get("�0�|�", ""),
            "���	��": row.get("���	��", ""),
            "���": row.get("���", ""),
        }
        base["�8"] = json.dumps(row.get("�8", {}), ensure_ascii=False)
        return base

    df = pd.DataFrame([normalize_row(r) for r in rows])
    df.to_excel(path, index=False)
    log(f"[SAVE] {path}")
    return str(path)


# =====================================================
# Backup old Excel files
# =====================================================

def backup_old_excels(base_dir: Path = OUTDIR, keep_days: int = 1):
    """
    Move *.xlsx older than keep_days to backup/YYYYMMDD/.
    """
    try:
        today = datetime.now().date()
        cutoff = today - timedelta(days=keep_days)

        backup_root = base_dir / "backup"
        backup_root.mkdir(parents=True, exist_ok=True)

        for f in base_dir.glob("*.xlsx"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
            if mtime <= cutoff:
                dst_dir = backup_root / mtime.strftime("%Y%m%d")
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst = dst_dir / f.name
                log(f"[BACKUP] move {f} -> {dst}")
                f.replace(dst)
    except Exception as e:
        log(f"[WARN] backup_old_excels failed: {e}")


# =====================================================
# Aligo / AlimTalk
# =====================================================

def _alligo_ready() -> bool:
    """
    Check if we can send via Alligo.

    - Respects KAKAO_DRY_RUN / KAKAO_TEST (if "1" -> skip send)
    - Requires local Alligo module.
    """
    if os.getenv("KAKAO_DRY_RUN", "0") == "1" or os.getenv("KAKAO_TEST", "0") == "1":
        log("[SEND] DRY-RUN / TEST mode -> skip actual send")
        return False

    if Alligo is None:
        log("[SEND] Alligo module not found -> skip send")
        return False

    return True


def _mk_message(row):
    """
    TB_0485 템플릿 형식에 맞춘 메시지 생성

    [세리공영]

    공고명 : #{bidNtceNm}
    입찰마감일시 :  #{bidClseDt}
    공동도급지역 : #{jntcontrctDutyRgnNm1}
    공동도급비율 : #{rgnDutyJntcontrctRt}
    추정금액 : #{presmptPrce}
    공고번호 : #{bidNtceNo} - #{bidNtceOrd}
    """

    src = row.get("원문") or {}

    bid_no  = _norm(src.get("bidNtceNo")  or row.get("공고번호"))
    bid_ord = _norm(src.get("bidNtceOrd") or row.get("차수"))
    nm      = _norm(src.get("bidNtceNm")  or row.get("공고명"))
    clse    = _norm(src.get("bidClseDt")  or row.get("입찰마감일시"))
    jnt_reg = _norm(src.get("jntcontrctDutyRgnNm1") or row.get("공동도급지역"))
    jnt_rt  = _norm(src.get("rgnDutyJntcontrctRt") or "")
    presm   = _norm(src.get("presmptPrce") or "")

    lines = [
        "[세리공영]",
        "",
        f"공고명 : {nm}",
        f"입찰마감일시 :  {clse}",
        f"공동도급지역 : {jnt_reg}",
        f"공동도급비율 : {jnt_rt}",
        f"추정금액 : {presm}",
        f"공고번호 : {bid_no} - {bid_ord}",
    ]
    return "\n".join(lines)


# =====================================================
# Send AlimTalk + recvdata upsert
# =====================================================

def send_alk(rows, receivers=None):
    """
    Send AlimTalk using local alligo.Alligo class.

    - rows: filtered bid list
    - receivers: if None, use default RECEIVERS
    - uses sendlog for de-dup
    - upserts kakao.recvdata
    """
    base_receivers = receivers or RECEIVERS
    if not base_receivers:
        log("[ALIMTALK] no receivers configured")
        return 0

    # For now, send only to the first number
    send_targets = [base_receivers[0]]

    if not rows:
        log("[ALIMTALK] no rows to send")
        return 0

    if not _alligo_ready():
        log(f"[ALIMTALK] sent=0/{len(rows)} (env/module not ready)")
        return 0

    # Ensure tables
    ensure_tables()

    # Instantiate Alligo (from local alligo.py)
    # Credentials and URLs are embedded in that class file.
    a = Alligo()

    sent_cnt = 0
    conn = get_db_conn()

    try:
        for r in rows:
            bid_no = str(
                r.get("���8") or r.get("bidNtceNo") or ""
            ).strip()
            bid_ord = str(
                r.get("(") or r.get("bidNtceOrd") or ""
            ).strip()

            if not bid_no:
                print(f"[SEND][SKIP] empty bid_no row: {r}")
                continue

            # Upsert recvdata
            try:
                recv_upsert_db(conn, bid_no, bid_ord, send_targets)
            except Exception as e:
                print(f"[RECVDB][ERR] {bid_no}/{bid_ord}: {e}")

            msg_head = "[8��] �0 L�"
            msg_body = _mk_message(r)

            for ph in send_targets:
                if already_sent(bid_no, bid_ord, ph, TEMPLATE_CODE):
                    print(f"[DEDUP] skip already sent {bid_no}/{bid_ord} -> {ph}")
                    continue

                try:
                    # sendTalk(tpl_code, sender, msgHead, message, receiverList)
                    resp = a.sendTalk(
                        TEMPLATE_CODE,
                        SENDER_NUM,
                        msg_head,
                        msg_body,
                        [ph],
                    )

                    code = None
                    msg_text = None
                    if isinstance(resp, dict):
                        code = resp.get("code")
                        msg_text = resp.get("message")

                    if code != 0:
                        print(
                            f"[SEND][FAIL-LOGIC] {bid_no}/{bid_ord} -> {ph}: "
                            f"code={code}, msg={msg_text}"
                        )
                        continue

                    mark_sent(bid_no, bid_ord, ph, TEMPLATE_CODE)
                    sent_cnt += 1
                    print(f"[SEND][OK] {bid_no}/{bid_ord} -> {ph}")

                except Exception as e:
                    print(f"[SEND][ERR] {bid_no}/{bid_ord} -> {ph}: {e}")

    finally:
        conn.close()

    log(f"[ALIMTALK] sent={sent_cnt}/{len(rows)}")
    return sent_cnt


# =====================================================
# main()
# =====================================================

def main():
    # Backup old Excel files
    backup_old_excels(OUTDIR, keep_days=1)

    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1, help="days to look back")
    p.add_argument("--ind", action="append", help="industry code (repeatable)")
    p.add_argument("--no-send", action="store_true", help="skip AlimTalk sending")
    args = p.parse_args()

    days = max(1, args.days or 1)
    end = datetime.now()
    begin = end - timedelta(days=days)
    bgn_dt = begin.strftime("%Y%m%d%H%M")
    end_dt = end.strftime("%Y%m%d%H%M")

    inds = args.ind or TARGET_INDS

    all_rows = []
    for ind in inds:
        log(f"[FETCH] ind={ind} from {bgn_dt} to {end_dt}")
        part = fetch_ind(ind, bgn_dt, end_dt)
        all_rows.extend(part)

    rows = filter_rows(all_rows)
    save_excel(rows)

    if args.no_send:
        log("[DONE] main_send finished (no-send)")
        return

    send_alk(rows, RECEIVERS)
    log("[DONE] main_send finished.")


if __name__ == "__main__":
    main()
