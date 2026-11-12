#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import os

import re

import ssl

import imaplib

import email

import hashlib

import argparse
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



from datetime import datetime, timedelta

from email.header import decode_header

from bs4 import BeautifulSoup



from google.oauth2 import service_account

from googleapiclient.discovery import build







BASE_DIR = "/home/pi/n_data/daum_mail"



# .env load

ENV_FILE = os.path.join(BASE_DIR, ".env")



if os.path.exists(ENV_FILE):



    with open(ENV_FILE, "r", encoding="utf-8") as f:



        for line in f:



            line = line.strip()



            if not line:

                continue



            if "=" not in line:

                continue



            k, v = line.split("=", 1)



            os.environ[k.strip()] = v.strip()






STATE_DIR = os.path.join(BASE_DIR, "state")

LOG_DIR = os.path.join(BASE_DIR, "logs")



os.makedirs(STATE_DIR, exist_ok=True)

os.makedirs(LOG_DIR, exist_ok=True)



SEEN_FILE = os.path.join(STATE_DIR, "seen.txt")





DAUM_USER = os.environ.get("DAUM_MAIL_USER", "redacted@example.invalid")

DAUM_PASS = os.environ.get("DAUM_MAIL_PASS", "")



IMAP_HOST = "imap.daum.net"

IMAP_PORT = 993





GCAL_CREDENTIALS = (

    "/home/pi/n_data/credentials/google_calendar_service_account.json"

)



GCAL_CALENDAR_ID = (

    "redacted@example.invalid"

)


# 공영 캘린더와 bid-daum 간 공고번호 중복 방지용
CROSS_CHECK_CALENDAR_IDS = [
    "redacted@example.invalid",
]






ALLOW_REGIONS = [

    "전국",

    "충북",

    "충청북도",

    "청주시",

    "충북 청주시",

    "세종",

    "세종시",

    "세종특별자치시",

]





WORK_KEYWORDS = [

    "기계설비",

    "기계설비공사업",

    "기계가스설비",
    "가스난방",
    "난방시설",
    "보일러",
    "세관",
    "정비 공사",

    "소방",

    "소방설비",

    "전문소방",

    "일반소방",

]





GOODS_KEYWORDS = [

    "EHP",

    "GHP",

    "냉난방",

    "냉난방기",

    "에어컨",

    "공조기",

    "히트펌프",

]





SUBJECT_KEYWORDS = [

    "맞춤메일",

    "맞춤정보",

    "공공구매",

    "판로지원",

    "입찰",

]





def log(msg):

    line = "[%s] %s" % (

        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        msg

    )



    print(line)



    with open(

        os.path.join(LOG_DIR, "daum_mail_sync.log"),

        "a",

        encoding="utf-8"

    ) as f:

        f.write(line + "\
")





def decode_mime(s):



    if not s:

        return ""



    out = ""



    for part, enc in decode_header(s):



        if isinstance(part, bytes):

            enc = (enc or "utf-8").lower().replace("_", "-")



            enc = {

                "cseuckr": "euc-kr",

                "ks-c-5601": "cp949",

                "ks_c_5601-1987": "cp949",

                "x-windows-949": "cp949",

            }.get(enc, enc)



            try:

                out += part.decode(enc, errors="ignore")

            except (LookupError, UnicodeDecodeError):

                out += part.decode("utf-8", errors="ignore")

        else:

            out += part



    return out





def load_seen():



    if not os.path.exists(SEEN_FILE):

        return set()



    with open(SEEN_FILE, "r", encoding="utf-8") as f:

        return set(x.strip() for x in f if x.strip())





def save_seen(key):



    with open(SEEN_FILE, "a", encoding="utf-8") as f:

        f.write(key + "\
")





def clean_text(s):



    return re.sub(r"\s+", " ", s or "").strip()





def parse_datetime(s):



    if not s:

        return None



    s = s.replace(".", "-")

    s = s.replace("/", "-")



    m = re.search(

        r"(20\d{2}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?::(\d{2}))?",

        s

    )



    if m:

        sec = m.group(3) or "00"

        return datetime.strptime(

            "%s %s:%s" % (m.group(1), m.group(2), sec),

            "%Y-%m-%d %H:%M:%S"

        )



    m = re.search(

        r"(\d{2}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?::(\d{2}))?",

        s

    )



    if m:

        sec = m.group(3) or "00"

        return datetime.strptime(

            "20%s %s:%s" % (m.group(1), m.group(2), sec),

            "%Y-%m-%d %H:%M:%S"

        )



    return None





