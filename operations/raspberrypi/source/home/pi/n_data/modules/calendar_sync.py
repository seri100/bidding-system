
import html

import re

from datetime import datetime, timedelta



from google.oauth2.service_account import Credentials

from googleapiclient.discovery import build

from googleapiclient.errors import HttpError





GCAL_SYNC_ENABLED = True

GCAL_SERVICE_ACCOUNT_FILE = "/home/pi/n_data/credentials/google_calendar_service_account.json"

GCAL_CALENDAR_ID = "redacted@example.invalid"

GCAL_TIMEZONE = "Asia/Seoul"

GCAL_DEFAULT_DURATION_MINUTES = 60



# 동기화 기준 금액: 10억

GCAL_PRICE_LIMIT_WON = 1_000_000_000



# 10억 미만이어도 동기화할 지역

GCAL_ALLOWED_REGIONS = [

    "충북",

    "충청북도",

    "충북청주",

    "충북 청주",

    "충청북도청주",

    "충청북도 청주",

    "청주",

    "청주시",

    "세종",

    "세종시",

    "세종특별자치시",

]



# 별도 관리 대상: 무조건 캘린더 자동 동기화 제외

GCAL_EXCLUDED_LH_KEYWORDS = [

    "한국토지주택공사",

    "한국토지주택",

    "토지주택",

    "LH입찰공고",

    "[LH]",

    "【LH】",

]



GCAL_PRICE_LABELS = [

    "추정가격",

    "기초금액",

    "예정가격",

]



GCAL_REGION_LABELS = [

    "참가가능지역",

    "입찰참가가능지역",

    "지역제한",

    "지역제한명",

    "공동도급지역",

    "참가지역",

    "공고지역",

    "공고범위",

    "공사현장",

    "현장",

]



GCAL_CONTEXT_LABELS = [

    "기관구분",

    "공고명",

    "입찰공고명",

    "입찰공고건명",

    "발주기관",

    "기관명",

    "업종",

    "업종유형",

]



GCAL_ALL_LABELS = (

    GCAL_PRICE_LABELS

    + GCAL_REGION_LABELS

    + GCAL_CONTEXT_LABELS

    + [

        "공고번호",

        "입찰마감일시",

        "입찰서접수개시일시",

        "입찰서접수마감일시",

        "개찰일시",

        "낙찰방법",

        "상세URL",

    ]

)



_gcal_service_cache = None





def get_gcal_service():

    global _gcal_service_cache



    if _gcal_service_cache is not None:

        return _gcal_service_cache



    creds = Credentials.from_service_account_file(

        GCAL_SERVICE_ACCOUNT_FILE,

        scopes=["https://www.googleapis.com/auth/calendar"],

    )



    _gcal_service_cache = build("calendar", "v3", credentials=creds)

    return _gcal_service_cache





def _extract_value(text: str, pattern: str) -> str:

    m = re.search(pattern, text, re.MULTILINE)

    return m.group(1).strip() if m else ""





def _to_24h(ampm: str, hour: int) -> int:

    if ampm == "오전":

        return 0 if hour == 12 else hour

    if ampm == "오후":

        return 12 if hour == 12 else hour + 12

    return hour





def _find_schedule_line(text: str) -> str:

    for line in text.splitlines():

        s = line.strip()

        if "월" in s and "일" in s and "~" in s and ("오전" in s or "오후" in s):

            return s

    return ""





def _parse_korean_schedule_line(line: str, fallback_year: int = None):

    if fallback_year is None:

        fallback_year = datetime.now().year



    s = line.strip()

    s = s.replace("⋅", " ")

    s = re.sub(r"\([^)]*\)", " ", s)

    s = re.sub(r"\s+", " ", s).strip()



    m = re.search(

        r"(\d{1,2})월\s*(\d{1,2})일\s*"

        r"(오전|오후)\s*(\d{1,2}):(\d{2})\s*~\s*"

        r"((오전|오후)\s*)?(\d{1,2}):(\d{2})",

        s,

    )



    if not m:

        raise ValueError(f"일정 시간 줄 파싱 실패: {line} -> 정리후: {s}")



    month = int(m.group(1))

    day = int(m.group(2))



    start_ampm = m.group(3)

    start_hour = int(m.group(4))

    start_min = int(m.group(5))



    end_ampm = m.group(7) if m.group(7) else start_ampm

    end_hour = int(m.group(8))

    end_min = int(m.group(9))



    start_dt = datetime(

        fallback_year,

        month,

        day,

        _to_24h(start_ampm, start_hour),

        start_min,

    )



    end_dt = datetime(

        fallback_year,

        month,

        day,

        _to_24h(end_ampm, end_hour),

        end_min,

    )



    if end_dt <= start_dt:

        end_dt = start_dt + timedelta(minutes=GCAL_DEFAULT_DURATION_MINUTES)



    return start_dt, end_dt





