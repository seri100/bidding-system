
#!/usr/bin/env python3

# -*- coding: utf-8 -*-


from lh_notice_doc import calendar_notice_condition_lines

import json

import os

from pathlib import Path

from datetime import datetime, timedelta


from googleapiclient.discovery import build
from google.oauth2 import service_account


BASE_DIR = Path(__file__).resolve().parent

FAIL_LOG = BASE_DIR / "logs" / "lh_calendar_failed.jsonl"


# Google Calendar ID for LH bid calendar

CALENDAR_ID = os.environ.get(
    "LH_GCAL_CALENDAR_ID",
    "redacted@example.invalid",
)


SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "/home/pi/n_data/credentials/google_calendar_service_account.json"

def _log_fail(row, err):

    try:

        FAIL_LOG.parent.mkdir(parents=True, exist_ok=True)

        data = {

            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "bid_no": row.get("공고번호"),

            "name": row.get("입찰공고건명"),

            "error": str(err),

        }

        with FAIL_LOG.open("a", encoding="utf-8") as f:

            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    except Exception:

        pass


def _build_service():


    """

    Build Google Calendar service using service account credentials.

    """


    creds = service_account.Credentials.from_service_account_file(

        SERVICE_ACCOUNT_FILE,

        scopes=SCOPES,

    )


    return build("calendar", "v3", credentials=creds)


def _parse_dt(s):

    s = str(s or "").strip()

    if not s:

        return None


    fmts = [

        "%Y/%m/%d %H:%M",

        "%Y-%m-%d %H:%M",

        "%Y.%m.%d %H:%M",

        "%Y/%m/%d %H:%M:%S",

        "%Y-%m-%d %H:%M:%S",

    ]


    for fmt in fmts:

        try:

            return datetime.strptime(s, fmt)

        except Exception:

            pass


    return None


def _pick(row, *names):

    for name in names:

        v = row.get(name)

        if v not in (None, ""):

            return str(v).strip()

    return ""


def sync_lh_calendar_row(row, service=None, log=None):

    bid_no = _pick(row, "공고번호", "notice_no", "bid_no")

    name = _pick(row, "입찰공고건명", "공고명", "공사명", "name")


    close_s = _pick(

        row,

        "입찰서접수마감일시",

        "입찰마감일시",

        "투찰마감일시",

        "마감일시",

    )


    start_dt = _parse_dt(close_s)


    if not bid_no:

        if log:

            log("[LH_GCAL_SKIP] no bid_no")

        return False


    if not start_dt:

        if log:

            log("[LH_GCAL_SKIP] no deadline bid_no={} close={}".format(bid_no, close_s))

        return False


    if not name:

        name = "LH 입찰공고"


    if service is None:

        service = _build_service()


    day_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    day_end = day_start + timedelta(days=1)


    # 중복 방지: 같은 날 같은 공고번호가 있으면 skip

    found = service.events().list(

        calendarId=CALENDAR_ID,

        timeMin=day_start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),

        timeMax=day_end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),

        q=bid_no,

        singleEvents=True,

        orderBy="startTime",

    ).execute().get("items", [])


    if found:

        if log:

            log("[LH_GCAL_SKIP] already exists bid_no={}".format(bid_no))

        return True


    end_dt = start_dt + timedelta(minutes=30)


    summary = "[LH] {}".format(name)


    desc_lines = [

        "REDACTED_PRIVATE_VALUE",

        "공고번호 : {}".format(bid_no),

        "업종유형 : {}".format(_pick(row, "업종유형", "업종")),

        "입찰공고건명 : {}".format(name),

        "기초금액 : {}".format(_pick(row, "기초금액")),

        "지역제한 : {}".format(_pick(row, "지역제한") or "없음"),

        "지역의무 : {}".format(_pick(row, "지역의무") or "없음"),

        "입찰서접수개시일시 : {}".format(_pick(row, "입찰서접수개시일시")),

        "입찰서접수마감일시 : {}".format(close_s),

    ]


    desc_lines.extend(calendar_notice_condition_lines(row))

    event = {

        "summary": summary,

        "description": "\n".join(desc_lines),

        "start": {

            "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),

            "timeZone": "Asia/Seoul",

        },

        "end": {

            "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),

            "timeZone": "Asia/Seoul",

        },


        "reminders": {

            "useDefault": False,

            "overrides": [

                {"method": "popup", "minutes": 60},

                {"method": "popup", "minutes": 1440},

            ],

        },

    }


    created = service.events().insert(

        calendarId=CALENDAR_ID,

        body=event,


    ).execute()


    if log:

        log("[LH_GCAL_OK] bid_no={} {}".format(bid_no, created.get("htmlLink", "")))


    return True


