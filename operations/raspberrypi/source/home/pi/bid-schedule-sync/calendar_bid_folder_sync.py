#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Calendar 입찰 일정을 NAS의 공고별 폴더/엑셀로 동기화한다."""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

KST = timezone(timedelta(hours=9))
TARGET_ROOT = Path(os.environ.get("BID_SCHEDULE_ROOT", "/mnt/vol1/AI/GPT/입찰일정"))
SERVICE_ACCOUNT_FILE = os.environ.get(
    "GCAL_SERVICE_ACCOUNT_FILE",
    "/home/pi/n_data/credentials/google_calendar_service_account.json",
)
LOOKBACK_DAYS = int(os.environ.get("BID_LOOKBACK_DAYS", "14"))
LOOKAHEAD_DAYS = int(os.environ.get("BID_LOOKAHEAD_DAYS", "120"))
LOG_FILE = Path(os.environ.get("BID_SCHEDULE_LOG", "/home/pi/bid-schedule-sync/logs/sync.log"))
BID_DAUM_CALENDAR_ID = "redacted@example.invalid"
SOURCE_CALENDARS = [
    ("redacted@example.invalid", "redacted@example.invalid"),
    ("redacted@example.invalid", "LH"),
]

FIELDS = [
    "공고번호", "공고명", "입찰개시일시", "입찰마감일시", "협정마감일시", "협정확인상태",
    "기초금액", "하한율", "지역", "필요면허·첨부서류", "신청완료여부", "다음행동",
    "발주기관", "입찰시스템", "상세URL", "캘린더", "최종동기화일시",
]