def get_calendar_service():



    scopes = [

        "https://www.googleapis.com/auth/calendar"

    ]



    creds = service_account.Credentials.from_service_account_file(

        GCAL_CREDENTIALS,

        scopes=scopes

    )



    return build(

        "calendar",

        "v3",

        credentials=creds

    )





def get_email_html(msg):



    htmls = []

    texts = []



    if msg.is_multipart():



        for part in msg.walk():



            ctype = part.get_content_type()



            disp = str(part.get("Content-Disposition") or "")



            if "attachment" in disp.lower():

                continue



            payload = part.get_payload(decode=True)



            if not payload:

                continue



            charset = part.get_content_charset() or "utf-8"



            body = payload.decode(

                charset,

                errors="ignore"

            )



            if ctype == "text/html":

                htmls.append(body)



            elif ctype == "text/plain":

                texts.append(body)



    else:



        payload = msg.get_payload(decode=True)



        if payload:



            charset = msg.get_content_charset() or "utf-8"



            body = payload.decode(

                charset,

                errors="ignore"

            )



            if msg.get_content_type() == "text/html":

                htmls.append(body)

            else:

                texts.append(body)



    if htmls:

        return "\\n".join(htmls)




    return "<pre>%s</pre>" % "\\n".join(texts)






def parse_bid_items(html):



    soup = BeautifulSoup(html, "html.parser")



    items = []



    box = soup.select_one("#box_bid_summary")



    if box:



        item = {}



        rows = box.select("tr")



        for tr in rows:



            cells = tr.find_all(["th", "td"])



            for i in range(0, len(cells) - 1, 2):



                key = clean_text(

                    cells[i].get_text(" ")

                )



                val = clean_text(

                    cells[i + 1].get_text(" ")

                )



                if key:

                    item[key] = val



        if item:

            items.append(item)



    # 공공구매종합정보 viewMail 링크형 공고 직접 파싱

    for a in soup.find_all("a", href=True):

        href = a.get("href", "")

        title = clean_text(a.get_text(" "))



        if "viewMail.php" not in href:

            continue



        if not title:

            continue



        if not any(k in title for k in WORK_KEYWORDS + GOODS_KEYWORDS):

            continue



        tr = a.find_parent("tr")

        block = ""



        if tr:

            parts = []

            cur = tr

            for _ in range(0, 3):

                if not cur:

                    break

                parts.append(clean_text(cur.get_text(" ")))

                cur = cur.find_next_sibling("tr")

            block = " ".join(parts)



        txt = clean_text(title + " " + block)



        item = {}

        item["공고명"] = title

        item["원문"] = txt

        item["상세링크"] = href



        m = re.search(r'(R\d{2}BK\d+(?:-\d{3})?|\d{8,}-\d{2})', txt)

        if m:

            item["공고번호"] = m.group(1)



        # 제출마감/투찰마감/입찰마감 우선 추출
        found_submit = None

        submit_patterns = [
            r"제출\s*마감\s*일시\s*[:：]?\s*(20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2})",
            r"제출마감일시\s*[:：]?\s*(20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2})",
            r"투찰\s*마감\s*일시\s*[:：]?\s*(20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2})",
            r"투찰마감일시\s*[:：]?\s*(20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2})",
            r"입찰\s*마감\s*일시\s*[:：]?\s*(20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2})",
            r"입찰마감일시\s*[:：]?\s*(20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2})",
        ]

        for pp in submit_patterns:
            mm = re.search(pp, txt)
            if mm:
                found_submit = clean_text(mm.group(1))
                break

        if found_submit:
            item["투찰마감일"] = found_submit
        else:
            dates = re.findall(
                r"20\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2}|\d{2}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2}",
                txt
            )
            if dates:
                item["투찰마감일"] = dates[1] if len(dates) >= 2 else dates[0]



        # 지역 판정

        region = ""



        if "충북" in txt or "충청북도" in txt:

            region = "충북"



        elif "청주" in txt:

            region = "청주"



        elif "세종" in txt:

            region = "세종"



        elif "전국" in txt:



            # 전국 + 타지역 조합 제외

            bad_regions = [

                "대구",

                "부산",

                "울산",

                "경남",

                "경북",

                "전남",

                "전북",

                "광주",

                "인천",

                "제주",

                "강원",

                "경기",

            ]



            if not any(r in txt for r in bad_regions):

                region = "전국"



        if region:

            item["지역제한"] = region



        items.append(item)



    if items:
        pass

        # return items  # disabled: allow supplement parser







    # 공고번호 row 기준 보강 파싱 비활성화

    # SMC지원센터에서 앞뒤 row가 섞여 제목/공고번호 mismatch가 발생하므로 사용하지 않음



    # 메일 목록형 테이블 파싱

    rows = soup.find_all("tr")



    for tr in rows:



        txt = clean_text(tr.get_text(" "))



        if not txt:

            continue



        if "공고번호" in txt:

            continue



        if not any(

            k in txt

            for k in (

                WORK_KEYWORDS +

                GOODS_KEYWORDS

            )

        ):

            continue



        bid_match = re.search(

            r'R\d{2}BK\d+(?:-\d{3})?',

            txt

        )



        date_match = re.search(

            r'20\d{2}[-.]\d{2}[-.]\d{2}\s+\d{2}:\d{2}',

            txt

        )



        item = {}



        if bid_match:

            item["공고번호"] = bid_match.group(0)



        if date_match:

            item["투찰마감일"] = date_match.group(0)



        item["공고명"] = txt[:300]



        item["원문"] = txt



        items.append(item)



    return items