def sync_lh_calendar_rows(rows, log=None):

    service = _build_service()

    ok_cnt = 0

    fail_cnt = 0


    for row in rows:

        try:

            if sync_lh_calendar_row(row, service=service, log=log):

                ok_cnt += 1

            else:

                fail_cnt += 1

        except Exception as e:

            fail_cnt += 1

            _log_fail(row, e)

            if log:

                log("[LH_GCAL_ERR] bid_no={} err={}".format(row.get("공고번호"), e))


    if log:

        log("[LH_GCAL_DONE] ok={} fail={}".format(ok_cnt, fail_cnt))


    return ok_cnt


# __LH_GCAL_OPEN_DATE_V2_BEGIN__
from datetime import datetime as _LHDateTime
from datetime import timedelta as _LHTimedelta
import os as _lh_os


def _lh_gcal_text(value):
    if value is None:
        return ""

    return str(value).strip()


def _lh_gcal_first(row, keys, default="미확인"):
    for key in keys:
        value = _lh_gcal_text(
            row.get(key)
        )

        if value:
            return value

    return default


def _lh_gcal_parse_datetime(value):
    text = _lh_gcal_text(value)

    if not text:
        return None

    for fmt in (
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
    ):
        try:
            return _LHDateTime.strptime(
                text,
                fmt,
            )

        except ValueError:
            pass

    return None


def _lh_gcal_calendar_id():
    for name in (
        "GCAL_CALENDAR_ID",
        "CALENDAR_ID",
        "GOOGLE_CALENDAR_ID",
        "LH_CALENDAR_ID",
    ):
        value = _lh_gcal_text(
            globals().get(name)
        )

        if value:
            return value

    value = _lh_gcal_text(
        _lh_os.environ.get(
            "LH_GCAL_CALENDAR_ID"
        )
    )

    if value:
        return value

    raise RuntimeError(
        "LH Google Calendar ID를 찾지 못했습니다"
    )


def _lh_gcal_timezone():
    for name in (
        "GCAL_TIMEZONE",
        "TIMEZONE",
        "GOOGLE_TIMEZONE",
    ):
        value = _lh_gcal_text(
            globals().get(name)
        )

        if value:
            return value

    return "Asia/Seoul"


def _lh_gcal_service():
    for name in (
        "get_lh_calendar_service",
        "get_calendar_service",
        "get_gcal_service",
        "build_service",
        "get_service",
        "_get_service",
    ):
        func = globals().get(name)

        if (
            callable(func)
            and func is not _lh_gcal_service
        ):
            try:
                service = func()

            except TypeError:
                continue

            if service is not None:
                return service

    service_file = ""

    for name in (
        "GCAL_SERVICE_ACCOUNT_FILE",
        "SERVICE_ACCOUNT_FILE",
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "SERVICE_ACCOUNT_JSON",
        "CREDENTIALS_FILE",
        "CREDENTIAL_FILE",
    ):
        value = _lh_gcal_text(
            globals().get(name)
        )

        if value:
            service_file = value
            break

    if not service_file:
        service_file = _lh_gcal_text(
            _lh_os.environ.get(
                "LH_GCAL_SERVICE_ACCOUNT_FILE"
            )
        )

    if not service_file:
        for candidate in (
            "/home/pi/n_data/credentials/"
            "google_calendar_service_account.json",
            "/home/pi/seri_Alarm_Server6/"
            "credentials/google_calendar_service_account.json",
            "/home/pi/seri_Alarm_Server6/lh/"
            "credentials/google_calendar_service_account.json",
        ):
            if _lh_os.path.exists(candidate):
                service_file = candidate
                break

    if not service_file:
        raise RuntimeError(
            "LH Google 서비스계정 파일 경로를 찾지 못했습니다"
        )

    from google.oauth2.service_account import (
        Credentials as _LHCredentials,
    )

    from googleapiclient.discovery import (
        build as _lh_google_build,
    )

    credentials = (
        _LHCredentials.from_service_account_file(
            service_file,
            scopes=[
                "https://www.googleapis.com/auth/calendar"
            ],
        )
    )

    return _lh_google_build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def _lh_gcal_regions(row):
    regions = []

    for key in (
        "참가지역1",
        "참가지역2",
        "참가지역3",
        "참가지역4",
        "참가지역",
    ):
        value = _lh_gcal_text(
            row.get(key)
        )

        if value and value not in regions:
            regions.append(value)

    return (
        ", ".join(regions)
        if regions
        else "없음"
    )