def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(str(LOG_FILE), encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


def first_match(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            return match.group(1).strip()
    return ""


def normalize_datetime(value):
    if not value:
        return ""
    value = value.strip().replace("/", "-")
    match = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?", value)
    if not match:
        return ""
    parts = [int(x or 0) for x in match.groups()]
    return "%04d-%02d-%02d %02d:%02d:%02d" % tuple(parts)


def parse_event(event, calendar_name):
    title = (event.get("summary") or "").strip()
    desc = re.sub(r"(?i)<br\s*/?>", "\n", (event.get("description") or "").replace("\\n", "\n"))
    combined = title + "\n" + desc
    if "취소" in combined:
        return None

    bid_no = first_match(combined, [
        r"공고번호\s*[:：]\s*([A-Z0-9-]+(?:\s*-\s*\d{3})?)",
        r"\b(R\d{2}BK\d{8}(?:\s*-?\s*\d{3})?)\b",
        r"\b([A-Z]{1,4}\d{6,}(?:-\d{2,5})?)\b",
    ]).replace(" ", "")
    bid_name = first_match(combined, [r"공고명\s*[:：]\s*([^\n]+)", r"입찰공고건명\s*[:：]\s*([^\n]+)"])
    if not bid_name:
        bid_name = re.sub(r"^[&◆#ㅁㅇ?\s]+", "", title)
        bid_name = re.sub(r"^(\[[^]]+\]\s*)+", "", bid_name)
        bid_name = re.sub(r"-\d{1,2}(?::\d{2})?$", "", bid_name).strip()
    bid_name = re.sub(r"^[?&ㅇㅁ/\s]*(?:\d{2}\.\d{3})\s*[_/\-]?\s*", "", bid_name).strip()

    start = normalize_datetime(first_match(combined, [
        r"입찰서?접수개시일시\s*[:：]\s*([^\n]+)",
        r"입찰개시일시\s*[:：]\s*([^\n]+)",
        r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)\s*~",
    ]))
    deadline = normalize_datetime(first_match(combined, [
        r"입찰서?접수마감일시\s*[:：]\s*([^\n]+)",
        r"입찰마감일시\s*[:：]\s*([^\n]+)",
        r"투찰마감일\s*[:：]\s*([^\n]+)",
        r"~\s*(20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)",
    ]))
    agreement = normalize_datetime(first_match(combined, [
        r"공동수급협정서(?:접수|제출)?마감일시\s*[:：]\s*([^\n]+)",
        r"공동수급협정(?:서)?\s*(?:접수|제출)?\s*마감일시\s*[:：]\s*([^\n]+)",
        r"공동협정서마감일시\s*[:：]\s*([^\n]+)",
        r"협정(?:서)?마감일시\s*[:：]\s*([^\n]+)",
        r"공동수급협정서[^\n]*(20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)",
    ]))

    # 캘린더 이벤트 자체가 [입찰개시]인 경우 이벤트 시작시각을 보조값으로 사용한다.
    if not start and "입찰개시" in title:
        raw_start = event.get("start", {}).get("dateTime", "")
        if raw_start:
            try:
                start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
    if not start:
        logging.warning("입찰개시일시 없음: %s", title)
        return None

    base_amount = first_match(combined, [r"기초금액\s*[:：]\s*([\d,]+)", r"기초예비가격\s*[:：]\s*([\d,]+)"])
    estimated_price = first_match(combined, [r"추정가격\s*[:：]\s*([\d,]+)"])
    estimated_value = int(estimated_price.replace(",", "")) if estimated_price else 0
    base_value = int(base_amount.replace(",", "")) if base_amount else 0
    agreement_required = estimated_value >= 1000000000 or (not estimated_value and base_value >= 1100000000)
    agreement_status = first_match(combined, [r"협정확인상태\s*[:：]\s*([^\n]+)"])
    if not agreement_status and agreement:
        agreement_status = "공식 원문 확인"
    agreement_check_required = bool(not agreement and not agreement_status and agreement_required)
    if agreement_check_required:
        agreement_status = "원문 확인 실패"
    lower_rate = first_match(combined, [r"(?:낙찰)?하한율\s*[:：]?\s*([\d.]+)\s*%", r"(?:투찰율|투찰률)\s*[:：]?\s*([\d.]+)\s*%"])
    if not lower_rate:
        title_rate = re.search(r"(?:^|[?ㅇㅁ/])\s*(\d{2}\.\d{3})\b", title)
        lower_rate = title_rate.group(1) if title_rate else ""

    region = first_match(combined, [r"참가지역\s*[:：]\s*([^\n]+)", r"지역제한\s*[:：]\s*([^\n]+)", r"공동도급지역\s*[:：]\s*([^\n]+)", r"지역\s*[:：]\s*([^\n]+)"])
    license_info = first_match(combined, [r"면허·첨부서류\s*[:：]\s*([^\n]+)", r"업종\s*[:：]\s*([^\n]+)", r"(전문소방시설공사업[^\n]*)", r"(일반소방시설공사업[^\n]*)", r"(기계설비공사업[^\n]*)", r"(전기공사업[^\n]*)"])
    complete = "완료" if "신청완료" in combined else "확인 필요"
    next_action = "투찰 완료 및 제출확인서 확인" if complete == "완료" else "참가신청·협정·투찰 여부 확인"
    if agreement_check_required:
        next_action = "공고문 원문에서 협정마감일시 확인 · " + next_action
        logging.warning("협정마감일시 원문 확인 필요: %s", bid_name)
    issuer = first_match(combined, [r"발주기관\s*[:：]\s*([^\n]+)", r"수요기관\s*[:：]\s*([^\n]+)"])
    detail_url = first_match(combined, [r"상세URL\s*[:：]\s*(https?://\S+)", r"(https?://www\.g2b\.go\.kr/\S+)"])
    explicit_system = first_match(combined, [r"입찰시스템\s*[:：]\s*([^\n]+)"])
    system = explicit_system or "나라장터"
    if "LH" in title or calendar_name.upper() == "LH": system = "LH"
    elif "한전" in title or "SRM" in combined: system = "한전 SRM"
    elif "국방부" in combined or "국방조달" in combined: system = "국방조달"

    return {
        "공고번호": bid_no or "공고번호미확인",
        "공고명": bid_name,
        "입찰개시일시": start,
        "입찰마감일시": deadline,
        "협정마감일시": agreement,
        "협정확인상태": agreement_status,
        "기초금액": int(base_amount.replace(",", "")) if base_amount else None,
        "하한율": float(lower_rate) if lower_rate else None,
        "지역": region,
        "필요면허·첨부서류": license_info,
        "신청완료여부": complete,
        "다음행동": next_action,
        "발주기관": issuer,
        "입찰시스템": system,
        "상세URL": detail_url,
        "캘린더": calendar_name,
        "최종동기화일시": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
    }


def normalize_bid_name(value):
    value = re.sub(r"(?i)<br\s*/?>", " ", value or "")
    value = re.sub(r"\[[^]]+\]", " ", value)
    value = re.sub(r"^\s*20\d{2}[-./]\d{1,2}[-./]\d{1,2}\s+", "", value)
    value = re.sub(r"^[?&ㅇㅁ/\s]*(?:\d{2}\.\d{3})\s*[_/\-]?\s*", "", value)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).lower()