def _make_event_id(source: str, notice_no: str, notice_ord: str, start_dt: datetime) -> str:

    import hashlib



    # 날짜가 바뀌어도 같은 공고를 갱신하도록 공고번호/차수만 사용한다.
    raw = f"{source}|{notice_no}|{notice_ord}"

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()



    # Google Calendar event id는 안전하게 영문 소문자/숫자만 사용

    return "bid" + digest





def parse_message_to_event(message_text: str) -> dict:

    lines = [x.strip() for x in message_text.splitlines() if x.strip()]



    if not lines:

        raise ValueError("빈 메시지입니다.")



    source = _extract_value(message_text, r"기관구분\s*:\s*(.+)")

    if not source:

        source = "g2b"



    title = _extract_value(message_text, r"공고명\s*:\s*(.+)")

    if not title:

        title = _extract_value(message_text, r"입찰공고건명\s*:\s*(.+)")



    if title:

        summary = f"[입찰개시] {title}"

    else:

        summary = lines[0]



    notice_raw = _extract_value(message_text, r"공고번호\s*:\s*(.+)")

    notice_no = notice_raw

    notice_ord = "000"



    m_no = re.search(r"([A-Z0-9]+)\s*-\s*(\d+)", notice_raw)

    if m_no:

        notice_no = m_no.group(1)

        notice_ord = m_no.group(2)



    open_dt = _extract_value(message_text, r"개찰일시\s*:\s*(.+)")



    site = _extract_value(message_text, r"공사현장\s*:\s*(.+)")

    if not site:

        site = _extract_value(message_text, r"현장\s*:\s*(.+)")

    if not site:

        site = _extract_value(message_text, r"참가지역\s*:\s*(.+)")



    fallback_year = datetime.now().year



    if open_dt:

        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", open_dt)

        if m:

            fallback_year = int(m.group(1))



    deadline_text = _extract_value(message_text, r"입찰서접수개시일시[ \t]*:[ \t]*(.+)")

    if not deadline_text:

        deadline_text = _extract_value(message_text, r"시작일시[ \t]*:[ \t]*(.+)")



    if deadline_text:

        deadline_text = deadline_text.strip().rstrip(",")



        parsed_dt = None

        for fmt in (

            "%Y-%m-%d %H:%M:%S",

            "%Y-%m-%d %H:%M",

            "%Y/%m/%d %H:%M:%S",

            "%Y/%m/%d %H:%M",

        ):

            try:

                parsed_dt = datetime.strptime(deadline_text, fmt)

                break

            except Exception:

                pass



        if parsed_dt is None:

            raise ValueError(f"지원하지 않는 입찰개시일시 형식: {deadline_text}")



        start_dt = parsed_dt

        end_dt = start_dt + timedelta(minutes=GCAL_DEFAULT_DURATION_MINUTES)



    else:

        schedule_line = _find_schedule_line(message_text)



        if not schedule_line:

            raise ValueError("일정 시간 줄 또는 입찰개시일시를 찾지 못했습니다.")



        start_dt, end_dt = _parse_korean_schedule_line(

            schedule_line,

            fallback_year,

        )



    event_id = _make_event_id(

        source,

        notice_no,

        notice_ord,

        start_dt,

    )



    return {

        "id": event_id,

        "summary": summary,

        "location": site,

        "description": message_text,

        "start_dt": start_dt,

        "end_dt": end_dt,

    }





# === GCAL 동기화 필터 시작 ===

# 최종 기준:

# 1. LH / 한국토지주택공사 / 토지주택 건은 무조건 제외

# 2. LH가 아닌 공고 중 추정가격/기초금액 10억 이상은 동기화

