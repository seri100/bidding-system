

# -*- coding: utf-8 -*-
"""
gcal_sync.py
- main_send_clean.py 와 동일한 수집/정규화 파이프라인 사용
- 공종: 기계설비(6202), 소방설비(0038, 0039, 0040)
- 지역: 전국 → 🔔ㅁ  /  충북·충북청주시 → 🔔ㅇ  /  세종 → 🔔?
- Google Calendar에 입찰마감일시 기준 이벤트 등록 (중복 방지)
- 실행: python gcal_sync.py [--hours N] [--no-send]
"""

import os
import sys
import argparse
import pickle
import traceback
from pathlib import Path
from datetime import datetime, timedelta

# ── Google Calendar API ──────────────────────────────────────
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ── main_send_clean 공용 로직 재사용 ─────────────────────────
# main_send_clean.py 가 같은 디렉터리에 있다고 가정
sys.path.insert(0, str(Path(__file__).parent))

from main_send import (
    load_api_key,
    collect_ppssrch,
    collect_cnstwk,
    merge_raw_rows,
    normalize_row,
    ymdhm,
    log,
    env_guard,
    MIN_BUDGET,
)

# ============================================================
# 설정
# ============================================================

# 동기화 대상 공종 코드
#   6202 = 기계설비 (main_send_clean 의 TARGET_INDS 중 기계설비)
#   0038/0039/0040 = 소방설비
CAL_TARGET_INDS = {"6202", "0038", "0039", "0040"}

# Google Calendar
SCOPES      = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "primary"           # 기본 캘린더. 전용 캘린더 ID로 교체 가능

# 인증 파일 경로 (NAS 또는 로컬)
NAS_BASE   = Path(os.environ.get("N_DATA_BASE", "/mnt/vol1/bid/n_data"))
CREDS_PATH = NAS_BASE / "credentials.json"   # Google OAuth 클라이언트 시크릿
TOKEN_PATH = NAS_BASE / "gcal_token.pickle"  # 자동 저장·갱신 토큰

# 봇 식별 이모티콘
BOT_EMOJI = "🔔"

# 이벤트 색상 (Google Calendar colorId)
#   9=Blueberry(파랑·전국), 10=Sage(초록·충북), 5=Banana(노랑·세종)
COLOR_MAP = {"ㅁ": "9", "ㅇ": "10", "?": "5"}

# ============================================================
# 지역 심볼 결정
# ============================================================

def get_symbol(row):
    """
    대표지역 / local_region 을 분석해 심볼 반환
      전국(scope=전국)          → ㅁ
      충북 · 충북청주시 제한    → ㅇ
      세종 제한                 → ?
      그 외 (대구·경북 등)      → None (동기화 제외)
    """
    scope  = str(row.get("scope", "")).strip()
    region = str(row.get("local_region") or row.get("대표지역") or "").strip()
    rep    = str(row.get("대표지역", "")).strip()

    # 전국 판정
    if scope == "전국" or rep == "전국":
        return "ㅁ"

    target = region + " " + rep  # 두 필드 합쳐서 검사

    # 충북 / 청주시
    if any(k in target for k in ("충청북도", "충북", "청주시")):
        return "ㅇ"

    # 세종
    if "세종" in target:
        return "?"

    return None   # 동기화 대상 아님


# ============================================================
# Google Calendar 인증
# ============================================================

def get_calendar_service():
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
        log("[GCAL] 토큰 저장 완료: %s" % TOKEN_PATH)

    return build("calendar", "v3", credentials=creds)


# ============================================================
# 중복 이벤트 체크
# ============================================================

def is_duplicate_event(service, notice_no, deadline_dt):
    """
    공고번호가 이미 캘린더에 등록돼 있으면 True
    마감일 ±2일 범위의 이벤트 description 을 검색
    """
    time_min = (deadline_dt - timedelta(days=2)).isoformat() + "Z"
    time_max = (deadline_dt + timedelta(days=2)).isoformat() + "Z"

    try:
        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        for ev in result.get("items", []):
            if notice_no in ev.get("description", ""):
                return True
    except Exception as e:
        log("[GCAL][중복체크 오류] %s" % e)

    return False


