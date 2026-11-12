
# -*- coding: utf-8 -*-

"""
LH main crawler script

Features:
1) Crawl LH bid list (all pages)
2) Fetch each bid detail
3) Normalize to standard dict format
4) Save to /mnt/vol1/bid/LH/LH_YYYYMMDD_HHMMSS.xlsx
5) Send Kakao AlimTalk only for:
   - 업종유형 == "소방시설공사"
   - 참가지역1~4 중 하나라도 값이 있는 경우
6) Exclude already-seen bid numbers (dedupe by 공고번호)
7) --reset-seen: reset dedupe history
8) On fatal error:
   - 1st try AlimTalk
   - retry once if it fails
   - if still fails or main logic crashes, send ASCII-only SMS to REDACTED_PHONE
"""

import sys
from datetime import datetime, timedelta
import time
from pathlib import Path
import json
import traceback

import requests  # for SMS

from lh_fetch import LHCrawler
from lh_parser import LHParser
from lh_excel import LHExcelSaver
from lh_notify import LHNotifier


# ============================
# Common paths & config
# ============================

BASE_DIR = Path(__file__).resolve().parent
SEEN_FILE = BASE_DIR / "lh_seen_bids.json"

# candidate keys for bid number
BID_KEY_CANDIDATES = [
    "bidNtceNo",
    "공고번호",
    "bid_no",
    "notice_no",
]

# Aligo SMS config file
ALIGO_SMS_CONF = Path("/home/pi/n_data/aligo_sms.json")
ERROR_SMS_RECEIVER = "REDACTED_PRIVATE_VALUE"  # fatal error SMS receiver


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[LH_MAIN] {} {}".format(ts, msg), flush=True)


# ============================
# Seen-bids management (dedupe)
# ============================

def _load_seen_bids():
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(str(x) for x in data)
        except Exception as e:
            log("WARN: SEEN_FILE load error: {}".format(e))
    return set()


def _save_seen_bids(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f, ensure_ascii=False)
    except Exception as e:
        log("WARN: SEEN_FILE save error: {}".format(e))


def reset_seen_bids():
    """Reset seen-bid history (for --reset-seen)"""
    if SEEN_FILE.exists():
        try:
            SEEN_FILE.unlink()
            log("Seen-bid file removed: {}".format(SEEN_FILE))
        except Exception as e:
            log("Error while removing seen-bid file: {}".format(e))
    else:
        log("Seen-bid file not found: {}".format(SEEN_FILE))


def _detect_bid_key(sample_row):
    if not isinstance(sample_row, dict):
        return None
    for k in BID_KEY_CANDIDATES:
        if k in sample_row:
            return k
    return None


def dedup_notices(rows):
    """Return only new bids by 공고번호 from rows(list[dict])"""
    if not rows:
        log("INFO: rows is empty")
        return rows

    bid_key = _detect_bid_key(rows[0])
    if not bid_key:
        log("ERROR: could not detect bid key from row.")
        return rows

    log("INFO: using '{}' as bid key".format(bid_key))

    seen = _load_seen_bids()
    new_seen = set(seen)
    used = set()  # used in this run only

    result = []
    dup_this_run = 0
    dup_seen = 0
    no_bid = 0

    for r in rows:
        if not isinstance(r, dict):
            result.append(r)
            continue

        bid_val = str(r.get(bid_key, "")).strip()

        if not bid_val:
            no_bid += 1
            result.append(r)
            continue

        if bid_val in used:
            dup_this_run += 1
            continue

        if bid_val in seen:
            dup_seen += 1
            continue

        used.add(bid_val)
        new_seen.add(bid_val)
        result.append(r)

    _save_seen_bids(new_seen)

    log(
        "INFO: dedup result - in-run dup={}, seen-dup={}, no-bid={}, final={}, total-seen={}".format(
            dup_this_run, dup_seen, no_bid, len(result), len(new_seen)
        )
    )

    return result


# ============================
# Filter for AlimTalk targets
# ============================

def is_fire_with_region(row):
    """
    대상 조건:
    - 업종유형 == "소방시설공사"
    - 참가지역1~4 중 하나라도 값이 있는 경우
    """
    ind_type = (row.get("업종유형") or "").strip()
    if ind_type != "소방시설공사":
        return False

    for key in ["참가지역1", "참가지역2", "참가지역3", "참가지역4"]:
        if (row.get(key) or "").strip():
            return True

    return False


# ============================
# Aligo SMS (ASCII-only message)
# ============================