# 3. LH가 아닌 공고 중 충북/충북청주/청주/세종 공고는 동기화

# 4. 나머지는 제외





def _gcal_unescape_text(text) -> str:

    return html.unescape(str(text or ""))





def _gcal_normalize(text) -> str:

    text = _gcal_unescape_text(text)

    return re.sub(r"\s+", "", text)





def _gcal_contains_any(text, keywords) -> bool:

    normalized = _gcal_normalize(text)

    return any(_gcal_normalize(keyword) in normalized for keyword in keywords)





def _gcal_extract_labeled_values(text: str, labels) -> str:

    """

    아래 같은 문구에서 label 값을 추출한다.



    공동도급지역 : 대구광역시

    참가지역: 대구

    추정가격 : 132,199,000원

    기초금액: 3,288,354,000원

    발주기관 : 대구광역시교육청

    """



    text = _gcal_unescape_text(text)

    values = []



    next_label_pattern = "|".join(

        re.escape(label) + r"\s*[:：]"

        for label in GCAL_ALL_LABELS

    )



    for label in labels:

        pattern = (

            re.escape(label)

            + r"\s*[:：]\s*"

            + r"(.*?)"

            + r"(?=\s*(?:"

            + next_label_pattern

            + r")|\n|\r|\||$)"

        )



        for match in re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL):

            value = match.strip()

            if value:

                values.append(value)



    return " ".join(values).strip()





def _gcal_extract_price_won(message_text: str):

    """

    추정가격/기초금액/예정가격을 원 단위 숫자로 추출한다.

    '원' 표기가 없어도 숫자가 있으면 추출한다.

    """



    text = _gcal_unescape_text(message_text)



    for label in GCAL_PRICE_LABELS:

        pattern = re.escape(label) + r"\s*[:：]\s*([0-9][0-9,\s]*)\s*(?:원)?"

        match = re.search(pattern, text)



        if match:

            digits = re.sub(r"[^\d]", "", match.group(1))

            if digits:

                return int(digits)



    return None





def _gcal_extract_region_text(message_text: str) -> str:

    region_text = _gcal_extract_labeled_values(message_text, GCAL_REGION_LABELS)

    context_text = _gcal_extract_labeled_values(message_text, GCAL_CONTEXT_LABELS)



    # 일부 메시지는 지역 필드가 비어 있고 공고명/발주기관/본문에 지역이 들어가므로

    # 원문도 함께 검사한다.

    return f"{region_text} {context_text} {message_text}".strip()





def _gcal_is_lh_or_land_housing_notice(message_text: str) -> bool:

    """

    LH / 한국토지주택공사 / 토지주택 건은 별도 관리 대상이므로 무조건 제외한다.

    """



    text = _gcal_unescape_text(message_text)

    normalized = _gcal_normalize(text).upper()



    for keyword in GCAL_EXCLUDED_LH_KEYWORDS:

        if _gcal_normalize(keyword).upper() in normalized:

            return True



    # [LH], LH 입찰공고, LH입찰공고 등 변형 대응

    if re.search(

        r"(^|[\s\[\]【】\(\)#])LH([\]\s】\)]|입찰|$)",

        text,

        flags=re.IGNORECASE,

    ):

        return True



    return False





def _gcal_is_allowed_region_notice(message_text: str) -> bool:

    """

    10억 미만이어도 동기화할 지역:

    충북 / 충북청주 / 청주 / 세종

    """



    region_text = _gcal_extract_region_text(message_text)

    return _gcal_contains_any(region_text, GCAL_ALLOWED_REGIONS)