def _region_allowed(item):



    region = str(item.get("지역제한", "")).strip()

    raw = str(item.get("원문", ""))



    # 지역제한 표준화

    region = region.replace("[", "").replace("]", "")

    region = region.replace("충청북도", "충북")

    region = region.replace("세종특별자치시", "세종")

    region = region.replace("세종시", "세종")

    region = " ".join(region.split())



    # SMC처럼 원문에 [전국], [충북], [세종]이 있는 경우 보강

    if not region:

        m = re.search(r"\[(전국|충북|충북\s*청주시|세종)\]", raw)

        if m:

            region = " ".join(m.group(1).split())



    allowed = [

        "전국",

        "충북",

        "충북 청주시",

        "세종",

    ]



    # SMC 제목/원문에 [전국]과 타지역이 같이 있으면 제외

    # 예: [전국] [서울], [전국] [경기]

    if region == "전국":

        mixed_bad = [

            "서울", "부산", "대구", "인천", "광주", "대전", "울산",

            "경기", "강원", "충남", "전남", "전북", "경남", "경북", "제주"

        ]

        for r in mixed_bad:

            check_text = raw + " " + str(item.get("공고명", "")) + " " + str(item.get("summary", ""))

            if ("[전국]" in check_text) and ("[%s]" % r in check_text):

                return False



    return region in allowed





def enrich_detail_from_viewmail(item):



    url = item.get("상세링크", "")



    if not url or "viewMail.php" not in url:

        return item



    try:

        r = requests.get(url, timeout=10, verify=False)

        r.encoding = r.apparent_encoding or "utf-8"



        soup = BeautifulSoup(r.text, "html.parser")

        text = clean_text(soup.get_text(" "))



        item["상세원문"] = text



        m = re.search(r"업종제한\s*([\[\(].{0,300}?[\]\)])", text)

        if m:

            item["업종제한"] = clean_text(m.group(1))



        if any(x in text for x in [

            "기계설비공사업",

            "기계가스설비",

            "가스난방",

            "난방시설1종",

        ]):

            item["업종"] = "기계설비"



    except Exception as e:

        log("[DETAIL_FETCH_ERROR] %s %s" % (url, e))



    return item




def is_target(item):



    text_raw = " ".join(str(v) for v in item.values())

    text = text_raw.upper()



    exclude_words = [

        "0건",

        "해당되는 조건의 데이터가 없습니다",

        "500개 이상 자료는 홈페이지",

        "낙찰업체정보",

        "[결과]",

        "[취소]",

        "유찰",

        "낙찰되었습니다",

    ]



    if any(x in text_raw for x in exclude_words):

        return False



    region_ok = _region_allowed(item)



    work_ok = any(x.upper() in text for x in [

        "기계설비",

        "기계설비공사업",

        "기계가스설비",
        "가스난방",
        "난방시설",
        "보일러",
        "세관",
        "정비 공사",

        "소방",

        "소방설비",

        "전문소방",

        "일반소방",

    ])



    return bool(work_ok and region_ok)






