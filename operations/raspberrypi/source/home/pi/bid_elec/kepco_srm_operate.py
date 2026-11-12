#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import argparse

import hashlib

import os

import sqlite3

import sys

import traceback

from datetime import datetime, timedelta, timezone

from pathlib import Path



os.environ.setdefault("N_DATA_ENV", "PROD")

os.environ.setdefault("N_DATA_BASE", "/mnt/vol1/bid/n_data")



BASE_DIR = Path("/home/pi/bid_elec")

STATE_DB = Path(

    "/home/pi/bid_elec/kepco_srm_send_state.sqlite3"

)



sys.path.insert(0, str(BASE_DIR))

sys.path.insert(0, "/home/pi/n_data")



import kepco_srm_collect as collector
from kepco_all_attachments import save_target_attachments

# __KEPCO_ALL_ATTACHMENTS_V1__





KST = timezone(timedelta(hours=9))





def connect_db():

    STATE_DB.parent.mkdir(parents=True, exist_ok=True)



    conn = sqlite3.connect(

        str(STATE_DB),

        timeout=30,

    )



    conn.execute(

        """

        CREATE TABLE IF NOT EXISTS send_state (

            announce_no TEXT NOT NULL,

            receiver TEXT NOT NULL,

            fingerprint TEXT NOT NULL,

            title TEXT,

            status TEXT NOT NULL,

            sent_at TEXT,

            updated_at TEXT NOT NULL,

            error TEXT,

            PRIMARY KEY (

                announce_no,

                receiver,

                fingerprint

            )

        )

        """

    )



    conn.execute(

        """

        CREATE INDEX IF NOT EXISTS

        idx_send_state_notice

        ON send_state (

            announce_no,

            receiver,

            status

        )

        """

    )



    conn.commit()

    return conn





def fingerprint(row):

    values = [

        str(row.get("공고명") or ""),

        str(row.get("입찰마감일시") or ""),

        str(row.get("추정가격") or ""),

        str(row.get("대표지역") or ""),

        str(row.get("진행상태") or ""),

    ]



    raw = "|".join(values).encode(

        "utf-8",

        errors="replace",

    )



    return hashlib.sha256(raw).hexdigest()





def normalize_industry_code(value):

    text = str(value or "").strip()



    if text.isdigit():

        return text.zfill(4)



    return text





def mask_phone(phone):

    text = str(phone or "").strip()



    if len(text) >= 8:

        return text[:3] + "****" + text[-4:]



    return "****"





def already_sent(conn, announce_no, receiver, fp):

    row = conn.execute(

        """

        SELECT status

        FROM send_state

        WHERE announce_no=?

          AND receiver=?

          AND fingerprint=?

        """,

        (announce_no, receiver, fp),

    ).fetchone()



    return bool(row and row[0] == "sent")





def save_result(

    conn,

    announce_no,

    receiver,

    fp,

    title,

    status,

    error="",

):

    now = datetime.now(KST).strftime(

        "%Y-%m-%d %H:%M:%S"

    )



    sent_at = now if status == "sent" else None



    conn.execute(

        """

        INSERT INTO send_state (

            announce_no,

            receiver,

            fingerprint,

            title,

            status,

            sent_at,

            updated_at,

            error

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT (

            announce_no,

            receiver,

            fingerprint

        )

        DO UPDATE SET

            title=excluded.title,

            status=excluded.status,

            sent_at=excluded.sent_at,

            updated_at=excluded.updated_at,

            error=excluded.error

        """,

        (

            announce_no,

            receiver,

            fp,

            title,

            status,

            sent_at,

            now,

            str(error or "")[:1000],

        ),

    )



    conn.commit()





def result_ok(main_send, result):

    checker = getattr(

        main_send,

        "_send_result_ok",

        None,

    )



    if callable(checker):

        try:

            return bool(checker(result))

        except Exception:

            pass



    if result is True:

        return True



    if isinstance(result, dict):

        for key in (

            "success",

            "ok",

            "result",

            "sent",

        ):

            if result.get(key) is True:

                return True



    return False