def gcal_sync_filter_decision(message_text: str):

    """

    반환값:

    (동기화여부: bool, 사유: str)

    """



    if _gcal_is_lh_or_land_housing_notice(message_text):

        return False, "LH/한국토지주택공사/토지주택 건 별도 관리"



    # __GCAL_ESTIMATED_PRICE_FIX_V1__
    # 추정가격이 명시되면 지역/10억 기준 판정에 우선 사용한다.
    estimated_match = re.search(
        r"^\s*추정가격\s*[:：]\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:원)?\s*$",
        message_text, re.MULTILINE
    )
    price = _gcal_extract_price_won(message_text)
    if estimated_match:
        from decimal import Decimal
        estimated_price = int(Decimal(estimated_match.group(1).replace(",", "")))
        if estimated_price > 0:
            price = estimated_price



    # __GCAL_EXPLICIT_ALLOWED_MULTI_REGION_V1__
    # Explicit eligibility including Chungbuk/Sejong takes precedence over
    # a Gyeongbuk occurrence in the site, title, or another allowed region.
    eligibility = re.findall(
        r"^\s*(?:참가가능지역|입찰참가가능지역|지역제한|지역제한명|참가지역)\s*[:：]\s*([^\r\n]*)$",
        message_text, re.MULTILINE)
    if price is not None and price < GCAL_PRICE_LIMIT_WON:
        for value in eligibility:
            if re.search(r"충청북도|충북|세종특별자치시|세종", value):
                return True, "명시된 참가가능지역에 충북/세종 포함: {:,}원".format(price)

    # __GCAL_GYEONGBUK_UNDER_1B_EXCLUDE_V1__

    # 경북/경상북도 공고는 추정가격이 10억원 미만이면

    # 충북·청주·세종 등의 허용지역 문구가 함께 있어도 최우선으로 제외한다.

    gyeongbuk_region_text = _gcal_extract_region_text(message_text)



    if (

        price is not None

        and price < GCAL_PRICE_LIMIT_WON

        and _gcal_contains_any(

            gyeongbuk_region_text,

            ("경북", "경상북도"),

        )

    ):

        return False, (

            f"경북지역 + 추정가격 10억 미만 제외: {price:,}원"

        )





    # __GCAL_NATIONWIDE_UNDER_1B_V1__

    # 명시된 참가자격만 판정한다. 공동도급지역 공란은 전국으로 보지 않는다.

    nationwide_region = ""

    for region_label in (

        "참가가능지역", "입찰참가가능지역",

        "지역제한", "지역제한명", "참가지역",

    ):

        region_match = re.search(

            r"^\s*" + re.escape(region_label)

            + r"\s*[:：]\s*([^\r\n]*)$",

            message_text,

            re.MULTILINE,

        )

        if region_match and region_match.group(1).strip():

            nationwide_region = region_match.group(1).strip()

            break



    if nationwide_region in (

        "전국", "전국가능", "전국 가능",

        "전국(지역제한없음)", "전국 (지역제한 없음)",

    ):

        return True, "전국 참가 가능 공고: 금액 하한 없음"



    if price is not None and price >= GCAL_PRICE_LIMIT_WON:

        return True, f"10억 이상 공고: {price:,}원"



    if _gcal_is_allowed_region_notice(message_text):

        if price is None:

            return True, "허용지역 공고: 충북/충북청주/청주/세종, 금액 미확인"

        return True, f"허용지역 공고: 충북/충북청주/청주/세종, {price:,}원"



    if price is None:

        return False, "금액 미확인 + 허용지역 아님"



    return False, f"10억 미만 + 허용지역 아님: {price:,}원"





def should_sync_message_to_gcal(message_text: str) -> bool:

    should_sync, _reason = gcal_sync_filter_decision(message_text)

    return should_sync





def _gcal_filter_preview(message_text: str, max_len: int = 160) -> str:

    text = _gcal_unescape_text(message_text)

    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_len]





# === GCAL 동기화 필터 끝 ===





def _is_not_found_error(error: HttpError) -> bool:

    status = getattr(getattr(error, "resp", None), "status", None)

    status_code = getattr(error, "status_code", None)



    return (

        status == 404

        or status_code == 404

        or "Not Found" in str(error)

    )





def _find_existing_notice_event_id(service, message_text: str):
    """이전 날짜기반 ID로 등록된 같은 공고를 찾아 이동/갱신한다."""
    notice_raw = _extract_value(message_text, r"공고번호\s*:\s*(.+)")
    match = re.search(r"([A-Z0-9]+)\s*-\s*(\d+)", notice_raw)
    if not match:
        return ""
    notice_no = match.group(1)
    notice_ord = match.group(2).zfill(3)
    try:
        result = service.events().list(
            calendarId=GCAL_CALENDAR_ID,
            q=notice_no,
            singleEvents=True,
            maxResults=50,
        ).execute()
        for item in result.get("items", []):
            text = "%s\n%s" % (
                item.get("summary", ""), item.get("description", "")
            )
            found = re.search(
                r"공고번호\s*:\s*" + re.escape(notice_no)
                + r"\s*-\s*(\d+)", text
            )
            if found and found.group(1).zfill(3) == notice_ord:
                return item.get("id", "")
    except Exception:
        return ""
    return ""