def build_event(item):



    title = clean_text(

        item.get("공고명", "입찰공고")

    )



    region = clean_text(

        item.get("지역제한", "")

    )



    industry = clean_text(

        item.get("업종제한", "")

    )



    prefix = []



    if "기계" in title or "기계" in industry:

        prefix.append("기계설비")



    elif "소방" in title or "소방" in industry:

        prefix.append("소방")



    elif any(

        x in title.upper()

        for x in GOODS_KEYWORDS

    ):

        prefix.append("물품")



    if region:

        prefix.append(region)



    if prefix:

        event_title = "[%s] %s" % (

            "][".join(prefix),

            title

        )

    else:

        event_title = title



    # SMC 원문에서 투찰마감일시 보강
    if not item.get("투찰마감일"):
        raw_for_deadline = str(item.get("원문", ""))

        m = re.search(
            r'R\d{2}BK\d+(?:-\d{3})?\s*호\s*(\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2})',
            raw_for_deadline
        )

        if not m:
            m = re.search(
                r'(\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2})',
                raw_for_deadline
            )

        if m:
            item["투찰마감일"] = m.group(1)

    start_dt = (

        parse_datetime(item.get("투찰마감일"))

        or parse_datetime(item.get("등록(신청)마감"))

        or parse_datetime(item.get("입찰(개찰)일시"))

    )



    if not start_dt:

        start_dt = datetime.now() + timedelta(days=1)



    end_dt = start_dt + timedelta(minutes=30)



    desc = []



    for k in [

        "공고번호",
        "투찰마감일",

        "업종제한",

        "지역제한",

        "기초금액",

        "추정가격",

        "등록(신청)마감",


        "입찰(개찰)일시",

        "발주처",

        "수요기관",

        "발주기관",

        "업종",

        "낙찰방법",

        "상세URL",

    ]:



        if item.get(k):

            desc.append(

                "%s : %s" % (

                    k,

                    item.get(k)

                )

            )



    return {

        "summary": event_title,

        "description": "\\n".join(desc),


        "start": {

            "dateTime": start_dt.isoformat(),

            "timeZone": "Asia/Seoul",

        },

        "end": {

            "dateTime": end_dt.isoformat(),

            "timeZone": "Asia/Seoul",

        },

        "reminders": {

            "useDefault": False,

            "overrides": [

                {

                    "method": "popup",

                    "minutes": 60

                },

                {

                    "method": "popup",

                    "minutes": 1440

                },

            ],

        },

    }





def _norm_bid_no_for_cross_check(v):

    s = str(v or '').strip()
    s = s.replace(' ', '')
    s = s.replace(' - ', '-')
    s = s.replace('–', '-')
    s = s.replace('—', '-')
    return s


def _extract_bid_no_from_event(event):

    text = (

        str(event.get("summary", "") or "")

        + "\n"

        + str(event.get("description", "") or "")

    ).upper()



    # 나라장터: 명시된 차수만 사용한다.

    m = re.search(

        r"\b(R\d{2}BK\d+)(?:\s*[-–—]\s*(\d{3}))?\b",

        text

    )

    if m:

        return m.group(1) + ("-" + m.group(2) if m.group(2) else "")



    # 국방조달: 예) UMM0945, UMM0945 - 1

    m = re.search(

        r"(?<![A-Z0-9])([A-Z]{3}\d{4})"

        r"(?:\s*[-–—]\s*(\d{1,3}))?(?![A-Z0-9])",

        text

    )

    if m:

        return m.group(1) + (

            "-" + str(int(m.group(2))) if m.group(2) else ""

        )



    return ""

def exists_bid_in_cross_calendars(service, bid_no):

    bid_no = _norm_bid_no_for_cross_check(bid_no).upper()

    if not bid_no:

        return False



    base = bid_no.split("-")[0]



    for cal_id in CROSS_CHECK_CALENDAR_IDS:

        token = None

        while True:

            try:

                response = service.events().list(

                    calendarId=cal_id,

                    q=base,

                    singleEvents=True,

                    showDeleted=False,

                    maxResults=2500,

                    pageToken=token,

                ).execute()

            except Exception as error:

                # 조회하지 못한 공고를 처리 완료로 기록하지 않는다.

                raise RuntimeError(

                    "교차 캘린더 조회 실패: %s %s" % (cal_id, error)

                )



            for existing in response.get("items", []):

                found = _extract_bid_no_from_event(existing)

                if not found or found.split("-")[0] != base:

                    continue



                if found == bid_no:

                    log("[SKIP_CROSS_CAL_DUP] %s calendar=%s event=%s" % (

                        bid_no, cal_id, existing.get("id", "")

                    ))

                    return True



                # 한쪽에 차수가 없으면 동일/변경 공고인지 확정할 수 없다.

                if "-" not in found or "-" not in bid_no:

                    raise RuntimeError(

                        "교차 캘린더 차수 확인 필요: candidate=%s existing=%s"

                        % (bid_no, found)

                    )



                # 양쪽 차수가 명시되어 있고 서로 다르면 중복 제외하지 않는다.



            token = response.get("nextPageToken")

            if not token:

                break



    return False