def prepare_rows(days):

    collector.log(

        "운영 수집 시작: 최근 %s일" % days

    )



    records = collector.collect(days)

    matched = []

    excluded = {}



    for source_row in records:

        ok, reason = collector.filter_reason(

            source_row

        )



        if ok:

            row = collector.convert_row(

                source_row

            )

            row["공고업종코드"] = (

                normalize_industry_code(

                    row.get("공고업종코드")

                )

            )

            matched.append(row)

        else:

            excluded[reason] = (

                excluded.get(reason, 0) + 1

            )



    # 공식 한전 공고문에서 공동수급·협정정보 보완

    try:

        from kepco_agreement_enrich import enrich_rows



        matched = enrich_rows(

            matched,

            log=collector.log,

        )

    except Exception as exc:

        collector.log(

            "[AGREEMENT][FATAL] {}: {}".format(

                type(exc).__name__,

                exc,

            )

        )



        for row in matched:

            row.setdefault("공동수급여부", "확인실패")

            row.setdefault("공동수급방식", "")

            row.setdefault("협정마감일시", "")

            row.setdefault(

                "협정정보출처",

                "한전 SRM 공식 입찰공고문",

            )

            row.setdefault(

                "협정확인상태",

                "자동 상세조회 실패",

            )

            row.setdefault(

                "다음행동",

                "공고문 원문에서 협정정보 직접 확인",

            )



    collector.log(

        "전체 수집=%s, 발송조건 일치=%s" %

        (len(records), len(matched))

    )

    collector.log("제외 내역=%s" % excluded)

    return matched







# __KEPCO_GCAL_CONNECT_V1__

def sync_kepco_calendar(row, main_send, dry_run=False):

    from modules.calendar_sync import sync_message_to_gcal

    import re



    notice = str(row.get("공고번호") or "").strip()

    item = dict(row)

    begin = (

        item.get("입찰시작일시")

        or item.get("입찰서접수개시일시")

        or item.get("시작일시")

    )

    if not begin:

        collector.log("[KEPCO_GCAL][DEFER_NO_BEGIN] %s" % notice)

        return None



    item["시작일시"] = str(begin)

    item["입찰서접수개시일시"] = str(begin)

    # __KEPCO_BASE_AMOUNT_SOURCE_V1__
    # 과거 엑셀의 추정가격 복사값도 공식 기초금액으로 표시하지 않는다.
    if str(item.get("기초금액출처") or "").strip() in ("", "미확인"):
        item["기초금액"] = 0
    message = main_send.build_gcal_message(item)



    # 한전 공고에 나라장터 링크가 들어가지 않도록 고정

    url_line = "상세URL : https://srm.kepco.net/index.do"

    if re.search(r"^상세URL\s*[:：].*$", message, re.MULTILINE):

        message = re.sub(

            r"^상세URL\s*[:：].*$",

            url_line,

            message,

            flags=re.MULTILINE,

        )

    else:

        message += "\n" + url_line



    if dry_run:

        from modules.calendar_sync import gcal_sync_filter_decision

        decision = gcal_sync_filter_decision(message)

        collector.log("[KEPCO_GCAL][DRY] %s -> %r" % (notice, decision))

        return decision



    result = sync_message_to_gcal(message, logger=collector.log)

    collector.log("[KEPCO_GCAL][RESULT] %s -> %r" % (notice, result))

    return result





