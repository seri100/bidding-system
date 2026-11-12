
#!/usr/bin/env python3

import argparse

import copy

import json

import os

import re

import sqlite3

import sys

from pathlib import Path



sys.path.insert(0, "/home/pi/bid-d2b")

import d2b_collect as collect



BASE_DIR = Path("/home/pi/bid-d2b")

PREVIEW = BASE_DIR / "output/preview.json"





def message_fields(row):

    text = re.sub(r"\s+", "", row.get("공고문텍스트", ""))

    values = set()



    patterns = [

        r"공사비\(추정가격\)[:：]([0-9,]+)원\([0-9,]+원\)",

        r"추정금액[:：]([0-9,]+)원"

    ]

    for pattern in patterns:

        for value in re.findall(pattern, text):

            values.add(int(value.replace(",", "")))



    if len(values) != 1:

        raise ValueError("알림톡 표시용 공사비/추정금액 확인 필요")



    amount = next(iter(values))

    title = row["공고명"]

    match = re.search(

        r"평가기준은추정가격(\d+)억원미만(\d+)억원이상",

        text

    )

    if match:

        upper, lower = match.groups()

        title += "/국방부 {}억이상_{}억미만".format(lower, upper)



    if row.get("공동계약") != "미허용":

        raise ValueError("공동계약 조건 추가 확인 필요")



    return {

        "bid_name": title,

        "close_time": row["입찰마감일시"],

        "joint_region": "없음",

        "joint_rate": "없음",

        "prtcpt_region": row["참가가능지역"],

        "amount": amount,

        "amount_str": format(amount, ","),

        "bid_no": row["공고번호"],

        "bid_ord": row["차수"],

        "detail_url": row["detail_url"],

        "org_name": row["발주기관"]

    }





def identity(row):

    raw = row["원문"]

    return (

        str(raw.get("rqstYear") or ""),

        str(raw.get("dprtCode") or ""),

        str(raw.get("anmtNumb") or "")

    )





def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--send", action="store_true")

    args = parser.parse_args()



    if args.send and os.environ.get("HARD_NO_SEND", "").strip() == "1":

        raise RuntimeError("HARD_NO_SEND=1: 실제 발송 차단")



    data = json.loads(PREVIEW.read_text(encoding="utf-8"))

    engine = collect.rules_engine(

        Path("/home/pi/n_data/main_send.py"),

        Path("/home/pi/n_data/alimtalk_recipients.json")

    )



    candidates = []

    for original in data.get("records", []):

        if original.get("status") != "READY_PREVIEW":

            continue

        row = copy.deepcopy(original)

        row["review_reasons"] = []

        collect.assess(row, engine)

        if row["status"] == "READY_PREVIEW":

            candidates.append(row)



    session = None

    latest = {}

    if args.send and candidates:

        session = collect.requests.Session()

        session.headers.update({"User-Agent": "Mozilla/5.0"})

        url = collect.BASE + "/peb/bid/announceList.do?key=41"

        response = session.get(url, timeout=(10, 30))

        response.raise_for_status()

        session.headers["Referer"] = url



        for raw in collect.list_rows(session, 14):

            key = (

                str(raw.get("rqstYear") or ""),

                str(raw.get("dprtCode") or ""),

                str(raw.get("anmtNumb") or "")

            )

            rank = (

                int(raw.get("rqstDegr") or 0),

                str(raw.get("finlChdt") or ""),

                raw.get("anmtCncl") == "Y"

            )

            if key not in latest or rank > latest[key][0]:

                latest[key] = (rank, raw)



    sys.path.insert(0, "/home/pi/n_data")

    from kakao_send_tb0485 import send_for_item



    db = None

    if args.send:

        state = BASE_DIR / "state"

        state.mkdir(parents=True, exist_ok=True)

        db = sqlite3.connect(str(state / "d2b_sent.sqlite3"), timeout=30)

        db.execute("""

            CREATE TABLE IF NOT EXISTS sends (

                event_key TEXT PRIMARY KEY,

                state TEXT NOT NULL,

                updated_at TEXT NOT NULL

            )

        """)

        db.commit()



    sent = skipped = failures = previews = 0

    for row in candidates:

        try:

            fields = message_fields(row)



            if args.send:

                current = latest.get(identity(row))

                if current is None:

                    raise ValueError("최신 목록에서 공고를 찾지 못함")

                raw = current[1]

                if (

                    raw.get("anmtCncl") == "Y"

                    or "취소" in str(raw.get("codeVld1", ""))

                    or str(raw.get("lv2Divs")) != "1"

                    or raw.get("contMthd") == "B"

                    or str(raw.get("rqstDegr")) != row["차수"]

                ):

                    raise ValueError("공고 취소/변경/참가조건 재확인 필요")



                fresh = collect.read_detail(session, raw)

                if fresh is None:

                    raise ValueError("최신 상세에서 대상 면허 미확인")

                collect.assess(fresh, engine)

                fresh_fields = message_fields(fresh)

                if (

                    fresh["status"] != "READY_PREVIEW"

                    or fresh_fields != fields

                    or fresh["추정가격"] != row["추정가격"]

                    or set(fresh["수신대상"]) != set(row["수신대상"])

                ):

                    raise ValueError("미리보기 이후 조건 변경: 재수집 필요")

                row = fresh



            print("[NOTICE]", row["공고번호"],

                  "수신=", len(row["수신대상"]), flush=True)



            for phone in row["수신대상"]:

                if not args.send:

                    result = send_for_item(phone, fields, dry_run=True)

                    if result.get("dry_run") is not True:

                        raise RuntimeError("미리보기 결과 확인 실패")

                    previews += 1

                    continue



                key = json.dumps(

                    ["D2B"] + list(identity(row)) + [row["차수"], phone]

                )

                cursor = db.execute(

                    "INSERT OR IGNORE INTO sends VALUES (?, ?, ?)",

                    (key, "PENDING", collect.now().isoformat())

                )

                db.commit()

                if cursor.rowcount != 1:

                    skipped += 1

                    print("[SKIP_RECORDED]", row["공고번호"], phone)

                    continue



                # Record before sending. An uncertain result stays PENDING;

                # repeated runs cannot automatically send it again.

                result = send_for_item(phone, fields, dry_run=False)

                if (

                    result.get("ok") is not True

                    or result.get("blocked")

                    or result.get("dry_run")

                ):

                    raise RuntimeError("발송 성공 미확인: PENDING 기록 유지")

                db.execute(

                    "UPDATE sends SET state=?, updated_at=? WHERE event_key=?",

                    ("SENT", collect.now().isoformat(), key)

                )

                db.commit()

                sent += 1

                print("[SENT]", row["공고번호"], phone, flush=True)



        except Exception as error:

            failures += 1

            print("[HOLD]", row.get("공고번호"), str(error), flush=True)



    if db:

        db.close()

    print("[SUMMARY] preview={} sent={} recorded_skip={} hold={}".format(

        previews, sent, skipped, failures

    ))

    return 1 if failures else 0





if __name__ == "__main__":

    try:

        sys.exit(main())

    except Exception as error:

        print("[STOP]", type(error).__name__, str(error))

        sys.exit(1)