def _load_aligo_sms_conf():
    if not ALIGO_SMS_CONF.exists():
        log("WARN: SMS config file not found: {}".format(ALIGO_SMS_CONF))
        return None
    try:
        with open(ALIGO_SMS_CONF, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        key = cfg.get("key")
        user_id = cfg.get("user_id")
        sender = cfg.get("sender")
        if not (key and user_id and sender):
            log("WARN: SMS config missing key/user_id/sender.")
            return None
        return cfg
    except Exception as e:
        log("WARN: SMS config read error: {}".format(e))
        return None


def _to_ascii_safe(text):
    """Convert any string to ASCII-safe form (non-ASCII -> '?')."""
    if not isinstance(text, str):
        text = str(text)
    return "".join(ch if ord(ch) < 128 else "?" for ch in text)


def send_error_sms(message):
    """
    Send ASCII-only SMS to ERROR_SMS_RECEIVER on fatal errors.
    Non-ASCII chars are replaced with '?' to avoid mojibake.
    """
    cfg = _load_aligo_sms_conf()
    if not cfg:
        log("ERROR: SMS config not available; skip error SMS.")
        return

    url = "https://apis.aligo.in/send/"

    short_msg = message
    if len(short_msg) > 400:
        short_msg = short_msg[:380] + "...(truncated)"

    safe_body = _to_ascii_safe(short_msg)
    full_msg = "[LH_MAIN ERROR]\n" + safe_body

    data = {
        "key": cfg["key"],
        "user_id": cfg["user_id"],
        "sender": cfg["sender"],
        "receiver": ERROR_SMS_RECEIVER,
        "msg": full_msg,
        "testmode_yn": "N",
    }

    try:
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        try:
            j = resp.json()
        except Exception:
            log("WARN: SMS response JSON decode failed: {}".format(resp.text))
            return

        result_code = str(j.get("result_code"))
        if result_code != "1":
            log("ERROR: SMS send failed: {}".format(j))
        else:
            log("INFO: error SMS sent to {}".format(ERROR_SMS_RECEIVER))
    except Exception as e:
        log("ERROR: SMS send exception: {}".format(e))


# ============================
# Main logic
# ============================

def run_main():
    today = datetime.now()
    start_date = today.strftime("%Y/%m/%d")
    end_date = (today + timedelta(days=150)).strftime("%Y/%m/%d")
    log("Crawl period: {} ~ {}".format(start_date, end_date))

    crawler = LHCrawler()
    parser = LHParser()
    saver = LHExcelSaver(out_dir="/mnt/vol1/bid/LH")
    notifier = LHNotifier(
        tpl_code="TZ_4492",
        sender="REDACTED_PRIVATE_VALUE",
        receivers=[
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
        ],
    )

    # page count
    try:
        page_count = crawler.get_page_count(start_date, end_date)
    except Exception as e:
        log("Error getting page count: {}".format(e))
        raise

    log("Total pages: {}".format(page_count))

    all_rows = []

    for page_no in range(1, page_count + 1):
        log("[PAGE] {}/{} collecting list".format(page_no, page_count))

        try:
            notices = crawler.fetch_list_page(page_no, start_date, end_date)
        except Exception as e:
            log("List page error p{}: {}".format(page_no, e))
            continue

        if not notices:
            log("[PAGE] {} no notices".format(page_no))
            continue

        log("[PAGE] {} notices: {}".format(page_no, len(notices)))

        for n in notices:
            notice_no = n.get("notice_no")
            log("  - detail: {}".format(notice_no))
            try:
                detail = crawler.fetch_detail(n)
                if not detail:
                    log("    no detail: {}".format(notice_no))
                    continue
                row = parser.normalize(detail)
                all_rows.append(row)
                time.sleep(0.5)
            except Exception as e:
                log("    detail error({}): {}".format(notice_no, e))
                continue

        time.sleep(1.0)

    if not all_rows:
        log("No collected notices -> exit")
        return

    log("Collected notices (with dup): {}".format(len(all_rows)))

    # dedupe by bid number
    all_rows = dedup_notices(all_rows)

    if not all_rows:
        log("After dedup: no new notices (skip Excel/AlimTalk)")
        return

    # Excel save
    xlsx = saver.save(all_rows)
    if not xlsx:
        log("Excel save failed")
        raise RuntimeError("Excel save failed")

    log("Excel saved: {}".format(xlsx))

    # filter AlimTalk targets
    targets = [r for r in all_rows if is_fire_with_region(r)]
    log("AlimTalk target count: {}".format(len(targets)))

    if not targets:
        log("No AlimTalk targets")
        log("Done")
        return

    # send AlimTalk: 1st try + 1 retry
    try:
        notifier.send_notices(targets)
    except Exception as e:
        log("AlimTalk first try error: {} -> retry once".format(e))
        time.sleep(3)
        try:
            notifier.send_notices(targets)
        except Exception as e2:
            log("AlimTalk retry failed: {}".format(e2))
            send_error_sms("AlimTalk send failed: {}".format(e2))
            raise

    log("Done")


# ============================
# Entry point
# ============================

if __name__ == "__main__":
    # 1) reset seen-bids mode
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-seen":
        reset_seen_bids()
        sys.exit(0)

    # 2) normal run
    try:
        run_main()
    except Exception as e:
        # catch all, log, traceback, send SMS
        log("Fatal error: {}".format(e))
        traceback.print_exc()
        send_error_sms("Fatal error in LH_MAIN: {}".format(e))
        sys.exit(1)

