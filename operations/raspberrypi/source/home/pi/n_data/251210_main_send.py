
# -*- coding: utf-8 -*-

"""

main_send.py — 2025 통합 리팩토링 버전

대표지역 자동 분류 + 수신자 결정(region_filter 기반) + 조회기간 15일 제한

"""



import os
import sys
import json
import time
import math
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import requests
import pandas as pd
import argparse
import shutil

def backup_and_rotate_excels():
    """
    RAW_DIR / SPLIT_DIR / REPORT_DIR 의 .xlsx 및 .html 파일에 대해:
    - 1일 지난 파일: backup/ 로 이동
    - backup/ 폴더 내에서 15일 지난 파일 삭제
    """

    def process_dir(base_dir):
        backup_dir = base_dir / "backup"
        backup_dir.mkdir(exist_ok=True)

        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        fifteen_days_ago = now - timedelta(days=15)

        # --------------------------
        # 1일 지난 파일 → backup 이동
        # --------------------------
        for f in base_dir.glob("*.*"):
            if f.is_file() and f.name != "backup":
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < one_day_ago:
                    dst = backup_dir / f.name
                    try:
                        shutil.move(str(f), str(dst))
                        log(f"[BACKUP] moved {f} -> {dst}")
                    except Exception as e:
                        log(f"[BACKUP][ERR] {f}: {e}")

        # --------------------------
        # 15일 지난 backup 파일 삭제
        # --------------------------
        for bf in backup_dir.glob("*.*"):
            if bf.is_file():
                mtime = datetime.fromtimestamp(bf.stat().st_mtime)
                if mtime < fifteen_days_ago:
                    try:
                        bf.unlink()
                        log(f"[ROTATE] deleted old backup: {bf}")
                    except Exception as e:
                        log(f"[ROTATE][ERR] {bf}: {e}")

    # RAW / SPLIT / REPORT 각각 처리
    process_dir(RAW_DIR)
    process_dir(SPLIT_DIR)
    process_dir(REPORT_DIR)