def build_lh_calendar_event(row):
    bid_no = _lh_gcal_first(
        row,
        (
            "공고번호",
            "bidNtceNo",
            "bid_no",
        ),
        default="",
    )

    title = _lh_gcal_first(
        row,
        (
            "입찰공고건명",
            "공고명",
            "title",
        ),
        default="LH 입찰공고",
    )

    open_text = _lh_gcal_first(
        row,
        (
            "입찰서접수개시일시",
            "입찰개시일시",
            "입찰개시",
        ),
        default="",
    )

    open_dt = _lh_gcal_parse_datetime(
        open_text
    )

    if open_dt is None:
        raise ValueError(
            "입찰서접수개시일시를 해석할 수 없습니다: {}".format(
                open_text
            )
        )

    close_text = _lh_gcal_first(
        row,
        (
            "입찰서접수마감일시",
            "입찰마감일시",
            "입찰마감",
        ),
    )

    agreement_text = _lh_gcal_first(row, ("공동수급협정서접수마감일시", "협정마감일시"), default="")
    agreement_method = _lh_gcal_first(row, ("공동수급협정서 접수/구성 방식", "공동수급방식"), default="")

    base_amount = _lh_gcal_first(
        row,
        (
            "기초금액",
            "설계가격",
        ),
    )

    a_amount = _lh_gcal_first(
        row,
        (
            "가격점수제외금액(A)",
            "가격점수제외금액",
            "가격점수 제외금액(A)",
            "A값",
        ),
    )

    exclusion_amount = _lh_gcal_first(
        row,
        (
            "낙찰제외기준금액",
            "낙찰 제외 기준금액",
            "낙찰제외 기준금액",
        ),
    )

    description = "\n".join([
        "REDACTED_PRIVATE_VALUE",
        "공고번호 : {}".format(
            bid_no or "미확인"
        ),
        "업종유형 : {}".format(
            _lh_gcal_first(
                row,
                (
                    "업종유형",
                    "업종",
                ),
            )
        ),
        "입찰공고건명 : {}".format(
            title
        ),
        "기초금액 : {}".format(
            base_amount
        ),
        "가격점수제외금액(A) : {}".format(
            a_amount
        ),
        "낙찰제외기준금액 : {}".format(
            exclusion_amount
        ),
        "공동도급 협정지역 : {}".format(
            _lh_gcal_regions(row)
        ),
        "협정마감일시 : {}".format(
            agreement_text
        ),
        "공동수급방식 : {}".format(
            agreement_method
        ),
        "입찰서접수개시일시 : {}".format(
            open_text
        ),
        "입찰서접수마감일시 : {}".format(
            close_text
        ),
    ])

    condition_lines = calendar_notice_condition_lines(row)
    if condition_lines:
        description += "\n\n[공고문 제한 및 실적평가]\n" + "\n".join(condition_lines)

    end_dt = open_dt + _LHTimedelta(
        minutes=30
    )

    timezone = _lh_gcal_timezone()

    return {
        "summary": "[LH] {}".format(
            title
        ),
        "description": description,
        "start": {
            "dateTime": open_dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "timeZone": timezone,
        },
        "extendedProperties": {
            "private": {
                "lh_bid_no": bid_no,
                "lh_event_basis": (
                    "입찰서접수개시일시"
                ),
            }
        },
    }