def main():

    parser = argparse.ArgumentParser()



    parser.add_argument(

        "--days",

        type=int,

        default=14,

    )



    parser.add_argument(

        "--no-send",

        action="store_true",

        help="발송 예정 내역만 표시",

    )



    args = parser.parse_args()



    rows = prepare_rows(args.days)



    import main_send



    conn = connect_db()



    total_receivers = 0

    pending = 0

    skipped = 0

    sent = 0

    failed = 0



    for row in rows:

        announce_no = str(

            row.get("공고번호") or ""

        ).strip()

        title = str(

            row.get("공고명") or ""

        ).strip()

        fp = fingerprint(row)



        receivers = main_send.decide_receivers(

            row

        )



        receivers = list(dict.fromkeys(

            str(value).strip()

            for value in receivers

            if str(value).strip()

        ))



        total_receivers += len(receivers)



        if not receivers:

            collector.log(

                "[NO_RECEIVER] %s | %s | "

                "업종=%s 지역=%s scope=%s" %

                (

                    announce_no,

                    title,

                    row.get("공고업종코드"),

                    row.get("대표지역"),

                    row.get("scope"),

                )

            )

            continue



        # 발송 이력과 별도로 일정 생성/갱신: 기발송 건도 누락 복구

        try:

            sync_kepco_calendar(row, main_send, dry_run=args.no_send)

        except Exception as exc:

            collector.log(

                "[KEPCO_GCAL][ERROR] %s | %r" % (announce_no, exc)

            )



        pending_receivers = []
        for receiver in receivers:
            masked = mask_phone(receiver)
            if already_sent(conn, announce_no, receiver, fp):
                skipped += 1
                collector.log("[ALREADY_SENT] %s | %s | %s" % (announce_no, masked, title))
                continue
            central_sent = False
            try:
                fields = main_send.build_kakao_fields(row)
                central_sent = bool(main_send.is_already_sent(fields, receiver))
            except Exception as exc:
                collector.log("[CENTRAL_DEDUP][WARN] %s | %s | %r" % (announce_no, masked, exc))
            if central_sent:
                skipped += 1
                if not args.no_send:
                    save_result(conn, announce_no, receiver, fp, title, "sent", "synced from n_data sent guard")
                collector.log("[CENTRAL_SENT_SYNC] %s | %s | %s" % (announce_no, masked, title))
                continue
            pending_receivers.append(receiver)

        if pending_receivers:
            save_target_attachments(row, log=collector.log)
            row["알림톡상태"] = "DRY_RUN" if args.no_send else "발송대기"
        elif receivers:
            row["알림톡상태"] = "기발송"

        for receiver in pending_receivers:

            masked = mask_phone(receiver)



            if already_sent(

                conn,

                announce_no,

                receiver,

                fp,

            ):

                skipped += 1



                collector.log(

                    "[ALREADY_SENT] %s | %s | %s" %

                    (announce_no, masked, title)

                )

                continue



            pending += 1



            if args.no_send:

                collector.log(

                    "[DRY_SEND] %s | %s | "

                    "업종=%s | 지역=%s | %s" %

                    (

                        announce_no,

                        masked,

                        row.get("공고업종명"),

                        row.get("대표지역"),

                        title,

                    )

                )

                continue



            try:

                result = main_send.send_kakao_one(

                    receiver,

                    row,

                    no_send=False,

                )



                if result_ok(main_send, result):

                    sent += 1



                    save_result(

                        conn,

                        announce_no,

                        receiver,

                        fp,

                        title,

                        "sent",

                    )



                    collector.log(

                        "[SEND_OK] %s | %s | %s" %

                        (announce_no, masked, title)

                    )

                else:

                    failed += 1



                    save_result(

                        conn,

                        announce_no,

                        receiver,

                        fp,

                        title,

                        "failed",

                        repr(result),

                    )



                    collector.log(

                        "[SEND_FAIL] %s | %s | "

                        "result=%r" %

                        (announce_no, masked, result)

                    )



            except Exception as e:

                failed += 1



                save_result(

                    conn,

                    announce_no,

                    receiver,

                    fp,

                    title,

                    "failed",

                    repr(e),

                )



                collector.log(

                    "[SEND_ERROR] %s | %s | %r" %

                    (announce_no, masked, e)

                )



    output, latest = collector.save_excel(rows)
    collector.log("엑셀 저장=%s" % output)
    collector.log("최신 파일=%s" % latest)

    conn.close()



    collector.log(

        "발송 요약: 공고=%s, 수신자합계=%s, "

        "신규대상=%s, 기존발송=%s, "

        "성공=%s, 실패=%s, no_send=%s" %

        (

            len(rows),

            total_receivers,

            pending,

            skipped,

            sent,

            failed,

            args.no_send,

        )

    )



    if failed:

        raise SystemExit(2)





if __name__ == "__main__":

    try:

        main()

    except Exception:

        traceback.print_exc()

        raise