def parse_args():
    """
    명령줄 옵션 처리:
    --hours : 조회 기간(시간 단위)
    --no-send : 알림톡 발송 금지
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="조회 기간(시간 단위)"
    )
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="알림톡 전송 생략"
    )

    return parser.parse_args()
import fcntl

LOCK_FILE = "/home/pi/n_data/main_send.lock"

def acquire_lock():
    """
    중복 실행 방지용 파일 락
    lock_fd를 반환하며, 반환값이 None이면 이미 다른 프로세스가 실행 중인 것.
    """
    try:
        fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o666)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # non-blocking
        return fd
    except BlockingIOError:
        print("[LOCK] Another instance is already running.")
        return None
    except Exception as e:
        print(f"[LOCK][ERR] {e}")
        return None
# ----------------------------------------------------------
# 실행 상태(last_run) 관리
# ----------------------------------------------------------
def load_last_run_ts():
    """
    직전 실행 시각(last_run.txt)을 읽어 datetime으로 반환.
    파일이 없거나 손상돼 있으면 None 반환.
    """
    if not LAST_RUN_FILE.exists():
        log("[STATE] last_run.txt 없음")
        return None

    try:
        txt = LAST_RUN_FILE.read_text().strip()
        if not txt:
            return None
        dt = datetime.strptime(txt, "%Y%m%d%H%M")
        return dt
    except Exception as e:
        log(f"[STATE][ERR] last_run 읽기 실패: {e}")
        return None


def save_last_run_ts(dt: datetime):
    """
    실행 종료 직후의 시각을 last_run.txt 파일에 저장.
    """
    try:
        LAST_RUN_FILE.write_text(dt.strftime("%Y%m%d%H%M"))
        log(f"[STATE] last_run 저장 완료: {dt.strftime('%Y%m%d%H%M')}")
    except Exception as e:
        log(f"[STATE][ERR] last_run 저장 실패: {e}")
    
# ---------------------------------------------

# region_filter 모듈에서 규칙 가져오기

# ---------------------------------------------

from seri_n_data.region_filter import (

    classify_region,

    decide_receivers,

)

# ---------------------------------------------
# 공통 설정
# ---------------------------------------------

# 로컬 작업 디렉토리 (코드/상태/키 파일)
BASE_DIR = Path("/home/pi/n_data")

# NAS 결과물 디렉토리 (/mnt/vol1 는 CIFS 마운트)
NAS_BASE = Path("/mnt/vol1/n_data")

# 엑셀/리포트 저장 위치는 NAS 기준
RAW_DIR = NAS_BASE / "raw"
SPLIT_DIR = NAS_BASE / "split"
REPORT_DIR = NAS_BASE / "report"

RAW_DIR.mkdir(parents=True, exist_ok=True)
SPLIT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# 실행 상태/키 파일은 로컬에 유지
LAST_RUN_FILE = BASE_DIR / "last_run.txt"
API_KEY_FILE = BASE_DIR / "bid_api_key.txt"

TARGET_INDS = ["0037", "0038", "0039", "0040", "6202"]

# 조회기간 최대 15일
MAX_DAYS = 15   # 조회기간 제한 — 최대 15일

# ---------------------------------------------

# 로깅 유틸

# ---------------------------------------------

def log(msg):

    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    print(ts, msg)



# ---------------------------------------------

# 날짜 포맷

# ---------------------------------------------

def ymdhm(dt: datetime):

    return dt.strftime("%Y%m%d%H%M")



# ---------------------------------------------

# API 호출 유틸

# ---------------------------------------------

def load_api_key():

    if not API_KEY_FILE.exists():

        raise RuntimeError("API 키 파일 없음: " + str(API_KEY_FILE))

    return API_KEY_FILE.read_text().strip()



# ---------------------------------------------

# API 요청 (단일 페이지)

# ---------------------------------------------

def fetch_api_page(ind_code: str, start: str, end: str, page: int, api_key: str):

    """

    ind_code : 공고업종코드 (0037 / 0038 / 0039 / 0040 / 6202)

    start, end : YYYYMMDDHHMM 문자열

    """

    base_url = (

        "http://apis.data.go.kr/1230000/"

        "REDACTED_LONG_LITERAL"

    )



    params = {

        "serviceKey": api_key,

        "pageNo": page,

        "numOfRows": 100,

        "inqryDiv": "1",

        "inqryBgnDt": start,

        "inqryEndDt": end,

        "indstrytyNm": ind_code,

        "type": "json",

    }



    r = requests.get(base_url, params=params, timeout=10)



    try:

        data = r.json()

    except Exception:

        log("[HTTP][ERROR] JSON 파싱 실패")

        return []



    items = (

        data.get("response", {})

            .get("body", {})

            .get("items", [])

    )



    return items if items else []





# ---------------------------------------------

# API 전체 페이징 조회

# ---------------------------------------------

def fetch_all_pages(ind_code: str, start: str, end: str, api_key: str):

    log(f"[FETCH] ind={ind_code} from {start} to {end}")



    rows = []



    # 첫 페이지를 가져와 item 수 확인

    first = fetch_api_page(ind_code, start, end, 1, api_key)

    count = len(first)



    log(f"[HTTP] ind={ind_code} page=1 count={count}")



    if count == 0:

        log(f"[HTTP] ind={ind_code} total=0")

        return []



    rows.extend(first)



    # 페이지 수 = 총 100개 단위

    total_pages = math.ceil(count / 100)

    log(f"[HTTP] ind={ind_code} total={count}")



    # 나머지 페이지

    for p in range(2, total_pages + 1):

        time.sleep(0.3)

        items = fetch_api_page(ind_code, start, end, p, api_key)

        log(f"[HTTP] ind={ind_code} page={p} count={len(items)}")

        rows.extend(items)



    return rows





# ---------------------------------------------

# 전체 업종 조회

# ---------------------------------------------

def fetch_all_industries(start: str, end: str):

    api_key = load_api_key()



    all_rows = []

    for ind in TARGET_INDS:

        items = fetch_all_pages(ind, start, end, api_key)

        all_rows.extend(items)



    log(f"[FETCH] total rows = {len(all_rows)}")

    return all_rows





# ---------------------------------------------

# DataFrame 정규화

# ---------------------------------------------

def normalize_rows(rows):

    """

    API 응답 JSON → DataFrame 형태의 표준화된 dict로 정리

    """



    normalized = []



    for raw in rows:

        row = {

            "공고업종코드": raw.get("indstrytyNm", ""),

            "공고번호": raw.get("bidNtceNo", ""),

            "차수": raw.get("bidNtceOrd", ""),

            "공고명": raw.get("bidNtceNm", ""),

            "입찰마감일시": raw.get("bidClseDt", ""),

            "게시일시": raw.get("bidNtceDt", ""),

            "추정금액": parse_amount(raw),

            "원문": raw,

        }

        normalized.append(row)



    return normalized





# ---------------------------------------------

# 추정금액 파싱

# ---------------------------------------------

def parse_amount(raw):

    """

    presmptPrce 또는 bdgtAmt 등에서 금액을 정리

    """

    v = (

        raw.get("presmptPrce")

        or raw.get("bdgtAmt")

        or raw.get("indutyVAT")

        or raw.get("VAT")

    )



    if not v:

        return 0



    try:

        return int(str(v).replace(",", "") or 0)

    except Exception:

        return 0
def collect_data(bgn_dt: str, end_dt: str):
    """
    전체 업종(TARGET_INDS)에 대해 조회 기간(bgn_dt~end_dt) 내 데이터를 수집하고
    normalize_rows() 를 적용한 리스트(dict) 형태로 반환한다.
    """
    try:
        # 1) API 에서 원본 row 전체 수집
        raw_rows = fetch_all_industries(bgn_dt, end_dt)

        if not raw_rows:
            log("[COLLECT] 조회 결과 없음")
            return []

        # 2) 표준화(normalize)
        rows = normalize_rows(raw_rows)

        # 3) 대표지역 자동 분류
        apply_region_classification(rows)

        # 4) 수신자 결정 (region_filter 기반)
        apply_receivers(rows)

        return rows

    except Exception as e:
        log(f"[COLLECT][ERR] 데이터 수집 중 오류: {e}")
        return []
def filter_rows(rows):
    """
    공고 row 리스트(dict)를 받아 다음을 수행:
    - 필수 필드 누락 제거
    - '공고번호+차수' 기준 중복 제거
    """

    if not rows:
        return []

    filtered = []
    seen = set()   # (공고번호, 차수) 저장

    for row in rows:
        bid_no = str(row.get("공고번호") or "").strip()
        bid_ord = str(row.get("차수") or "").strip()

        # 필수값 체크
        if not bid_no:
            continue

        key = (bid_no, bid_ord)
        if key in seen:
            # 중복 공고 제거
            continue

        seen.add(key)
        filtered.append(row)

    log(f"[FILTER] after duplicate-removal = {len(filtered)}")
    return filtered
def _fetch_prtcpt_region_map_for_rows(rows):
    """
    rows: dict 리스트 (공고번호, 차수, 원문 포함)
    return: { "공고번호-차수": [지역1, 지역2, ...], ... }
    참가가능지역 API를 조회해 mapping 을 만든다.
    조회 실패하면 빈 dict 반환.
    """

    result = {}
    
    # 참가가능지역 API URL (공공데이터 포맷 동일)
    api_url = (
        "http://apis.data.go.kr/1230000/"
        "REDACTED_LONG_LITERAL"
    )

    api_key = load_api_key()

    for row in rows:
        raw = row.get("원문") or {}
        bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "")
        bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "")

        if not bid_no:
            continue

        key = f"{bid_no}-{bid_ord}"
        params = {
            "serviceKey": api_key,
            "bidNtceNo": bid_no,
            "bidNtceOrd": bid_ord,
            "type": "json",
        }

        try:
            r = requests.get(api_url, params=params, timeout=5)
            data = r.json()

            items = (
                data.get("response", {})
                    .get("body", {})
                    .get("items", [])
            )

            region_list = []
            for it in items:
                nm = it.get("prtcptPossRgnNm")
                if nm:
                    region_list.append(nm.strip())

            result[key] = region_list

        except Exception as e:
            log(f"[PRTCPT][ERR] API 조회 실패 ({key}): {e}")
            result[key] = []

    return result
def _build_rep_region_from_prtcpt(rgn_list, fallback):
    """
    참가가능지역 리스트(rgn_list)를 기반으로 대표지역을 결정.
    rgn_list가 비어 있으면 fallback 사용.
    여러 지역일 경우 규칙에 따라 대표지역을 선택.
    """

    # 참가가능지역 정보가 없으면 기존 대표지역 사용
    if not rgn_list:
        return fallback

    # 문자열 정규화
    normalized = []
    for nm in rgn_list:
        nm = str(nm)
        if "대구" in nm:
            normalized.append("대구")
        elif "경북" in nm:
            normalized.append("경북")
        elif "충북" in nm:
            normalized.append("충북")
        elif "충남" in nm:
            normalized.append("충남")
        elif "전북" in nm:
            normalized.append("전북")
        elif "전남" in nm:
            normalized.append("전남")
        elif "경기" in nm:
            normalized.append("경기")
        elif "강원" in nm:
            normalized.append("강원")
        else:
            normalized.append(nm)

    # 대구+경북 같이 존재 → 대구경북
    if "대구" in normalized and "경북" in normalized:
        return "대구경북"

    # 한 지역만 존재하면 바로 그 지역 사용
    if len(normalized) == 1:
        return normalized[0]

    # 여러 지역이지만 특별 조합이 아닐 때 → 첫 지역 사용
    return normalized[0]

# ---------------------------------------------

# 대표지역 자동 생성 (region_filter 기반)

# ---------------------------------------------

def apply_region_classification(rows):

    """

    rows: normalize_rows() 결과 리스트(dict)

    → 각 row에 '대표지역' 필드 생성

    """

    for row in rows:

        region_text = " ".join([

            str(row.get("공동도급지역") or ""),

            str(row.get("수요지역") or ""),

            str(row.get("지역명") or ""),

            str(row.get("공고명") or "")

        ])



        row["대표지역"] = classify_region(region_text)





# ---------------------------------------------

# 수신자 결정

# ---------------------------------------------

def apply_receivers(rows):

    """

    decide_receivers(row) 를 사용하여

    수신번호 / 알림대상 필드 자동 생성

    """

    for row in rows:

        receivers = decide_receivers(row)

        row["수신번호"] = ",".join(receivers) if receivers else ""

        row["알림대상"] = "Y" if receivers else "N"





# ---------------------------------------------

# 조회기간 제한 (15일 초과 방지)

# ---------------------------------------------

def adjust_period_by_limit(start_dt: datetime, end_dt: datetime):

    """

    end_dt - start_dt > MAX_DAYS(15)이면 강제로 15일로 제한

    """

    diff = end_dt - start_dt

    if diff.days > MAX_DAYS:

        log(f"[PERIOD] 조회 범위가 {diff.days}일임 → 15일로 자동 조정")

        start_dt = end_dt - timedelta(days=MAX_DAYS)

    return start_dt, end_dt

# ============================================================

# SECTION 4 — Excel 저장, 지역별 split, 리포트 생성

# ============================================================



from openpyxl import Workbook

from openpyxl.utils import get_column_letter


# ------------------------------------------------------------

# 엑셀 저장 (raw 전체)

# ------------------------------------------------------------

def save_raw_excel(rows, timestamp):

    if not rows:

        return None



    filename = f"입찰공고_{timestamp}.xlsx"

    out_path = RAW_DIR / filename



    df = pd.DataFrame(rows)

    df.to_excel(out_path, index=False)



    log(f"[SAVE] {out_path}")

    return out_path





# ------------------------------------------------------------

# 지역별 split 저장

# ------------------------------------------------------------

def save_split_by_region(rows, timestamp):

    """

    rows: 대표지역 이미 분류됨

    """

    if not rows:

        return []



    df = pd.DataFrame(rows)



    results = []



    for region in df["대표지역"].unique():

        region_df = df[df["대표지역"] == region].copy()

        fname = f"입찰공고_{timestamp}_{region}.xlsx"

        out = SPLIT_DIR / fname

        region_df.to_excel(out, index=False)

        results.append(out)

        log(f"[SAVE] split for region={region} -> {out}")



    return results





# ------------------------------------------------------------

# 리포트 HTML / XLSX 생성

# ------------------------------------------------------------

def generate_html_report(rows, timestamp):

    """

    rows: 리스트(dict)

    """

    df = pd.DataFrame(rows)

    out_html = REPORT_DIR / f"입찰리포트_{timestamp}.html"



    try:

        df.to_html(out_html, index=False)

        log(f"[REPORT] HTML 생성: {out_html}")

    except Exception as e:

        log(f"[REPORT][ERR] HTML 생성 실패: {e}")



    return out_html





def generate_excel_report(rows, timestamp):

    """

    rows: 리스트(dict)

    """

    df = pd.DataFrame(rows)

    out_xlsx = REPORT_DIR / f"입찰리포트_{timestamp}.xlsx"



    try:

        df.to_excel(out_xlsx, index=False)

        log(f"[REPORT] EXCEL 생성: {out_xlsx}")

    except Exception as e:

        log(f"[REPORT][ERR] EXCEL 생성 실패: {e}")



    return out_xlsx





# ------------------------------------------------------------

# Index HTML 자동 생성

# ------------------------------------------------------------

def update_report_index():

    """

    REPORT_DIR 아래의 HTML 파일 목록을 index로 정리

    """

    index_file = REPORT_DIR / "입찰리포트_index.html"



    try:

        html_files = sorted(REPORT_DIR.glob("입찰리포트_*.html"))

        lines = [

            "<html><body><h2>입찰 리포트 Index</h2><ul>"

        ]



        for f in html_files:

            name = f.name

            lines.append(f'<li><a href="{name}">{name}</a></li>')



        lines.append("</ul></body></html>")



        index_file.write_text("\n".join(lines), encoding="utf-8")



        log(f"[REPORT] index HTML 갱신: {index_file}")



    except Exception as e:

        log(f"[REPORT][ERR] index 생성 실패: {e}")

# ============================================================

# SECTION 5 — main() 실행 루프 (최종 완성본)

# ============================================================



def main():
    args = parse_args()

    # 조회기간 제한(15일) — MAX_DAYS 기준으로 자동 조정
    max_hours = MAX_DAYS * 24
    if args.hours > max_hours:
        log(f"[MAIN][ADJUST] --hours={args.hours} → {max_hours}으로 자동 조정")
        args.hours = max_hours

    # 중복 실행 방지 락
    lock_fd = acquire_lock()
    if lock_fd is None:
        return

    start_ts = datetime.now()
    now_ts = start_ts
    success = False

    log("[MAIN] === main_send.py START ===")

    # 매 실행마다 오래된 엑셀 백업/정리
    backup_and_rotate_excels()

    try:
        # ----------------------------------------------------
        # 조회 기간 계산: last_run 기반
        # ----------------------------------------------------
        last_run = load_last_run_ts()
        if last_run and last_run < now_ts:
            bgn_ts = last_run
            log(f"[MAIN] last_run 기반 조회 시작: {bgn_ts.strftime('%Y%m%d%H%M')}")
        else:
            bgn_ts = now_ts - timedelta(hours=args.hours)
            log(f"[MAIN] last_run 없음/이상 → --hours 기준 조회 적용")

        # 조회 범위가 15일 초과하면 강제 조정
        if now_ts - bgn_ts > timedelta(days=MAX_DAYS):
            bgn_ts = now_ts - timedelta(days=MAX_DAYS)
            log(f"[MAIN][ADJUST] 조회 범위 15일 제한 적용")

        # API 포맷
        bgn_dt = bgn_ts.strftime("%Y%m%d%H%M")
        end_dt = now_ts.strftime("%Y%m%d%H%M")
        log(f"[MAIN] 조회기간 {bgn_dt} ~ {end_dt}")

        # ----------------------------------------------------
        # 공고 수집
        # ----------------------------------------------------
        raw_rows = collect_data(bgn_dt, end_dt)
        log(f"[FETCH] total rows = {len(raw_rows)}")

        # 1차 필터링(공종·금액·기본 제외조건)
        rows = filter_rows(raw_rows)
        log(f"[FILTER] filtered rows = {len(rows)}")

        # Pandas DataFrame
        df = pd.DataFrame(rows)

        # ----------------------------------------------------
        # 알림톡 발송 (region_filter 규칙 적용 후)
        # ----------------------------------------------------
        if not args.no_send:
            try:
                send_kakao_tb0485(df)
            except Exception as e:
                log(f"[SEND][ERR] 전송 실패: {e}")
        else:
            log("[MAIN] --no-send 옵션 → 알림톡 전송 생략")

        # 발송 후 df → dict 리스트로 복구
        rows_after_send = df.to_dict(orient="records")

        # ----------------------------------------------------
        # 엑셀용 부가 컬럼 세팅
        # ----------------------------------------------------
        for row in rows_after_send:
            raw = row.get("원문") or {}
            row["지역태그"] = str(raw.get("jntcontrctDutyRgnNm1", "")).strip()
            row["심사기준"] = str(raw.get("aplBssCntnts", "")).strip()

        # ----------------------------------------------------
        # 참가가능지역 API 기반 대표지역 보정
        # ----------------------------------------------------
        prtcpt_map = {}
        try:
            prtcpt_map = _fetch_prtcpt_region_map_for_rows(rows_after_send)
        except Exception as e:
            log(f"[PRTCPT][ERR] 참가가능지역 조회 실패: {e}")

        for row in rows_after_send:
            raw = row.get("원문") or {}
            bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "")
            bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "")
            key = f"{bid_no}-{bid_ord}"

            fallback = str(row.get("대표지역") or "").strip()
            rgn_list = prtcpt_map.get(key, [])

            # 참가가능지역 보정 수행
            new_rep = _build_rep_region_from_prtcpt(rgn_list, fallback)
            if new_rep:
                row["대표지역"] = new_rep

        # ----------------------------------------------------
        # 대표지역 추가 후 — 대구/경북 분리 재정규화
        # ----------------------------------------------------
        for row in rows_after_send:
            rep = row.get("대표지역", "")
            if "대구" in rep and "경북" in rep:
                row["대표지역"] = "대구경북"
            elif "대구" in rep:
                row["대표지역"] = "대구"
            elif "경북" in rep:
                row["대표지역"] = "경북"

        # ----------------------------------------------------
        # Excel 저장
        # ----------------------------------------------------
        timestamp = now_ts.strftime("%Y%m%d_%H%M")

        raw_xlsx = save_raw_excel(rows_after_send, timestamp)
        if not raw_xlsx:
            # 조회 결과는 없지만, 조회 자체는 정상 수행된 것으로 보고 last_run 갱신
            log("[MAIN] 저장할 내용 없음. 조회만 수행됨.")
            success = True
            return


        # 지역별 Split 저장
        save_split_by_region(rows_after_send, timestamp)

        # 리포트 생성
        generate_html_report(rows_after_send, timestamp)
        generate_excel_report(rows_after_send, timestamp)
        update_report_index()

        success = True

    except Exception as e:
        log(f"[FATAL] main() exception: {e}")
        log(traceback.format_exc())
    finally:
        # 정상 종료 시 last_run 갱신
        if success:
            save_last_run_ts(now_ts)

        if lock_fd:
            try:
                os.close(lock_fd)
            except Exception:
                pass

        log(f"[MAIN] === main_send.py END ===")

if __name__ == "__main__":
    main()