def _lh_gcal_rfc3339(value):
    return value.strftime(
        "%Y-%m-%dT%H:%M:%S+09:00"
    )


def _lh_gcal_find_existing(
    service,
    bid_no,
    open_dt,
    close_dt,
):
    search_start = open_dt
    search_end = open_dt

    if close_dt is not None:
        search_start = min(
            search_start,
            close_dt,
        )

        search_end = max(
            search_end,
            close_dt,
        )

    common = {
        "calendarId": _lh_gcal_calendar_id(),
        "timeMin": _lh_gcal_rfc3339(
            search_start
            - _LHTimedelta(days=30)
        ),
        "timeMax": _lh_gcal_rfc3339(
            search_end
            + _LHTimedelta(days=30)
        ),
        "singleEvents": True,
        "showDeleted": False,
        "maxResults": 50,
    }

    if not bid_no:
        return None

    response = service.events().list(
        privateExtendedProperty=(
            "lh_bid_no={}".format(
                bid_no
            )
        ),
        **common
    ).execute()

    items = response.get(
        "items",
        [],
    )

    if items:
        return items[0]

    response = service.events().list(
        q=bid_no,
        **common
    ).execute()

    for item in response.get(
        "items",
        [],
    ):
        description = _lh_gcal_text(
            item.get("description")
        )

        summary = _lh_gcal_text(
            item.get("summary")
        )

        if (
            bid_no in description
            or bid_no in summary
        ):
            return item

    return None


def sync_lh_calendar_rows(
    rows,
    log=print,
):
    service = _lh_gcal_service()
    calendar_id = _lh_gcal_calendar_id()

    created = 0
    updated = 0
    skipped = 0
    failed = 0

    for row in rows or []:
        if not isinstance(row, dict):
            skipped += 1
            continue

        bid_no = _lh_gcal_first(
            row,
            (
                "공고번호",
                "bidNtceNo",
                "bid_no",
            ),
            default="",
        )

        open_text = _lh_gcal_first(
            row,
            (
                "입찰서접수개시일시",
                "입찰개시일시",
                "입찰개시",
            ),
            default="",
        )

        open_dt = _lh_gcal_parse_datetime(
            open_text
        )

        if open_dt is None:
            skipped += 1

            log(
                "[LH_GCAL][SKIP] "
                "bid={} invalid open datetime={}".format(
                    bid_no or "unknown",
                    open_text,
                )
            )

            continue

        close_dt = _lh_gcal_parse_datetime(
            _lh_gcal_first(
                row,
                (
                    "입찰서접수마감일시",
                    "입찰마감일시",
                    "입찰마감",
                ),
                default="",
            )
        )

        try:
            body = build_lh_calendar_event(
                row
            )

            existing = _lh_gcal_find_existing(
                service,
                bid_no,
                open_dt,
                close_dt,
            )

            if existing:
                event = service.events().update(
                    calendarId=calendar_id,
                    eventId=existing["id"],
                    body=body,
                ).execute()

                updated += 1

                log(
                    "[LH_GCAL][UPDATE] "
                    "bid={} start={} event_id={}".format(
                        bid_no,
                        open_text,
                        event.get("id", ""),
                    )
                )

            else:
                event = service.events().insert(
                    calendarId=calendar_id,
                    body=body,
                ).execute()

                created += 1

                log(
                    "[LH_GCAL][CREATE] "
                    "bid={} start={} event_id={}".format(
                        bid_no,
                        open_text,
                        event.get("id", ""),
                    )
                )

        except Exception as exc:
            failed += 1

            log(
                "[LH_GCAL][ERROR] "
                "bid={} type={} message={}".format(
                    bid_no or "unknown",
                    type(exc).__name__,
                    exc,
                )
            )

    result = {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }

    log(
        "[LH_GCAL][RESULT] "
        "created={created} updated={updated} "
        "skipped={skipped} failed={failed}".format(
            **result
        )
    )

    return result
# __LH_GCAL_OPEN_DATE_V2_END__