# ============================================================
# 이벤트 내용 생성
# ============================================================

def make_title(row, symbol):
    """
    예: 🔔ㅇ 서원 국민체육센터 건립사업 기계공사
        충북
    → 한 줄 제목: 🔔ㅇ 서원 국민체육센터 건립사업 기계공사 충북
    """
    name   = row.get("공고명", "")
    region = row.get("대표지역", "") or row.get("local_region", "")
    return f"{BOT_EMOJI}{symbol} {name} {region}"


def make_description(row, symbol):
    """
    요청하신 포맷 그대로:

    🔔ㅇ 서원 국민체육센터 건립사업 기계공사-10
    충북

    공고명 : 서원 국민체육센터 건립사업 기계공사
    입찰마감일시 : 2026-05-20 12:00:00
    추정금액 : 1,516,263,637원
    공고번호 : R26BK01501554 - 000
    """
    name      = row.get("공고명", "")
    region    = row.get("대표지역", "") or row.get("local_region", "")
    deadline  = row.get("입찰마감일시", "")
    amount    = row.get("추정금액", 0) or row.get("추정가격", 0) or 0
    notice_no = row.get("공고번호", "")
    bid_ord   = row.get("차수", "000")
    org       = row.get("발주기관", "")
    ind_nm    = row.get("공고업종명", "")
    method    = row.get("낙찰방법세부기준", "")
    detail    = row.get("detail_url", "")

    try:
        amount_str = f"{int(amount):,}"
    except Exception:
        amount_str = str(amount)

    # 공고번호 표시: "R26BK01501554 - 000" 형식
    notice_display = f"{notice_no} - {bid_ord}"

    return (
        f"{BOT_EMOJI}{symbol} {name}\n"
        f"{region}\n"
        f"\n"
        f"공고명 : {name}\n"
        f"입찰마감일시 : {deadline}\n"
        f"추정금액 : {amount_str}원\n"
        f"공고번호 : {notice_display}\n"
        f"\n"
        f"발주기관 : {org}\n"
        f"업종 : {ind_nm}\n"
        f"낙찰방법 : {method}\n"
        f"상세URL : {detail}"
    )


# ============================================================
# 캘린더 이벤트 등록
# ============================================================

def create_event(service, row, symbol, no_send=False):
    """
    입찰마감일시를 이벤트 시작 시각으로 등록
    알림: 마감 24시간 전 / 2시간 전
    """
    deadline_str = row.get("입찰마감일시", "")
    notice_no    = row.get("공고번호", "")
    name         = row.get("공고명", "")

    # ── 날짜 파싱 ─────────────────────────────────────────────
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            deadline_dt = datetime.strptime(deadline_str, fmt)
            break
        except ValueError:
            continue
    else:
        log("[GCAL][날짜파싱 실패] %s / %s" % (notice_no, deadline_str))
        return False

    if no_send:
        log("[GCAL][DRY RUN] %s%s %s (%s)" % (BOT_EMOJI, symbol, name, notice_no))
        return False

    # ── 중복 체크 ─────────────────────────────────────────────
    if is_duplicate_event(service, notice_no, deadline_dt):
        log("[GCAL][중복 SKIP] %s / %s" % (notice_no, name))
        return False

    # ── 이벤트 Body ───────────────────────────────────────────
    event_body = {
        "summary":     make_title(row, symbol),
        "description": make_description(row, symbol),
        "start": {
            "dateTime": deadline_dt.isoformat(),
            "timeZone": "Asia/Seoul",
        },
        "end": {
            "dateTime": (deadline_dt + timedelta(hours=1)).isoformat(),
            "timeZone": "Asia/Seoul",
        },
        "colorId": COLOR_MAP.get(symbol, "1"),
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60 * 24},   # D-1 알림
                {"method": "popup", "minutes": 60 * 2},    # 2시간 전 알림
            ],
        },
    }

    try:
        created = service.events().insert(
            calendarId=CALENDAR_ID, body=event_body
        ).execute()
        log(
            "[GCAL][등록 완료] %s%s %s | 마감:%s | %s"
            % (BOT_EMOJI, symbol, name, deadline_str, created.get("htmlLink", ""))
        )
        return True
    except Exception as e:
        log("[GCAL][등록 오류] %s / %s → %s" % (notice_no, name, e))
        return False