def _gcal_log(logger, level, message, *args):
    if not logger:
        return
    text = message % args if args else message
    method = getattr(logger, level, None)
    if callable(method):
        method(text)
    elif callable(logger):
        logger(text)


def sync_message_to_gcal(message_text: str, logger=None):

    if not GCAL_SYNC_ENABLED:

        return "disabled", "", ""

    from g2b_cancel_sync import is_cancel_message, sync_cancel_message
    if is_cancel_message(message_text):
        return sync_cancel_message(
            get_gcal_service(), GCAL_CALENDAR_ID, message_text,
            lambda text: _gcal_log(logger, "info", text))



    should_sync, filter_reason = gcal_sync_filter_decision(message_text)



    if not should_sync:

        if logger:

            _gcal_log(logger, "info",

                "[GCAL SKIP] %s: %s",

                filter_reason,

                _gcal_filter_preview(message_text),

            )

        return None



    event_data = parse_message_to_event(message_text)
    try:
        from g2b_inspection import title_for_message
        event_data["summary"] = title_for_message(event_data["summary"], message_text)
    except Exception as exc:
        if logger:
            _gcal_log(logger, "warning", "[INSPECTION_TITLE][RETRY] %s", type(exc).__name__)



    service = get_gcal_service()



    body = {

        "id": event_data["id"],

        "summary": event_data["summary"],

        "location": event_data["location"],

        "description": event_data["description"],

        "start": {

            "dateTime": event_data["start_dt"].strftime("%Y-%m-%dT%H:%M:%S"),

            "timeZone": GCAL_TIMEZONE,

        },

        "end": {

            "dateTime": event_data["end_dt"].strftime("%Y-%m-%dT%H:%M:%S"),

            "timeZone": GCAL_TIMEZONE,

        },

        "reminders": {

            "useDefault": False,

            "overrides": [

                {"method": "popup", "minutes": 60},

                {"method": "popup", "minutes": 10},

            ],

        },

    }



    try:

        try:

            existing = service.events().get(
                calendarId=GCAL_CALENDAR_ID, eventId=event_data["id"]
            ).execute()
            if is_cancel_message(existing.get("summary", "") + "\n"
                                 + existing.get("description", "")):
                return "cancel_protected", existing.get("htmlLink", ""), event_data["id"]
            updated = service.events().update(

                calendarId=GCAL_CALENDAR_ID,

                eventId=event_data["id"],

                body=body,

            ).execute()



            if logger:

                _gcal_log(logger, "info",

                    "[GCAL UPDATED] %s / %s",

                    event_data["id"],

                    filter_reason,

                )



            return (

                "updated",

                updated.get("htmlLink", ""),

                event_data["id"],

            )



        except HttpError as e:

            if _is_not_found_error(e):

                old_event_id = _find_existing_notice_event_id(
                    service, message_text
                )

                if old_event_id:
                    existing = service.events().get(
                        calendarId=GCAL_CALENDAR_ID, eventId=old_event_id
                    ).execute()
                    if is_cancel_message(existing.get("summary", "") + "\n"
                                         + existing.get("description", "")):
                        return "cancel_protected", existing.get("htmlLink", ""), old_event_id
                    update_body = dict(body)
                    update_body.pop("id", None)
                    created = service.events().update(
                        calendarId=GCAL_CALENDAR_ID,
                        eventId=old_event_id,
                        body=update_body,
                    ).execute()
                    result_state = "migrated"
                else:
                    created = service.events().insert(
                        calendarId=GCAL_CALENDAR_ID,
                        body=body,
                    ).execute()
                    result_state = "created"



                if logger:

                    _gcal_log(logger, "info",

                        "[GCAL %s] %s / %s",

                        result_state.upper(),

                        event_data["id"],

                        filter_reason,

                    )



                return (

                    result_state,

                    created.get("htmlLink", ""),

                    event_data["id"],

                )



            raise



    except Exception as e:

        if logger:

            _gcal_log(logger, "exception", f"[GCAL][ERROR] {e}")



        raise