def _normalize_calendar_bid_title(value):



    """

    캘린더 중복 비교용 공고명 정규화.



    프로그램이 붙인 업종/지역 머리말과 공백 차이만 제거한다.

    [변경공고] 등 실제 공고명에 포함된 표시는 유지한다.

    """



    value = clean_text(str(value or ""))

    value = value.replace("\u00a0", " ")

    value = value.replace("\u200b", "")

    value = re.sub(r"\s+", " ", value).strip()



    auto_prefixes = {

        "기계설비",

        "소방",

        "물품",

        "전국",

        "충북",

        "충청북도",

        "청주시",

        "충북 청주시",

        "세종",

        "세종시",

        "세종특별자치시",

    }



    while True:

        m = re.match(r"^\[([^\[\]]+)\]\s*", value)



        if not m:

            break



        prefix = re.sub(r"\s+", " ", m.group(1)).strip()



        if (

            prefix not in auto_prefixes

            and not prefix.startswith("충북 ")

            and not prefix.startswith("세종 ")

        ):

            break



        value = value[m.end():].strip()



    return value.casefold()





def exists_same_title_same_date(service, event):



    """

    bid-daum 캘린더에서 같은 날짜의 동일 공고명을 찾는다.

    """



    start_info = event.get("start", {})

    start_value = (

        start_info.get("dateTime")

        or start_info.get("date")

        or ""

    )



    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(start_value))



    if not m:

        log("[WARN_DAUM_DUP_CHECK] 이벤트 날짜 확인 불가: %s" % start_value)

        return False



    event_date = m.group(1)

    candidate_summary = str(event.get("summary", "") or "")

    candidate_title = _normalize_calendar_bid_title(candidate_summary)



    if not candidate_title:

        return False



    time_min = event_date + "T00:00:00+09:00"

    time_max_date = (

        datetime.strptime(event_date, "%Y-%m-%d")

        + timedelta(days=1)

    ).strftime("%Y-%m-%d")

    time_max = time_max_date + "T00:00:00+09:00"



    page_token = None



    try:

        while True:

            result = service.events().list(

                calendarId=GCAL_CALENDAR_ID,

                timeMin=time_min,

                timeMax=time_max,

                singleEvents=True,

                showDeleted=False,

                maxResults=2500,

                pageToken=page_token,

            ).execute()



            for existing in result.get("items", []):

                existing_summary = str(

                    existing.get("summary", "") or ""

                )



                existing_title = _normalize_calendar_bid_title(

                    existing_summary

                )



                if existing_title == candidate_title:

                    log(

                        "[SKIP_DAUM_TITLE_DATE_DUP] "

                        "date=%s eventId=%s title=%s"

                        % (

                            event_date,

                            existing.get("id", ""),

                            candidate_summary,

                        )

                    )

                    return True



            page_token = result.get("nextPageToken")



            if not page_token:

                break



    except Exception as e:

        # 조회 장애가 발생했다고 정상 공고 등록까지 중단하지 않는다.

        log(

            "[WARN_DAUM_DUP_CHECK] date=%s error=%s"

            % (event_date, e)

        )



    return False





def insert_event(service, event):



    bid_no = _extract_bid_no_from_event(event)



    if exists_bid_in_cross_calendars(service, bid_no):

        return None



    if exists_same_title_same_date(service, event):

        return None



    return service.events().insert(

        calendarId=GCAL_CALENDAR_ID,

        body=event

    ).execute()






def fetch_recent_emails(days=3, max_count=20):



    if not DAUM_PASS:

        raise RuntimeError(

            "DAUM_MAIL_PASS 환경변수가 없습니다."

        )



    ctx = ssl.create_default_context()



    imap = imaplib.IMAP4_SSL(

        IMAP_HOST,

        IMAP_PORT,

        ssl_context=ctx

    )



    imap.login(

        DAUM_USER,

        DAUM_PASS

    )



    imap.select("INBOX")



    since = (

        datetime.now() - timedelta(days=days)

    ).strftime("%d-%b-%Y")



    typ, data = imap.search(

        None,

        '(SINCE "%s")' % since

    )



    ids = data[0].split()[-max_count:]



    mails = []



    for mid in reversed(ids):



        typ, msg_data = imap.fetch(

            mid,

            "(RFC822)"

        )



        if typ != "OK":

            continue



        raw = msg_data[0][1]



        msg = email.message_from_bytes(raw)



        subject = decode_mime(

            msg.get("Subject")

        )



        sender = decode_mime(

            msg.get("From")

        )



        if not any(

            x in subject

            for x in SUBJECT_KEYWORDS

        ):

            continue



        html = get_email_html(msg)



        raw_dir = "/home/pi/n_data/daum_mail/backup/raw_mail"

        os.makedirs(raw_dir, exist_ok=True)

        raw_path = os.path.join(raw_dir, "mail_%s.html" % mid.decode())

        with open(raw_path, "w", encoding="utf-8") as f:

            f.write(html)

        log("[RAW_SAVE] %s subject=%s" % (raw_path, subject))



        mails.append({

            "mail_id": mid.decode(),

            "subject": subject,

            "from": sender,

            "html": html,

        })



    imap.logout()



    return mails