# ============================================================
# 메인
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser(description="입찰공고 Google Calendar 동기화")
    ap.add_argument("--hours",   type=int,  default=1,     help="수집 기간(시간 단위, 기본 1)")
    ap.add_argument("--no-send", action="store_true",      help="DRY RUN: 캘린더 등록 생략")
    return ap.parse_args()


def main():
    # ── 환경 검증 (main_send_clean 과 동일) ───────────────────
    env_guard()
    args = parse_args()

    now   = datetime.now()
    start = now - timedelta(hours=max(1, args.hours))
    bgn   = ymdhm(start)
    end   = ymdhm(now)

    log("[GCAL_SYNC] 시작: %s ~ %s  no_send=%s" % (bgn, end, args.no_send))

    # ── 데이터 수집 ───────────────────────────────────────────
    api_key  = load_api_key()
    pps_rows = collect_ppssrch(api_key, bgn, end)
    cnt_rows = collect_cnstwk(api_key, bgn, end)
    raw_rows = merge_raw_rows(pps_rows, cnt_rows)
    log("[GCAL_SYNC] 병합 raw rows=%d" % len(raw_rows))

    # ── 정규화 + 필터 ─────────────────────────────────────────
    rows = []
    for raw in raw_rows:
        row = normalize_row(raw)

        # 공종 필터 (기계설비 + 소방설비)
        if row["공고업종코드"] not in CAL_TARGET_INDS:
            continue

        # 최소 추정금액 필터
        if row["추정금액"] < MIN_BUDGET and row["추정가격"] < MIN_BUDGET:
            continue

        # 지역 심볼 결정 (None = 대상 아님)
        symbol = get_symbol(row)
        if symbol is None:
            continue

        row["_cal_symbol"] = symbol
        rows.append(row)

    log("[GCAL_SYNC] 필터 후 대상 rows=%d" % len(rows))

    if not rows:
        log("[GCAL_SYNC] 동기화할 공고 없음. 종료.")
        return

    # ── Google Calendar 연결 ──────────────────────────────────
    if not args.no_send:
        service = get_calendar_service()
        log("[GCAL_SYNC] Calendar API 연결 완료")
    else:
        service = None
        log("[GCAL_SYNC] DRY RUN 모드 — Calendar 연결 생략")

    # ── 이벤트 등록 ───────────────────────────────────────────
    ok_count   = 0
    skip_count = 0
    fail_count = 0

    for row in rows:
        symbol = row["_cal_symbol"]
        result = create_event(service, row, symbol, no_send=args.no_send)

        if args.no_send:
            skip_count += 1
        elif result:
            ok_count += 1
        else:
            skip_count += 1

    # ── 결과 요약 ─────────────────────────────────────────────
    log("=" * 60)
    log("[GCAL_SYNC] 완료 요약")
    log("  등록 성공 : %d건" % ok_count)
    log("  스킵/중복 : %d건" % skip_count)
    log("  심볼 기준 :")
    log("    %sㅁ = 전국 공고       (파란색 이벤트)" % BOT_EMOJI)
    log("    %sㅇ = 충북·청주시 제한 (초록색 이벤트)" % BOT_EMOJI)
    log("    %s? = 세종 제한        (노란색 이벤트)" % BOT_EMOJI)
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("[FATAL] %s: %s" % (type(e).__name__, e))
        traceback.print_exc()
        sys.exit(1)