def build_bid_number_index(service):
    index = []
    for event in iter_events(service, BID_DAUM_CALENDAR_ID):
        title = event.get("summary") or ""
        desc = re.sub(r"(?i)<br\s*/?>", "\n", (event.get("description") or "").replace("\\n", "\n"))
        combined = title + "\n" + desc
        if "취소" in combined:
            continue
        bid_no = first_match(combined, [
            r"공고번호\s*[:：]\s*([A-Z0-9-]+(?:\s*-\s*\d{3})?)",
            r"\b(R\d{2}BK\d{8}(?:\s*-?\s*\d{3})?)\b",
        ]).replace(" ", "")
        if not bid_no:
            continue
        names = [title]
        named = first_match(combined, [r"공고명\s*[:：]\s*([^\n]+)", r"입찰공고건명\s*[:：]\s*([^\n]+)"])
        if named:
            names.append(named)
        for name in names:
            normalized = normalize_bid_name(name)
            if len(normalized) >= 8:
                index.append((normalized, bid_no))
    logging.info("bid-daum 공고번호 색인: %d건", len(index))
    return index


def enrich_bid_number(item, index):
    if item["공고번호"] != "공고번호미확인":
        return item
    target = normalize_bid_name(item["공고명"])
    matches = [(len(name), bid_no) for name, bid_no in index
               if target == name or (len(target) >= 8 and (target in name or name in target))]
    if matches:
        item["공고번호"] = max(matches)[1]
        logging.info("공고번호 자동 보완: %s -> %s", item["공고명"], item["공고번호"])
    return item


def safe_name(value, max_len=90):
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value or "")
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or "이름미확인")[:max_len]


def daily_workbook_path(day):
    return TARGET_ROOT / day / (day[5:7] + day[8:10] + ".xlsx")


def read_user_status(path):
    saved = {}
    if not path.exists():
        return saved
    try:
        wb = load_workbook(str(path), data_only=False)
        ws = wb.active
        headers = {cell.value: cell.column for cell in ws[1] if cell.value}
        for row in range(2, ws.max_row + 1):
            bid_no = ws.cell(row, headers.get("공고번호", 1)).value
            bid_name = ws.cell(row, headers.get("공고명", 2)).value
            key = (str(bid_no or ""), str(bid_name or ""))
            saved[key] = {
                "신청완료여부": ws.cell(row, headers["신청완료여부"]).value if "신청완료여부" in headers else None,
                "다음행동": ws.cell(row, headers["다음행동"]).value if "다음행동" in headers else None,
            }
    except Exception as exc:
        logging.warning("기존 관리상태 읽기 실패(%s): %s", path, exc)
    return saved