def merge_collected_bid_items(items):

    """

    여러 메일에서 수집한 공고를 처리 전에 통합한다.



    우선순위:

    1. 공고번호가 같으면 같은 공고로 통합

    2. 공고번호가 없으면 공고명 + 투찰마감일 기준 통합

    3. 값이 비어 있는 필드는 다른 메일의 값으로 보강

    4. 원문은 정보량이 더 많은 값을 유지

    """



    def normalize_bid_no(value):

        value = clean_text(str(value or ""))

        value = re.sub(r"\s*-\s*", "-", value)



        m = re.search(r"(R\d{2}BK\d+)(?:-(\d{3}))?", value, re.I)

        if m:

            return m.group(1).upper() + "-" + (m.group(2) or "000")



        return value.upper()



    def normalize_title(value):

        value = clean_text(str(value or ""))

        value = re.sub(r"^\d+\s+", "", value)

        value = re.sub(r"\s+", " ", value).strip()

        return value



    def normalize_deadline(value):

        return clean_text(str(value or ""))



    def item_key(item, index):

        bid_no = normalize_bid_no(item.get("공고번호"))



        if bid_no:

            return ("BID", bid_no)



        title = normalize_title(item.get("공고명"))

        deadline = normalize_deadline(item.get("투찰마감일"))



        if len(title) >= 8 and deadline:

            return ("TITLE_DATE", title, deadline)



        # 식별할 근거가 부족한 항목은 서로 합치지 않는다.

        return ("UNIQUE", index)



    def meaningful(value):

        if value is None:

            return False



        text = clean_text(str(value))



        return text not in {

            "",

            "-",

            "0",

            "0원",

            "None",

            "null",

        }



    def item_score(item):

        important_fields = [

            "공고번호",

            "공고명",

            "투찰마감일",

            "지역제한",

            "기초금액",

            "추정가격",

            "수요기관",

            "발주기관",

            "업종",

            "상세URL",

        ]



        score = sum(

            10

            for field in important_fields

            if meaningful(item.get(field))

        )



        title = normalize_title(item.get("공고명"))

        raw = str(item.get("원문", "") or "")



        score += min(len(title), 200)

        score += min(len(raw) // 20, 100)



        # 표 전체나 헤더가 공고명으로 잘못 들어온 항목은 감점

        if "번호 공고명 기초금액 추정가격" in title:

            score -= 300



        if len(title) > 500:

            score -= 200



        # SMC 원문 전체가 공고명으로 들어온 항목 감점

        if re.match(r"^20\d{2}-\d{2}-\d{2}\s+SAC", title):

            score -= 250



        if " 조달청 " in title and " 호 " in title:

            score -= 150



        return score



    merged = {}

    order = []



    for index, original in enumerate(items):

        item = dict(original)

        key = item_key(item, index)



        if key not in merged:

            merged[key] = item

            order.append(key)

            continue



        current = merged[key]



        # 더 완전한 항목을 기준 항목으로 선택

        if item_score(item) > item_score(current):

            primary = item

            secondary = current

        else:

            primary = current

            secondary = item



        result = dict(primary)



        # 비어 있는 필드를 다른 메일의 정보로 보강

        for field, value in secondary.items():

            if not meaningful(result.get(field)) and meaningful(value):

                result[field] = value



        # 원문은 정보가 많은 쪽을 유지

        raw_primary = str(primary.get("원문", "") or "")

        raw_secondary = str(secondary.get("원문", "") or "")



        if len(raw_secondary) > len(raw_primary):

            result["원문"] = raw_secondary



        # 어느 메일에서 들어왔는지 기록

        sources = []



        for source in [

            current.get("_source_subject", ""),

            item.get("_source_subject", ""),

        ]:

            source = clean_text(str(source or ""))



            if source and source not in sources:

                sources.append(source)



        result["_source_subject"] = " | ".join(sources)

        merged[key] = result



    result = [merged[key] for key in order]



    log(

        "[PRE_MERGE] input=%d merged=%d removed=%d"

        % (

            len(items),

            len(result),

            len(items) - len(result),

        )

    )



    return result





def main():



    ap = argparse.ArgumentParser()



    ap.add_argument(

        "--days",

        type=int,

        default=3

    )



    ap.add_argument(

        "--max",

        type=int,

        default=20

    )



    ap.add_argument(

        "--apply",

        action="store_true"

    )



    ap.add_argument(

        "--include-subject",

        default="",

        help="쉼표로 구분한 포함 메일 제목 키워드"

    )



    args = ap.parse_args()



    seen = load_seen()



    run_seen = set()
    run_seen_title = set()



    service = None



    if args.apply:

        service = get_calendar_service()



    mails = fetch_recent_emails(

        days=args.days,

        max_count=args.max

    )



    if args.include_subject:

        keys = [x.strip() for x in args.include_subject.split(",") if x.strip()]

        mails = [

            m for m in mails

            if any(k in m.get("subject", "") for k in keys)

        ]



    log("메일 %d건 조회" % len(mails))



    excel_rows = []



    # 모든 메일을 먼저 파싱한 후 공고 단위로 통합
    collected_items = []

    for mail in mails:

        log("메일 제목: %s" % mail["subject"])

        parsed_items = parse_bid_items(

            mail["html"]

        )

        log("공고 %d건 발견" % len(parsed_items))

        for parsed_item in parsed_items:

            parsed_item = dict(parsed_item)

            parsed_item["_source_subject"] = mail.get("subject", "")

            collected_items.append(parsed_item)

    merged_items = merge_collected_bid_items(collected_items)

    log("통합 후 공고 %d건 처리" % len(merged_items))

    # 기존 처리 코드의 들여쓰기를 유지하기 위한 1회 반복 블록
    for _merged_once in [None]:

        for item in merged_items:

            mail = {"subject": item.get("_source_subject", "")}

            item = enrich_detail_from_viewmail(item)



            if "R26BK01517647" in str(item):

                log("[DEBUG_ITEM] %s" % item)





            # SMC 등에서 제목/설명 row가 섞여 공고번호가 불일치하면 제외
            raw_text = str(item.get("원문", ""))
            bid_no_now = str(item.get("공고번호", "")).strip()

            bid_nums_in_raw = re.findall(r"R\\d{2}BK\\d+(?:-\\d{3})?", raw_text)

            # 제목 안의 공고번호와 item 공고번호가 다르면 제외
            title_text = str(item.get("공고명", ""))
            bid_nums_in_title = re.findall(r"R\\d{2}BK\\d+(?:-\\d{3})?", title_text)

            if bid_no_now and bid_nums_in_title:
                norm_now_title = bid_no_now if "-" in bid_no_now else bid_no_now + "-000"
                norm_title = [
                    x if "-" in x else x + "-000"
                    for x in bid_nums_in_title
                ]

                if norm_now_title not in norm_title:
                    log("[SKIP_TITLE_BID_MISMATCH] item=%s title=%s name=%s" % (
                        norm_now_title,
                        ",".join(norm_title[:5]),
                        item.get("공고명", "")
                    ))
                    continue

            if bid_no_now and bid_nums_in_raw:
                norm_now = bid_no_now if "-" in bid_no_now else bid_no_now + "-000"
                norm_raw = [
                    x if "-" in x else x + "-000"
                    for x in bid_nums_in_raw
                ]

                if norm_now not in norm_raw:
                    log("[SKIP_BID_MISMATCH] item=%s raw=%s title=%s" % (
                        norm_now,
                        ",".join(norm_raw[:5]),
                        item.get("공고명", "")
                    ))
                    continue

            # 민간 소방점검/업체선정 공고 제외
            title_chk = str(item.get("공고명", ""))

            # 점검/업체선정 계열 전면 제외
            if any(x in title_chk for x in [
                "점검",
                "정밀점검",
                "최초점검",
                "작동점검",
                "업체선정",
                "업체 선정",
                "관리업체",
                "관리업체 선정",
                "유지관리",
                "유지관리업체",
                "사업자선정",
                "사업자 선정",
            ]):
                log("[SKIP_INSPECTION] %s" % title_chk)
                continue

            # 제목에 타지역이 명시된 SMC 전국 공고 제외
            if any(x in title_chk for x in [
                "[서울]",
                "[경기]",
                "[인천]",
                "[부산]",
                "[대구]",
                "[광주]",
                "[대전]",
                "[울산]",
                "[강원]",
                "[충남]",
                "[전남]",
                "[전북]",
                "[경남]",
                "[경북]",
                "[제주]",
            ]):
                log("[SKIP_TITLE_REGION] %s" % title_chk)
                continue

            bid_chk = str(item.get("공고번호", ""))

            if (
                any(x in title_chk for x in [
                    "업체선정",
                    "사업자 선정",
                    "사업자선정",
                    "종합점검",
                    "정밀점검",
                    "작동점검",
                    "최초점검",
                    "소방점검",
                ])
                and not bid_chk.startswith("R")
            ):
                log("[SKIP_PRIVATE_FIRE] %s" % title_chk)
                continue

            if "광교지사" in title_chk:

                log("[SKIP_BAD_AREA_TITLE] %s" % title_chk)

                continue



            if not is_target(item):

                continue



            bid_no = clean_text(

                item.get("공고번호", "")

            )



            # 공고번호에 차수가 붙지 않은 경우 -000 보정
            if bid_no and bid_no.startswith("R") and "-" not in bid_no:
                bid_no = bid_no + "-000"

            if not bid_no:



                bid_no = hashlib.sha1(

                    (

                        mail["subject"]

                        + item.get("공고명", "")

                    ).encode("utf-8")

                ).hexdigest()[:16]



            if bid_no in run_seen:



                log("[SKIP_RUN_DUP] %s" % bid_no)



                continue







            title_key = (
                str(item.get("공고명", "")).strip(),
                str(item.get("투찰마감일", "")).strip(),
            )

            if title_key in run_seen_title:
                log("[SKIP_TITLE_DUP] %s" % str(title_key))
                continue

            if bid_no in seen:



                log(

                    "[SKIP_ALREADY] %s"

                    % bid_no

                )



                continue



            run_seen.add(bid_no)
            run_seen_title.add(title_key)



            event = build_event(item)



            excel_rows.append({

                "status": "NEW",

                "mail_subject": mail.get("subject", ""),

                "bid_key": bid_no,

                "summary": event.get("summary", ""),

                "start": event.get("start", {}).get("dateTime", ""),

                "공고명": item.get("공고명", ""),

                "공고번호": item.get("공고번호", ""),

                "업종제한": item.get("업종제한", ""),

                "지역제한": item.get("지역제한", ""),

                "기초금액": item.get("기초금액", ""),

                "추정가격": item.get("추정가격", ""),

                "투찰마감일": item.get("투찰마감일", ""),

                "입찰(개찰)일시": item.get("입찰(개찰)일시", ""),

                "원문": item.get("원문", ""),

            })



            if args.apply:



                result = insert_event(

                    service,

                    event

                )

                if result is None:

                    save_seen(bid_no)

                    log("[GCAL_SKIP] %s" % bid_no)

                    continue




                save_seen(bid_no)



                log(

                    "[GCAL_OK] %s"

                    % result.get("htmlLink", "")

                )



            else:



                log(

                    "[DRY] %s | %s"

                    % (

                        bid_no,

                        event["summary"]

                    )

                )





    save_excel_and_cleanup(excel_rows)





# ===== bid-daum Excel save / cleanup =====

def save_excel_and_cleanup(rows):



    from pathlib import Path

    from datetime import datetime

    import shutil



    out_dir = Path("/mnt/vol1/bid/bid-daum")

    backup_dir = out_dir / "backup-bid-daum"



    out_dir.mkdir(parents=True, exist_ok=True)

    backup_dir.mkdir(parents=True, exist_ok=True)



    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_file = out_dir / ("bid_daum_%s.xlsx" % ts)



    if rows:

        try:

            import pandas as pd

            df = pd.DataFrame(rows)

            df.to_excel(str(out_file), index=False)

            log("[EXCEL_SAVE] %s rows=%d" % (out_file, len(rows)))

        except Exception as e:

            log("[EXCEL_SAVE][ERROR] %s" % e)

    else:

        log("[EXCEL_SAVE] 신규 대상 없음")



    now = datetime.now()



    for f in out_dir.glob("*.xlsx"):

        age_days = (now - datetime.fromtimestamp(f.stat().st_mtime)).days

        if age_days >= 2:

            dst = backup_dir / f.name

            try:

                shutil.move(str(f), str(dst))

                log("[BACKUP_MOVE] %s -> %s" % (f, dst))

            except Exception as e:

                log("[BACKUP_MOVE][ERROR] %s %s" % (f, e))



    for f in backup_dir.glob("*.xlsx"):

        age_days = (now - datetime.fromtimestamp(f.stat().st_mtime)).days

        if age_days >= 30:

            try:

                f.unlink()

                log("[DELETE_OLD] %s" % f)

            except Exception as e:

                log("[DELETE_OLD][ERROR] %s %s" % (f, e))



if __name__ == "__main__":

    main()

