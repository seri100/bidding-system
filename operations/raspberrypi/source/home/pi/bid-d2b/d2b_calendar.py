
import hashlib

import json

import sys

from datetime import datetime, timedelta, timezone

from pathlib import Path



sys.path.insert(0, "/home/pi/n_data")

sys.path.insert(0, "/home/pi/bid-d2b")



from modules import calendar_sync as gcal

from googleapiclient.errors import HttpError

import d2b_collect as collect



KST = timezone(timedelta(hours=9))







def money_text(value):

    if value is None or value == "":

        return "미확인"

    try:

        return "{:,}원".format(int(str(value).replace(",", "")))

    except (ValueError, TypeError):

        return "미확인"




def main():

    if not getattr(gcal, "GCAL_SYNC_ENABLED", False):

        raise RuntimeError("既存 GCAL_SYNC_ENABLED가 꺼져 있습니다.")



    path = Path("/home/pi/bid-d2b/output/preview.json")

    data = json.loads(path.read_text(encoding="utf-8"))

    generated = datetime.fromisoformat(data["generated_at"])

    if generated.tzinfo is None:

        generated = generated.replace(tzinfo=KST)

    age = datetime.now(KST) - generated

    if not timedelta(minutes=-5) <= age <= timedelta(hours=2):

        raise RuntimeError("최신 수집 결과가 아닙니다.")



    engine = collect.rules_engine(

        Path("/home/pi/n_data/main_send.py"),

        Path("/home/pi/n_data/alimtalk_recipients.json"),

    )

    service = None

    synced = held = skipped = errors = 0



    for original in data.get("records", []):

        if original.get("status") != "READY_PREVIEW":

            continue

        row = dict(original)

        row["review_reasons"] = []

        collect.assess(row, engine)

        if row.get("status") != "READY_PREVIEW":

            continue



        bid = str(row.get("공고번호") or "")

        region = str(row.get("참가가능지역") or "")

        amount = int(row.get("추정가격") or 0)

        local = any(

            name in region

            for name in ("충청북도", "충북", "청주", "세종")

        )

        nationwide = "전국" in region and amount >= 1000000000

        if not (local or nationwide):

            print("[GCAL_SKIP_REGION]", bid, region, flush=True)

            skipped += 1

            continue



        release = str(row.get("기초예비가격공개일시") or "")

        if not release:

            print("[GCAL_HOLD_NO_RELEASE]", bid, flush=True)

            held += 1

            continue



        try:

            kind = row.get("기초예비가격공개값유형")

            if kind == "date":

                day = datetime.strptime(release, "%Y-%m-%d").date()

                start = {"date": day.isoformat()}

                end = {"date": (day + timedelta(days=1)).isoformat()}

            elif kind == "dateTime":

                dt = datetime.fromisoformat(release)

                if dt.tzinfo is None:

                    dt = dt.replace(tzinfo=KST)

                minutes = getattr(gcal, "GCAL_DEFAULT_DURATION_MINUTES", 60)

                start = {

                    "dateTime": dt.isoformat(),

                    "timeZone": "Asia/Seoul",

                }

                end = {

                    "dateTime": (dt + timedelta(minutes=minutes)).isoformat(),

                    "timeZone": "Asia/Seoul",

                }

            else:

                raise ValueError("공개일 값 유형 확인 필요")



            raw = row.get("원문") or {}

            year = str(raw.get("rqstYear") or "")

            agency = str(raw.get("dprtCode") or "")

            if not all((year, agency, bid)):

                raise ValueError("연도/기관/공고번호 누락")



            key = "d2b|{}|{}|{}".format(year, agency, bid)

            event_id = "d2b" + hashlib.sha256(key.encode()).hexdigest()

            description = "\n".join([

                "국방전자조달(D2B)",

                "공고번호: {} - {}".format(bid, row.get("차수", "")),

                "발주기관: {}".format(row.get("발주기관", "")),

                "참가지역: " + region,

                "추정가격: {:,}원".format(amount),

                "기초예비가격: " + money_text(row.get("기초예비가격")),

                "A값: " + money_text(row.get("A값")),

                "순공사원가: " + money_text(row.get("순공사원가")),

                "금액 산출기준: " + str(row.get("금액산출기준", "")),

                "입찰개시일(기초예비가격 공개일): " + release,

                "참가등록마감: {}".format(row.get("참가등록마감일시", "")),

                "입찰마감: {}".format(row.get("입찰마감일시", "")),

                "개찰일시: {}".format(row.get("개찰일시", "")),

                "공동계약: {}".format(row.get("공동계약", "")),

                "공개일 출처: {}".format(

                    row.get("기초예비가격공개출처", "")

                ),

                str(row.get("detail_url") or ""),

            ])

            body = {

                "summary": "[입찰개시·국방] " + row["공고명"],

                "description": description,

                "location": region,

                "start": start,

                "end": end,

                "extendedProperties": {

                    "private": {"source": "d2b", "noticeKey": key}

                },

            }



            if service is None:

                service = gcal.get_gcal_service()

                if service is None:

                    raise RuntimeError("기존 캘린더 인증 확인 필요")

            events = service.events()



            try:

                existing = events.get(

                    calendarId=gcal.GCAL_CALENDAR_ID,

                    eventId=event_id,

                ).execute()

            except HttpError as exc:

                if getattr(exc.resp, "status", None) != 404:

                    raise

                existing = None



            if existing is None:

                result = events.insert(

                    calendarId=gcal.GCAL_CALENDAR_ID,

                    body=dict(body, id=event_id),

                ).execute()

                action = "CREATED"

            elif all(existing.get(k) == v for k, v in body.items()):

                result = existing

                action = "UNCHANGED"

            else:

                result = events.patch(

                    calendarId=gcal.GCAL_CALENDAR_ID,

                    eventId=event_id,

                    body=body,

                ).execute()

                action = "UPDATED"



            print("[GCAL_{}] {} {} {}".format(

                action, bid, release, result.get("htmlLink", "")

            ), flush=True)

            synced += 1

        except Exception as exc:

            print("[GCAL_ERROR]", bid, type(exc).__name__, str(exc),

                  flush=True)

            errors += 1



    print("[GCAL_SUMMARY] synced={} hold={} skipped={} errors={}".format(

        synced, held, skipped, errors), flush=True)

    return 1 if errors else 0





if __name__ == "__main__":

    sys.exit(main())

