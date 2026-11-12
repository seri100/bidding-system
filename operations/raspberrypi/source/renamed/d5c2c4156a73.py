
# -*- coding: utf-8 -*-

"""
LH main crawler script

Features:
1) Crawl LH bid list (all pages, up to MAX_PAGES_HARD_LIMIT)
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
import os

import sys
from datetime import datetime, timedelta
import time
from pathlib import Path
import json
import traceback

import requests  # for SMS

from lh_fetch_gw_adapter import LHCrawler
from lh_parser import LHParser
from lh_excel import LHExcelSaver
from lh_notify import LHNotifier
from lh_notice_doc import enrich_row_from_notice
from lh_attachments import save_target_attachments
from lh_retry_queue import is_already_sent
# __LH_PENDING_RETRY_IMPORT_V2__
from lh_retry_queue import (
    process_alimtalk_rows,
    retry_pending_alimtalk,
)


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

# ---- C안 준비용 크롤링 범위/페이지 상수 ----
# * CRAWL_DAYS_BACK: 입찰공고일 기준 며칠 전부터 조회할지
# * CRAWL_DAYS_FORWARD: 오늘 기준 며칠 뒤까지 볼지
#   - LH가 미래 공고도 미리 등록하는 구조라서 어느 정도 여유를 둠
CRAWL_DAYS_BACK = 14       # 지난 14일 치 공고 포함
CRAWL_DAYS_FORWARD = 150  # 미래 공고까지 포함

# 너무 많은 페이지를 긁지 않도록 하드 리밋
# (LHCrawler.get_page_count() 값이 이보다 크면 이 값으로 캡)
MAX_PAGES_HARD_LIMIT = 50   # 충분히 넉넉한 페이지 범위


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

# __LH_ALIM_REGION_FILTER_V2_BEGIN__

def is_fire_with_region(row):

    """

    LH 알림톡 대상 판정.



    허용 지역:

      - 전국

      - 충청북도/충북

      - 세종특별자치시/세종시/세종



    업종별 처리:

      - 소방시설공사: 지역 공란은 전국 공고로 보고 허용

      - 기계설비/기계가스 계열: 지역값이 있어야 하며 허용 지역만 통과

    """



    ind_type = "".join(str(row.get("업종유형") or "").split())



    regions = []



    for key in [

        "지역제한",

        "지역의무",

        "지역제한1",

        "지역제한2",

        "지역제한3",

        "지역제한4",

        "지역의무1",

        "지역의무2",

        "지역의무3",

        "지역의무4",

        "참가지역1",

        "참가지역2",

        "참가지역3",

        "참가지역4",

        "참가지역",

    ]:

        val = str(row.get(key) or "").strip()



        if val and val not in regions:

            regions.append(val)



    compact = " ".join(regions)



    for ch in [

        " ",

        "\t",

        "\r",

        "\n",

        "_",

        "·",

        ",",

        ";",

        "/",

        "(",

        ")",

        "-",

        "[",

        "]",

    ]:

        compact = compact.replace(ch, "")



    has_region = bool(regions)



    allowed_region = (

        "전국" in compact

        or "충청북도" in compact

        or "충북" in compact

        or "세종특별자치시" in compact

        or "세종시" in compact

        or "세종" in compact

        or "지역제한없음" in compact

        or "제한없음" in compact

    )



    is_fire = "소방시설공사" in ind_type



    is_mechanical = (

        "기계설비" in ind_type

        or "기계가스" in ind_type

        or "가스설비" in ind_type

    )



    if is_fire:

        return (not has_region) or allowed_region



    if is_mechanical:

        return has_region and allowed_region



    return False

# __LH_ALIM_REGION_FILTER_V2_END__

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

# __LH_ALIM_REGION_FILTER_V4_BEGIN__

LH_NATIONWIDE_ESTIMATE_THRESHOLD = 1_000_000_000





def _lh_v4_amount_to_int(value):

    """LH 금액 문자열을 정수 원 단위로 변환한다."""

    if value is None or isinstance(value, bool):

        return 0



    if isinstance(value, (int, float)):

        return int(value)



    text = str(value).strip()



    if not text:

        return 0



    # 예:

    # 4,912,825,000원 (사십구억...)

    head = text.split("원", 1)[0]



    digits = "".join(

        ch for ch in head

        if ch.isdigit()

    )



    return int(digits) if digits else 0





def _lh_v4_industry_flags(row):

    """

    업종유형과 실제 요구면허 전체를 함께 확인한다.

    """



    industry_values = [

        row.get("업종유형"),

        row.get("업종"),

        row.get("요구면허"),

    ]



    industry_values.extend(

        row.get("요구면허{}".format(index))

        for index in range(1, 11)

    )



    industry = "".join(

        "".join(str(value or "").split())

        for value in industry_values

    )



    is_fire = (

        "소방시설공사" in industry

    )



    is_mechanical = any(

        keyword in industry

        for keyword in (

            "기계설비",

            "기계가스",

            "기계·가스",

            "가스설비",

        )

    )



    return is_fire, is_mechanical





def _lh_v4_regions(row):

    """

    참가지역1~4를 수집한다.



    추정가격 10억원 이상 공고에서는

    입찰 제한지역이 아니라 지역업체 협정정보로 취급한다.

    """

    regions = []



    for key in (

        "지역제한",

        "지역의무",

        "지역제한1",

        "지역제한2",

        "지역제한3",

        "지역제한4",

        "지역의무1",

        "지역의무2",

        "지역의무3",

        "지역의무4",

        "참가지역1",

        "참가지역2",

        "참가지역3",

        "참가지역4",

        "참가지역",

    ):

        value = str(

            row.get(key) or ""

        ).strip()



        if value and value not in regions:

            regions.append(value)



    return regions





def _lh_v4_allowed_local_region(regions):

    region_text = "".join(

        " ".join(regions).split()

    )



    return any(

        keyword in region_text

        for keyword in (

            "전국",

            "지역제한없음",

            "제한없음",

            "충청북도",

            "충북",

            "세종특별자치시",

            "세종시",

            "세종",

        )

    )





def lh_alimtalk_target_decision(row):

    """

    LH 알림톡 최종 판정.



    1. 대상 업종

       - 소방시설공사

       - 기계설비·기계가스 계열



    2. 추정가격 10억원 이상

       - 전국 공고

       - 참가지역1~4와 무관하게 발송

       - 참가지역은 지역업체 협정정보로 표시



    3. 추정가격 10억원 미만

       - 전국·충북·세종만 발송

       - 모든 대상 업종에서 지역 공란 제외

       - 지역이 명시된 전국·충북·세종만 허용

    """

    is_fire, is_mechanical = (

        _lh_v4_industry_flags(row)

    )



    if not (is_fire or is_mechanical):

        return False, "대상업종 아님"



    estimate = _lh_v4_amount_to_int(

        row.get("추정가격")

    )



    regions = _lh_v4_regions(row)



    region_label = (

        ", ".join(regions)

        if regions

        else "공란"

    )



    # 가장 먼저 추정가격으로 전국 여부를 판정한다.

    if (

        estimate

        >= LH_NATIONWIDE_ESTIMATE_THRESHOLD

    ):

        return (

            True,

            (

                "추정가격 10억원 이상 전국판정: "

                "{:,}원 / 협정지역={}"

            ).format(

                estimate,

                region_label,

            ),

        )



    allowed_local = (

        _lh_v4_allowed_local_region(

            regions

        )

    )



    if allowed_local:

        return (

            True,

            "10억원 미만 허용지역: {}".format(

                region_label

            ),

        )



    if not regions:

        return (

            False,

            "10억원 미만 + 지역공란 제외",

        )


    return (

        False,

        "10억원 미만 제외지역: {}".format(

            region_label

        ),

    )





def is_fire_with_region(row):

    """

    기존 run_main() 호출부와의 호환성을 유지한다.

    """

    return lh_alimtalk_target_decision(

        row

    )[0]

# __LH_ALIM_REGION_FILTER_V4_END__


def run_main():
    # ---- C안: 날짜 범위는 넓게, 내부에서 필터링 ----
    today = datetime.now().date()
    start_dt = today - timedelta(days=CRAWL_DAYS_BACK)
    end_dt = today + timedelta(days=CRAWL_DAYS_FORWARD)

    start_date = start_dt.strftime("%Y/%m/%d")
    end_date = end_dt.strftime("%Y/%m/%d")
    log("Crawl period: {} ~ {}".format(start_date, end_date))

    crawler = LHCrawler()
    parser = LHParser()
    #✅ REDACTED_PRIVATE_VALUE ← 라즈베리파이에서의 실제 경로
    #✅ Z:\VOL1\bid\seri_Alarm_Server6 ← 윈도우에서 보이는 경로
    #saver = LHExcelSaver(out_dir="/mnt/vol1/bid/LH")
    out_dir = os.environ.get("LH_OUT_DIR", "REDACTED_PRIVATE_VALUE")
    saver = LHExcelSaver(out_dir=out_dir)

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
    # __LH_FAILURE_SMS_BIND_V1__
    notifier.error_callback = send_error_sms

    # __LH_PENDING_RETRY_RUN_V2_BEGIN__
    pending_sent_rows, pending_failed_rows = (
        retry_pending_alimtalk(
            notifier,
            log=log,
        )
    )

    if pending_sent_rows:
        try:
            from lh_calendar_sync import (
                sync_lh_calendar_rows,
            )

            sync_lh_calendar_rows(
                pending_sent_rows,
                log=log,
            )

        except Exception as exc:
            log(
                "Pending calendar sync error: {}".format(
                    exc
                )
            )
    # __LH_PENDING_RETRY_RUN_V2_END__


    # page count: 일시적인 LH 응답 지연은 최대 3회 재시도한다.

    page_count = None



    for attempt in range(1, 4):

        try:

            page_count = crawler.get_page_count(

                start_date,

                end_date,

            )



            log(

                "Raw total pages from crawler: {}".format(

                    page_count

                )

            )

            break



        except Exception as exc:

            log(

                "Page count error attempt {}/3: {}".format(

                    attempt,

                    exc,

                )

            )



            if attempt < 3:

                time.sleep(2)



    if page_count is None:

        log(

            "Page count failed after 3 attempts "

            "-> abort this run safely"

        )

        return



    if page_count > MAX_PAGES_HARD_LIMIT:

        log(

            "Total pages {} > limit {} -> use capped value".format(

                page_count,

                MAX_PAGES_HARD_LIMIT,

            )

        )

        page_count = MAX_PAGES_HARD_LIMIT



    if page_count <= 0:
        log("No pages to crawl (page_count={}) → exit".format(page_count))
        return

    log("Total pages to crawl: {}".format(page_count))

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
            # C안: 더 이상 공고가 없으면 조기 종료
            break

        log("[PAGE] {} notices: {}".format(page_no, len(notices)))

        for n in notices:
            # 여기서 notice_no 키는 LHCrawler가 normalize한 리스트 구조를 따른다.
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

    # __REDACTED_PRIVATE_VALUE_ENRICH_NEW_ROWS_V1_BEGIN__

    for row in all_rows:

        bid_no = (

            row.get("공고번호")

            or ""

        )



        try:

            enrich_row_from_notice(

                row,

                session=crawler.session,

            )

            log(

                "[NOTICE_DOC] bid={} status={}".format(

                    bid_no,

                    row.get("공고문 추출상태", ""),

                )

            )

        except Exception as exc:

            row["공고문 추출상태"] = (

                "실패: {}: {}".format(

                    type(exc).__name__,

                    exc,

                )

            )

            log(

                "[NOTICE_DOC] bid={} error={}".format(

                    bid_no,

                    exc,

                )

            )

    # __REDACTED_PRIVATE_VALUE_ENRICH_NEW_ROWS_V1_END__



    # Excel save
    xlsx = saver.save(all_rows)
    if not xlsx:
        log("Excel save failed")
        raise RuntimeError("Excel save failed")

    log("Excel saved: {}".format(xlsx))

    # filter AlimTalk targets
    targets = []

    for row in all_rows:
        allowed, reason = lh_alimtalk_target_decision(row)

        log(
            "[FILTER] bid={} title={} allowed={} reason={}".format(
                row.get("공고번호")
                or row.get("notice_no")
                or "",
                row.get("입찰공고건명")
                or row.get("공고명")
                or "",
                allowed,
                reason,
            )
        )

        if allowed:
            targets.append(row)

    # __LH_ALL_ATTACHMENTS_V1__
    attachment_targets = [
        row for row in targets
        if not is_already_sent(row.get("공고번호"))
    ]
    if attachment_targets:
        count = save_target_attachments(
            attachment_targets,
            session=crawler.session,
            output_root=out_dir,
            log=log,
        )
        # 최초 저장한 동일 엑셀을 갱신하여 첨부 경로/개수/상태를 반영한다.
        import pandas as _lh_attach_pd
        _lh_attach_pd.DataFrame(all_rows).to_excel(xlsx, index=False)
        log("[ATTACH][EXCEL_UPDATED] path={} rows={}".format(xlsx, count))

    log("AlimTalk target count: {}".format(len(targets)))
    if not targets:
        log("No AlimTalk targets")
        log("Done")
        return

    # __LH_PENDING_NEW_SEND_V2_BEGIN__
    sent_rows, failed_rows = process_alimtalk_rows(
        notifier,
        targets,
        log=log,
    )
    sent_cnt = len(sent_rows)

    if sent_rows:
        try:
            from lh_calendar_sync import (
                sync_lh_calendar_rows,
            )

            sync_lh_calendar_rows(
                sent_rows,
                log=log,
            )

        except Exception as exc:
            log(
                "Calendar sync error: {}".format(
                    exc
                )
            )

    if failed_rows:
        log(
            "AlimTalk failed rows queued: {}".format(
                len(failed_rows)
            )
        )
    # __LH_PENDING_NEW_SEND_V2_END__

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