def write_daily_workbook(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = read_user_status(path)
    wb = Workbook()
    ws = wb.active
    ws.title = "입찰정보"
    for idx, field in enumerate(FIELDS, start=1):
        ws.cell(1, idx, field)
    for row, item in enumerate(items, start=2):
        old = saved.get((str(item["공고번호"]), str(item["공고명"])), {})
        for field in ("신청완료여부", "다음행동"):
            if old.get(field) not in (None, ""):
                item[field] = old[field]
        for col, field in enumerate(FIELDS, start=1):
            ws.cell(row, col, item.get(field))
    header_fill = PatternFill("solid", fgColor="17365D")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True, name="Malgun Gothic")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=2, max_row=max(2, ws.max_row)):
        for cell in row:
            cell.font = Font(name="Malgun Gothic", size=10)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(FIELDS)), max(1, ws.max_row))
    widths = [22, 48, 21, 21, 21, 24, 16, 11, 18, 38, 15, 34, 22, 14, 35, 18, 21]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.row_dimensions[1].height = 30
    for row in range(2, ws.max_row + 1):
        ws.row_dimensions[row].height = 48
        ws.cell(row, FIELDS.index("기초금액") + 1).number_format = '#,##0"원"'
        ws.cell(row, FIELDS.index("하한율") + 1).number_format = '0.000"%"'
    tmp = path.with_suffix(".xlsx.tmp")
    wb.save(str(tmp))
    os.replace(str(tmp), str(path))


def get_calendar_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar.readonly"]
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def iter_calendars(service):
    token = None
    while True:
        response = service.calendarList().list(pageToken=token, maxResults=250).execute()
        for cal in response.get("items", []):
            name = cal.get("summary", "")
            if "휴일" not in name and "holiday" not in cal.get("id", "").lower():
                yield cal["id"], name
        token = response.get("nextPageToken")
        if not token: break


def iter_events(service, calendar_id):
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=LOOKBACK_DAYS)).isoformat().replace("+00:00", "Z")
    time_max = (now + timedelta(days=LOOKAHEAD_DAYS)).isoformat().replace("+00:00", "Z")
    token = None
    while True:
        response = service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy="startTime", maxResults=2500, pageToken=token,
        ).execute()
        for event in response.get("items", []):
            yield event
        token = response.get("nextPageToken")
        if not token: break


def main():
    setup_logging()
    if not Path(SERVICE_ACCOUNT_FILE).is_file():
        raise FileNotFoundError("Google Calendar 인증파일 없음: %s" % SERVICE_ACCOUNT_FILE)
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    service = get_calendar_service()
    bid_number_index = build_bid_number_index(service)
    target_date = os.environ.get("BID_TARGET_DATE") or datetime.now(KST).strftime("%Y-%m-%d")
    written = skipped = 0
    items = []
    seen = set()
    for calendar_id, calendar_name in SOURCE_CALENDARS:
        logging.info("캘린더 조회: %s", calendar_name)
        for event in iter_events(service, calendar_id):
            item = parse_event(event, calendar_name)
            if not item:
                skipped += 1
                continue
            if item["입찰개시일시"][:10] != target_date:
                continue
            item = enrich_bid_number(item, bid_number_index)
            key = (item["공고번호"], item["공고명"], item["입찰개시일시"])
            if key in seen: continue
            seen.add(key)
            items.append(item)
    items.sort(key=lambda x: (x["입찰개시일시"], x["협정마감일시"] or "9999", x["입찰마감일시"] or "9999", x["공고명"]))
    if items:
        path = daily_workbook_path(target_date)
        write_daily_workbook(path, items)
        written = len(items)
        logging.info("일자별 통합파일 생성/갱신: %s (%d건)", path, written)
    logging.info("완료: 생성/갱신=%d, 제외/개시일없음=%d", written, skipped)


if __name__ == "__main__":
    main()
