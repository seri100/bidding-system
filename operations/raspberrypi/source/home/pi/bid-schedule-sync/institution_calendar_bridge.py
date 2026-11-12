#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기관 공식 산출물을 Google Calendar 표준 입찰 이벤트로 연결한다.

기본 동작은 읽기 전용 계획 출력이다. Calendar 쓰기는 --apply-calendar를
명시한 경우에만 수행한다. Python 3.7 호환.
"""

import argparse
import ast
import glob
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

MAIN_CALENDAR = "redacted@example.invalid"
LH_CALENDAR = "redacted@example.invalid"
CREDENTIAL = "/home/pi/n_data/credentials/google_calendar_service_account.json"
PLAN_FILE = Path("/home/pi/bid-schedule-sync/staging_calendar_plan.json")


def text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def dt_value(value):
    value = text(value).replace("/", "-")
    match = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", value)
    if not match:
        return ""
    parts = [int(item or 0) for item in match.groups()]
    return "%04d-%02d-%02d %02d:%02d:%02d" % tuple(parts)


def latest(pattern):
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def agreement_status(deadline, method, current_status=""):
    if dt_value(deadline):
        return "공식 원문 확인"
    joined = "%s %s" % (text(method), text(current_status))
    if re.search(r"해당\s*(?:사항\s*)?없음|불허|공동수급불허|공동도급 해당없음|아니오", joined):
        return "공동도급 해당없음"
    if re.search(r"공동|허용|분담|이행", joined):
        return "공식 원문에서 마감 미확인"
    return "원문 확인 실패"


def next_action(status, value=""):
    if text(value) and text(value) not in ("확인 필요",):
        return text(value)
    if status == "공식 원문 확인":
        return "공식 협정마감 전 협정서 제출 여부 확인"
    if status == "공동도급 해당없음":
        return "입찰 참가조건과 투찰일정 확인"
    if status == "공식 원문에서 마감 미확인":
        return "공식 상세화면 또는 공고문에서 협정 제출 시각 재확인"
    return "공식 원문 접근·첨부 선택을 재시도하고 협정 대상 여부 확인"


def standard(source, bid_no, name, start, end, deadline="", status="", **kwargs):
    status = status or agreement_status(deadline, kwargs.get("method", ""))
    return {
        "기관": source,
        "calendar_id": kwargs.get("calendar_id", MAIN_CALENDAR),
        "공고번호": text(bid_no),
        "공고명": text(name),
        "기초금액": text(kwargs.get("amount", "")),
        "하한율": text(kwargs.get("rate", "")),
        "지역": text(kwargs.get("region", "")),
        "면허·첨부서류": text(kwargs.get("license_doc", "")),
        "입찰개시일시": dt_value(start),
        "입찰마감일시": dt_value(end),
        "협정마감일시": dt_value(deadline),
        "협정확인상태": status,
        "다음행동": next_action(status, kwargs.get("action", "")),
        "발주기관": text(kwargs.get("buyer", source)),
        "입찰시스템": text(kwargs.get("system", source)),
        "상세URL": text(kwargs.get("url", "")),
        "협정정보출처": text(kwargs.get("agreement_source", "")),
    }


def calendar_service(write=False):
    scope = "https://www.googleapis.com/auth/calendar" if write else "https://www.googleapis.com/auth/calendar.readonly"
    creds = service_account.Credentials.from_service_account_file(CREDENTIAL, scopes=[scope])
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_events(service, calendar_id):
    events = []
    token = None
    while True:
        response = service.events().list(
            calendarId=calendar_id,
            timeMin="2026-01-01T00:00:00+09:00",
            timeMax="2027-01-01T00:00:00+09:00",
            singleEvents=True,
            maxResults=2500,
            pageToken=token,
        ).execute()
        events.extend(response.get("items", []))
        token = response.get("nextPageToken")
        if not token:
            return events


def load_lh():
    sys.path.insert(0, "/home/pi/seri_Alarm_Server6/lh")
    from lh_fetch import LHCrawler
    from lh_parser import LHParser

    service = calendar_service(False)
    crawler = LHCrawler()
    records = []
    for event in list_events(service, LH_CALENDAR):
        combined = "%s\n%s" % (event.get("summary", ""), event.get("description", ""))
        match = re.search(r"공고번호\s*[:：]\s*(26\d{5})", combined) or re.search(r"\b(26\d{5})\b", combined)
        if not match:
            continue
        bid_no = match.group(1)
        official = None
        for emergency in ("Y", "N"):
            try:
                raw = crawler.fetch_detail({"notice_no": bid_no, "degree": "00", "job_gb": "10", "emergency": emergency})
                if raw:
                    official = LHParser.normalize(raw)
                    break
            except Exception:
                pass
        if not official:
            records.append(standard("LH", bid_no, event.get("summary", ""), "", "", status="원문 확인 실패", calendar_id=LH_CALENDAR))
            continue
        method = official.get("공동수급협정서 접수/구성 방식", "")
        deadline = official.get("공동수급협정서접수마감일시", "")
        records.append(standard(
            "LH", bid_no, official.get("입찰공고건명", ""),
            official.get("입찰서접수개시일시", ""), official.get("입찰서접수마감일시", ""), deadline,
            method=method, calendar_id=LH_CALENDAR,
            amount=official.get("기초금액", ""), region=" ".join(filter(None, [official.get("참가지역%d" % i, "") for i in range(1, 5)])),
            license_doc=official.get("요구면허", "") or official.get("업종유형", ""),
            agreement_source="LH 공식 상세화면 공동수급협정서접수마감일시",
            system="LH e-Bid",
        ))
    return records


def load_kepco():
    source_file = latest("/mnt/vol1/bid/bid_elec/KEPCO_SRM_공사공고_LATEST.xlsx")
    rows = pd.read_excel(source_file).fillna("").to_dict("records") if source_file else []
    return [standard(
        "한전 SRM", row.get("공고번호"), row.get("공고명"), row.get("입찰시작일시"), row.get("입찰마감일시"), row.get("협정마감일시"),
        status=text(row.get("협정확인상태")), amount=row.get("기초금액"), region=row.get("대표지역"),
        license_doc=row.get("공고업종명"), buyer=row.get("발주기관"), url=row.get("detail_url"),
        agreement_source=row.get("협정정보출처"), action=row.get("다음행동"), method=row.get("공동수급방식"),
    ) for row in rows]


def load_nr():
    report_file = latest("/mnt/vol1/bid/bid-nr/report/*.xlsx")
    rows = pd.read_excel(report_file).fillna("").to_dict("records") if report_file else []
    records = []
    official_schedule = {
        "2026-01-000133-00": ("2026-08-07 09:00", "2026-08-14 10:00"),
        "2026-01-000123-00": ("2026-07-23 09:00", "2026-07-30 10:00"),
        "2026-01-000121-00": ("2026-07-20 09:00", "2026-07-27 10:00"),
    }
    for row in rows:
        schedule = official_schedule.get(text(row.get("공고번호")), ("", ""))
        raw_status = text(row.get("협정마감확인상태"))
        status = "공식 원문 확인" if text(row.get("협정마감일시")) else "원문 확인 실패"
        if "명시없음" in raw_status:
            status = "공식 원문에서 마감 미확인"
        records.append(standard(
            "국가철도공단", row.get("공고번호"), row.get("공고명"), schedule[0], schedule[1], row.get("협정마감일시"), status=status,
            amount=row.get("설계금액"), region=row.get("공동도급지역") or row.get("참가지역"),
            license_doc=row.get("공종코드"), url=row.get("상세URL"), agreement_source=(row.get("협정마감출처") or "국가철도공단 공식 입찰공고문 6.2 입찰서 제출기간"),
        ))
    return records


# EXROAD_CALENDAR_REGION_SCOPE_V1

def load_exroad():

    source_file = latest(

        "/mnt/vol1/bid/exroad/target/"

        "exroad_target_*.xlsx"

    )



    rows = (

        pd.read_excel(

            source_file,

            dtype=str,

        ).fillna("").to_dict("records")

        if source_file

        else []

    )



    records = []



    for row in rows:

        raw = row.get("raw_text", {})



        try:

            raw = (

                ast.literal_eval(raw)

                if isinstance(raw, str)

                else raw

            )

        except Exception:

            raw = {}



        bid_no = text(row.get("bid_no"))



        official_start = text(

            row.get("시작일시")

            or row.get("bid_start_time")

            or row.get("bid_start_dt")

            or raw.get("bid_start_dt", "")

        )



        official_end = text(

            row.get("close_time")

            or row.get("bid_end_dt")

            or raw.get("bid_end_dt", "")

        )



        participation_scope = text(

            row.get("participation_scope")

        ).upper()

        participation_region = text(

            row.get("participation_region")

        )



        if participation_scope == "NATIONWIDE":

            calendar_region = "전국"

        elif participation_scope == "LOCAL":

            calendar_region = participation_region

        else:

            calendar_region = ""



        agreement_deadline = text(

            row.get("agreement_deadline")

        )

        joint_rate = text(row.get("joint_rate"))

        joint_method = text(row.get("joint_method"))

        joint_member_rate = text(

            row.get("joint_member_min_rate")

        )



        has_joint_contract = bool(

            agreement_deadline

            or joint_rate

            or joint_method

            or joint_member_rate

        )



        if has_joint_contract:

            joint_region = text(

                row.get("joint_region")

            )

            official_status = text(

                row.get("agreement_status")

            ) or "한국도로공사 공식 상세화면 확인"

        else:

            joint_region = ""

            joint_rate = ""

            joint_method = ""

            joint_member_rate = ""

            agreement_deadline = ""

            official_status = "공동도급 해당없음"



        records.append(

            standard(

                "한국도로공사",

                bid_no,

                row.get("bid_name"),

                official_start,

                official_end,

                agreement_deadline,

                status=official_status,

                amount=row.get("amount"),

                region=calendar_region,

                license_doc=row.get("license"),

                agreement_source=(

                    row.get("document_text_path")

                    or row.get("document_path")

                    or ""

                ),

                system="한국도로공사 전자조달",

            )

        )



        records[-1]["공동도급지역"] = joint_region

        records[-1]["공동도급비율"] = joint_rate

        records[-1]["공동도급방식"] = joint_method

        records[-1][

            "구성원최소지분율"

        ] = joint_member_rate



    return records





def load_kwater():
    source_file = latest("/mnt/vol1/bid/bid-water/debug/filtered_rows_*.json")
    rows = json.load(open(source_file, encoding="utf-8")) if source_file else []
    records = []
    for row in rows:
        original = text(row.get("원문요약"))
        method = "공동계약 허용" if "공동계약허용여부 공동" in original else "공동계약 불허" if "공동계약허용여부 단독" in original else ""
        amount_match = re.search(r"발주금액\s+([\d,]+)\s*원", original)
        official_amount = amount_match.group(1) if amount_match else (row.get("기초금액") or row.get("발주금액"))
        records.append(standard(
            "K-water", row.get("공고번호"), row.get("공고명"), row.get("시작일시"), row.get("입찰마감일시"), "",
            method=method, amount=official_amount, region=row.get("지역제한") or row.get("대표지역"),
            license_doc=row.get("공고업종명"), buyer=row.get("수요기관"), url=row.get("상세링크"),
            agreement_source="K-water 공식 입찰공고 상세화면", system="K-water 전자조달",
        ))
    return records


def description(record):
    order = ["공고번호", "공고명", "기초금액", "하한율", "지역", "공동도급지역", "공동도급비율", "공동도급방식", "구성원최소지분율", "면허·첨부서류", "입찰개시일시", "입찰마감일시", "협정마감일시", "협정확인상태", "다음행동", "발주기관", "입찰시스템", "상세URL", "협정정보출처"]
    return "\n".join("%s : %s" % (key, record.get(key, "")) for key in order)


def event_body(record):
    start = datetime.strptime(record["입찰개시일시"], "%Y-%m-%d %H:%M:%S")
    return {
        "summary": "[입찰개시] [%s] %s" % (record["기관"], record["공고명"]),
        "description": description(record),
        # date=None removes an existing all-day date when patching it to dateTime.
        "start": {"date": None, "dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Seoul"},
        "end": {"date": None, "dateTime": (start + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Seoul"},
        "extendedProperties": {"private": {"bid_no": record["공고번호"], "source": record["기관"]}},
    }


def _event_bid_no(event):

    private = (

        event.get("extendedProperties", {})

        .get("private", {})

    )

    value = text(private.get("bid_no"))

    if value:

        return value



    event_description = (

        event.get("description", "") or ""

    )

    match = re.search(

        r"(?:^|\n)공고번호\s*[:：]\s*([^\n]+)",

        event_description,

    )

    return match.group(1).strip() if match else ""





def _event_is_same(event, record):

    desired = event_body(record)



    current_start = (

        event.get("start", {}).get("dateTime", "") or ""

    )[:19]

    current_end = (

        event.get("end", {}).get("dateTime", "") or ""

    )[:19]

    desired_start = (

        desired.get("start", {}).get("dateTime", "") or ""

    )[:19]

    desired_end = (

        desired.get("end", {}).get("dateTime", "") or ""

    )[:19]



    current_private = (

        event.get("extendedProperties", {})

        .get("private", {})

    )

    desired_private = (

        desired.get("extendedProperties", {})

        .get("private", {})

    )



    return all(

        (

            event.get("summary", "")

                == desired["summary"],

            (event.get("description", "") or "")

                == desired["description"],

            current_start == desired_start,

            current_end == desired_end,

            text(current_private.get("bid_no"))

                == text(desired_private.get("bid_no")),

            text(current_private.get("source"))

                == text(desired_private.get("source")),

        )

    )





def make_plan(records, apply_calendar=False):

    unique_records = []

    seen_record_keys = set()



    for record in records:

        record_key = (

            record.get("calendar_id", ""),

            record.get("기관", ""),

            record.get("공고번호", ""),

        )

        if record_key in seen_record_keys:

            continue

        seen_record_keys.add(record_key)

        unique_records.append(record)



    records = unique_records

    read_service = calendar_service(False)

    by_calendar = {}



    for calendar_id in sorted(

        set(

            record["calendar_id"]

            for record in records

        )

    ):

        by_calendar[calendar_id] = list_events(

            read_service,

            calendar_id,

        )



    plan = []



    for record in records:

        if (

            not record["공고번호"]

            or not record["입찰개시일시"]

            or not record["입찰마감일시"]

        ):

            item = dict(record)

            item.update(

                {

                    "action": "exclude",

                    "reason":

                        "공식 입찰개시·마감일시 미확인",

                }

            )

            plan.append(item)

            continue



        found = [

            event

            for event in by_calendar[

                record["calendar_id"]

            ]

            if _event_bid_no(event)

                == record["공고번호"]

        ]



        item = dict(record)



        if found:

            primary = found[0]

            existing_description = (

                primary.get("description", "") or ""

            )

            existing_action = re.search(

                r"(?:^|\n)다음행동\s*[:：]\s*([^\n]+)",

                existing_description,

            )



            if (

                record.get("기관")

                    != "한국도로공사"

                and existing_action

                and existing_action.group(1).strip()

            ):

                item["다음행동"] = (

                    existing_action.group(1).strip()

                )



            action = (

                "skip"

                if _event_is_same(primary, item)

                else "update"

            )

            event_id = primary.get("id", "")

            duplicate_event_ids = [

                event.get("id", "")

                for event in found[1:]

                if event.get("id", "")

            ]

        else:

            action = "create"

            event_id = ""

            duplicate_event_ids = []



        item.update(

            {

                "action": action,

                "event_id": event_id,

                "duplicate_matches":

                    max(0, len(found) - 1),

                "duplicate_event_ids":

                    duplicate_event_ids,

            }

        )

        plan.append(item)



    if apply_calendar:

        write_service = calendar_service(True)



        for item in plan:

            if item["action"] == "create":

                created = (

                    write_service.events()

                    .insert(

                        calendarId=item["calendar_id"],

                        body=event_body(item),

                        sendUpdates="none",

                    )

                    .execute()

                )

                by_calendar[

                    item["calendar_id"]

                ].append(created)



            elif item["action"] == "update":

                (

                    write_service.events()

                    .patch(

                        calendarId=item["calendar_id"],

                        eventId=item["event_id"],

                        body=event_body(item),

                        sendUpdates="none",

                    )

                    .execute()

                )



    return plan




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-send", action="store_true", help="Calendar를 쓰지 않고 계획만 생성")
    parser.add_argument("--apply-calendar", action="store_true", help="승인 후 Calendar 생성·갱신")
    args = parser.parse_args()
    if args.apply_calendar and args.no_send:
        parser.error("--no-send와 --apply-calendar는 함께 사용할 수 없습니다")
    if not args.apply_calendar:
        args.no_send = True
    records = load_lh() + load_kepco() + load_nr() + load_exroad() + load_kwater()
    plan = make_plan(records, apply_calendar=args.apply_calendar)
    payload = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "calendar_write": bool(args.apply_calendar), "items": plan}
    PLAN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
