# -*- coding: utf-8 -*-
"""
낙찰정보 DB 수집 공통 모듈 (운영 안정화 버전)

개선 사항
- inqryDiv 매핑 반영
- 공고번호 단건조회 시 자동 inqryDiv=4
- 429 / 5xx / 빈 응답 / JSON 오류 재시도
- items / items.item 구조 모두 정규화
- 등록일시/개찰일시/공고번호 기준 로컬 후처리
- 로컬 중복 제거
- UPSERT 공통화
- logging 기반 운영 로그
"""

from __future__ import annotations

import logging
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymysql
import requests


# =========================================================
# 기존 운영값 유지
# =========================================================
API_KEY = "REDACTED_PRIVATE_VALUE"
BASE_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"

ENDPOINTS = {
    "물품": "getScsbidListSttusThng",
    "공사": "getScsbidListSttusCnstwk",
}

DB_CONFIG = dict(
    host="192.168.0.250",
    port=3306,
    user="seri825",
    password="REDACTED_PRIVATE_VALUE",
    db="seridb",
    charset="utf8",
    autocommit=False,
)

DEFAULT_ROWS_PER_PAGE = 100
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_PER_PAGE = 5
DEFAULT_SLEEP_SEC = 1.5
DEFAULT_DB_RETRY = 3


# =========================================================
# 로깅
# =========================================================
def build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# =========================================================
# inqryDiv 매핑
# =========================================================
class InqryDiv(IntEnum):
    REG_DATE = 1       # 등록일시
    NOTICE_DATE = 2    # 공고일시 (응답상 재검증 제한적)
    OPEN_DATE = 3      # 개찰일시
    BID_NO = 4         # 입찰공고번호


INQRY_DIV_LABELS = {
    InqryDiv.REG_DATE: "등록일시 조회",
    InqryDiv.NOTICE_DATE: "공고일시 조회(실측 추정)",
    InqryDiv.OPEN_DATE: "개찰일시 조회",
    InqryDiv.BID_NO: "입찰공고번호 조회",
}


# =========================================================
# 예외
# =========================================================
class BidApiError(Exception):
    pass


class BidApiHttpError(BidApiError):
    pass


class BidApiResponseError(BidApiError):
    pass


class BidApiValidationError(BidApiError):
    pass


# =========================================================
# 유틸
# =========================================================
def safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v not in (None, "", "None", "null") else default
    except Exception:
        return default


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "", "None", "null") else default
    except Exception:
        return default


def safe_str(v: Any, maxlen: int = 50) -> Optional[str]:
    if v in (None, "", "None", "null"):
        return None
    return str(v).strip()[:maxlen]


def parse_dt(v: Any) -> Optional[datetime]:
    if not v:
        return None

    s = str(v).strip()
    for fmt, n in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    ):
        try:
            return datetime.strptime(s[:n], fmt)
        except Exception:
            pass
    return None


def fmt_bgn_dt(d: datetime) -> str:
    return d.strftime("%Y%m%d") + "0000"


def fmt_end_dt(d: datetime) -> str:
    return d.strftime("%Y%m%d") + "2359"


def normalize_items(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    API 응답의 items 구조를 모두 흡수:
    1) items: []
    2) items: {"item": []}
    3) items: {"item": {}}
    4) items: {}
    """
    items = body.get("items", [])

    if items is None:
        return []

    if isinstance(items, list):
        return items

    if isinstance(items, dict):
        if "item" in items:
            item = items.get("item", [])
            if item is None:
                return []
            if isinstance(item, list):
                return item
            if isinstance(item, dict):
                return [item]
            return []

        if items:
            return [items]
        return []

    return []


def iter_windows(start_dt: datetime, end_dt: datetime, chunk_days: int):
    cur = start_dt
    step = timedelta(days=chunk_days)

    while cur <= end_dt:
        win_end = min(cur + step - timedelta(days=1), end_dt)
        yield cur, win_end
        cur = win_end + timedelta(days=1)


def build_url(
    endpoint: str,
    page_no: int,
    rows_per_page: int,
    inqry_div: InqryDiv,
    bgn: Optional[datetime] = None,
    end: Optional[datetime] = None,
    bid_no: Optional[str] = None,
) -> str:
    url = (
        f"{BASE_URL}/{endpoint}"
        f"?serviceKey=REDACTED_PRIVATE_VALUE"
        f"&numOfRows={rows_per_page}"
        f"&pageNo={page_no}"
        f"&inqryDiv={int(inqry_div)}"
        f"&type=json"
    )

    if inqry_div == InqryDiv.BID_NO:
        if not bid_no:
            raise BidApiValidationError("inqryDiv=4 에서는 bid_no가 필요합니다.")
        url += f"&bidNtceNo={bid_no}"
    else:
        if not bgn or not end:
            raise BidApiValidationError("inqryDiv=1/2/3 에서는 bgn/end가 필요합니다.")
        url += f"&inqryBgnDt={fmt_bgn_dt(bgn)}"
        url += f"&inqryEndDt={fmt_end_dt(end)}"

    return url


# =========================================================
# HTTP 요청 / 재시도
# =========================================================
def request_json(
    session: requests.Session,
    url: str,
    logger: logging.Logger,
    timeout: int = DEFAULT_TIMEOUT,
    retry_per_page: int = DEFAULT_RETRY_PER_PAGE,
) -> Dict[str, Any]:
    last_error: Optional[Exception] = None

    for attempt in range(1, retry_per_page + 1):
        try:
            resp = session.get(url, timeout=timeout)
            status = resp.status_code

            if status == 429 or 500 <= status <= 599:
                raise BidApiHttpError(f"HTTP {status}")

            if status != 200:
                raise BidApiHttpError(f"HTTP {status}: {resp.text[:300]}")

            text = resp.text.strip()
            if not text:
                raise BidApiResponseError("empty response")

            data = resp.json()

            if "response" not in data:
                raise BidApiResponseError("response 키 없음")

            response = data["response"]
            header = response.get("header", {})
            result_code = str(header.get("resultCode", ""))
            result_msg = str(header.get("resultMsg", ""))

            if result_code and result_code != "00":
                raise BidApiResponseError(f"API resultCode={result_code}, resultMsg={result_msg}")

            return data

        except Exception as e:
            last_error = e
            sleep_sec = min(60, (2 ** attempt) + random.uniform(0.3, 1.2))
            logger.warning(
                "request failed attempt=%s/%s sleep=%.1fs err=%s",
                attempt, retry_per_page, sleep_sec, e
            )
            if attempt < retry_per_page:
                time.sleep(sleep_sec)

    raise BidApiError(f"최종 요청 실패: {last_error}")
    # =========================================================
# 후처리 필터
# =========================================================
@dataclass
class PostFilter:
    exact_bid_no: Optional[str] = None
    exact_agency_name: Optional[str] = None
    title_contains: Optional[str] = None
    participant_count: Optional[int] = None
    winner_name: Optional[str] = None


def filter_items(
    items: Sequence[Dict[str, Any]],
    inqry_div: InqryDiv,
    bgn: Optional[datetime] = None,
    end: Optional[datetime] = None,
    bid_no: Optional[str] = None,
    post_filter: Optional[PostFilter] = None,
) -> List[Dict[str, Any]]:
    post_filter = post_filter or PostFilter()
    rows = list(items)

    # 조회구분 기반 방어적 재검증
    if inqry_div == InqryDiv.REG_DATE and bgn and end:
        end_bound = end.replace(hour=23, minute=59, second=59)
        tmp = []
        for row in rows:
            dtv = parse_dt(row.get("rgstDt"))
            if dtv and bgn <= dtv <= end_bound:
                tmp.append(row)
        rows = tmp

    elif inqry_div == InqryDiv.OPEN_DATE and bgn and end:
        end_bound = end.replace(hour=23, minute=59, second=59)
        tmp = []
        for row in rows:
            dtv = parse_dt(row.get("rlOpengDt"))
            if dtv and bgn <= dtv <= end_bound:
                tmp.append(row)
        rows = tmp

    elif inqry_div == InqryDiv.BID_NO and bid_no:
        rows = [row for row in rows if str(row.get("bidNtceNo", "")).strip() == str(bid_no).strip()]

    # 선택 필터
    if post_filter.exact_bid_no:
        rows = [row for row in rows if str(row.get("bidNtceNo", "")).strip() == str(post_filter.exact_bid_no).strip()]

    if post_filter.exact_agency_name:
        rows = [row for row in rows if (row.get("dminsttNm") or "") == post_filter.exact_agency_name]

    if post_filter.title_contains:
        keyword = post_filter.title_contains.strip()
        rows = [row for row in rows if keyword in (row.get("bidNtceNm") or "")]

    if post_filter.participant_count is not None:
        rows = [row for row in rows if safe_int(row.get("prtcptCnum")) == post_filter.participant_count]

    if post_filter.winner_name:
        rows = [row for row in rows if (row.get("bidwinnrNm") or "") == post_filter.winner_name]

    return rows


# =========================================================
# 데이터 변환
# =========================================================
def item_to_row(item: Dict[str, Any], btype: str) -> Tuple[Any, ...]:
    ntc_cd = safe_str(item.get("ntcelnsttCd") or item.get("dminsttCd"), 35) or ""
    ntc_nm = safe_str(item.get("ntcelnsttNm") or item.get("dminsttNm"), 50)

    openg_dt = (
        parse_dt(item.get("rlOpengDt"))
        or parse_dt(item.get("opengDt"))
        or parse_dt(item.get("fnlSucsfDate"))
    )

    rgst_dt = parse_dt(item.get("rgstDt"))

    return (
        safe_str(item.get("bidNtceNo"), 35),
        safe_str(item.get("bidNtceNm"), 100),
        openg_dt,
        rgst_dt,
        ntc_cd,
        ntc_nm,
        safe_str(item.get("dminsttCd"), 35) or "",
        safe_str(item.get("dminsttNm"), 50),
        safe_int(item.get("prtcptCnum")),
        safe_str(item.get("bidwinnrBizno"), 35),
        safe_str(item.get("bidwinnrNm"), 50),
        safe_str(item.get("bidwinnrCeoNm"), 50),
        safe_int(item.get("sucsfbidAmt")) or 0,
        safe_float(item.get("sucsfbidRate")) or 0.0,
        safe_int(item.get("bssamt")) or 0,
        safe_int(item.get("plnprc")) or 0,
        safe_str(item.get("bidwinrSlctnAplBssCntnts"), 50),
        safe_str(item.get("exctvNm"), 50) or "",
        safe_int(item.get("indstrytyCd")),
        safe_str(item.get("mainCnsttyNm"), 50) or btype,
        safe_str(item.get("indstrytyNm"), 50),
    )



INSERT_SQL = """
INSERT INTO final_insert
  (bidNtceNo, bidNtceNm, opengDt, rgstDt,
   ntcelnsttCd, ntcelnsttNm,
   dminsttCd, dminsttNm,
   prtcptCnum,
   bidwinnrBizno, bidwinnrNm, bidwinnrCeoNm,
   sucsfbidAmt, sucsfbidRate,
   bssamt, plnprc,
   bidwinrSlctnAplBssCntnts, exctvNm,
   indstrytyCd, mainCnsttyNm, indstrytyNm)
VALUES (%s,%s,%s,%s, %s,%s, %s,%s, %s, %s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s,%s)
ON DUPLICATE KEY UPDATE
  bidNtceNm=VALUES(bidNtceNm),
  opengDt=VALUES(opengDt),
  rgstDt=VALUES(rgstDt),
  ntcelnsttCd=VALUES(ntcelnsttCd),
  ntcelnsttNm=VALUES(ntcelnsttNm),
  dminsttCd=VALUES(dminsttCd),
  dminsttNm=VALUES(dminsttNm),
  prtcptCnum=VALUES(prtcptCnum),
  bidwinnrBizno=VALUES(bidwinnrBizno),
  bidwinnrNm=VALUES(bidwinnrNm),
  bidwinnrCeoNm=VALUES(bidwinnrCeoNm),
  sucsfbidAmt=VALUES(sucsfbidAmt),
  sucsfbidRate=VALUES(sucsfbidRate),
  bssamt=VALUES(bssamt),
  plnprc=VALUES(plnprc),
  bidwinrSlctnAplBssCntnts=VALUES(bidwinrSlctnAplBssCntnts),
  exctvNm=VALUES(exctvNm),
  indstrytyCd=VALUES(indstrytyCd),
  mainCnsttyNm=VALUES(mainCnsttyNm),
  indstrytyNm=VALUES(indstrytyNm)
"""



def rows_from_items(items: Sequence[Dict[str, Any]], btype: str) -> Tuple[List[Tuple[Any, ...]], int]:
    rows: List[Tuple[Any, ...]] = []
    bad_rows = 0

    for it in items:
        try:
            row = item_to_row(it, btype)
            if row[0] and (row[2] or row[3]):
                rows.append(row)
            else:
                bad_rows += 1

        except Exception:
            bad_rows += 1

    return rows, bad_rows


def dedupe_rows(rows: Sequence[Tuple[Any, ...]]) -> Tuple[List[Tuple[Any, ...]], int]:
    """
    bidNtceNo 기준으로 로컬 중복 제거
    같은 bidNtceNo가 여러 번 나오면 rgstDt가 가장 최신인 row 유지
    row[0] = bidNtceNo
    row[3] = rgstDt
    """
    from datetime import datetime

    latest: Dict[str, Tuple[Any, ...]] = {}
    dup_count = 0

    def to_dt(v: Any):
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v

        s = str(v).strip()
        if not s:
            return None

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y-%m-%d",
            "%Y%m%d",
        ):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        return None

    for row in rows:
        bid_no = str(row[0]).strip() if row and row[0] else ""
        if not bid_no:
            continue

        if bid_no in latest:
            dup_count += 1

            old_row = latest[bid_no]
            old_dt = to_dt(old_row[3] if len(old_row) > 3 else None)
            new_dt = to_dt(row[3] if len(row) > 3 else None)

            # 새 row의 rgstDt가 더 최신이면 교체
            if new_dt and old_dt:
                if new_dt > old_dt:
                    latest[bid_no] = row
            elif new_dt and not old_dt:
                latest[bid_no] = row
            # old_dt만 있거나 둘 다 없으면 기존 유지
        else:
            latest[bid_no] = row

    return list(latest.values()), dup_count



# =========================================================
# 페이지 수집
# =========================================================
@dataclass
class FetchResult:
    items: List[Dict[str, Any]]
    complete: bool
    total_expected: int
    last_page: int
    warnings: List[str]


def fetch_all(
    endpoint: str,
    inqry_div: InqryDiv,
    logger: logging.Logger,
    bgn: Optional[datetime] = None,
    end: Optional[datetime] = None,
    bid_no: Optional[str] = None,
    rows_per_page: int = DEFAULT_ROWS_PER_PAGE,
    retry_per_page: int = DEFAULT_RETRY_PER_PAGE,
    sleep_sec: float = DEFAULT_SLEEP_SEC,
) -> FetchResult:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "bidsync/2026.07",
        "Accept": "application/json",
        "Connection": "close",
    })

    results: List[Dict[str, Any]] = []
    page = 1
    total_expected = 0
    complete = True
    warnings: List[str] = []

    while True:
        try:
            url = build_url(
                endpoint=endpoint,
                page_no=page,
                rows_per_page=rows_per_page,
                inqry_div=inqry_div,
                bgn=bgn,
                end=end,
                bid_no=bid_no,
            )

            data = request_json(
                session=session,
                url=url,
                logger=logger,
                retry_per_page=retry_per_page,
            )

            body = data["response"].get("body", {})
            total_expected = safe_int(body.get("totalCount"), default=len(results))
            items = normalize_items(body)

            if not items:
                break

            results.extend(items)

            if total_expected and page * rows_per_page >= total_expected:
                break

            page += 1
            time.sleep(sleep_sec)

        except Exception as e:
            complete = False
            warnings.append(str(e))
            logger.error("fetch page failed endpoint=%s page=%s err=%s", endpoint, page, e)
            break

    session.close()

    return FetchResult(
        items=results,
        complete=complete,
        total_expected=total_expected,
        last_page=page,
        warnings=warnings,
    )


# =========================================================
# DB 저장
# =========================================================
def get_connection():
    return pymysql.connect(**DB_CONFIG)


def upsert_rows(
    conn,
    rows: Sequence[Tuple[Any, ...]],
    logger: logging.Logger,
    db_retry: int = DEFAULT_DB_RETRY,
) -> int:
    last_error: Optional[Exception] = None

    for attempt in range(1, db_retry + 1):
        try:
            with conn.cursor() as cur:
                cur.executemany(INSERT_SQL, list(rows))
            conn.commit()
            return len(rows)
        except Exception as e:
            conn.rollback()
            last_error = e
            logger.warning("db upsert failed attempt=%s/%s err=%s", attempt, db_retry, e)
            if attempt < db_retry:
                time.sleep(1.5 * attempt)

    raise BidApiError(f"DB UPSERT 최종 실패: {last_error}")


# =========================================================
# 공통 실행기
# =========================================================
def run_sync(
    *,
    script_name: str,
    bid_types: Sequence[str],
    start_date: datetime,
    end_date: datetime,
    chunk_days: int,
    only_bid_no: Optional[str] = None,
    inqry_div: Optional[InqryDiv] = None,
    post_filter: Optional[PostFilter] = None,
    rows_per_page: int = DEFAULT_ROWS_PER_PAGE,
    retry_per_page: int = DEFAULT_RETRY_PER_PAGE,
    sleep_sec: float = DEFAULT_SLEEP_SEC,
    max_call_days: int = 30,
) -> int:
    logger = build_logger(script_name)

    actual_inqry_div = InqryDiv.BID_NO if only_bid_no else (inqry_div or InqryDiv.REG_DATE)

    range_days = (end_date - start_date).days + 1
    if actual_inqry_div != InqryDiv.BID_NO and range_days > max_call_days:
        start_date = end_date - timedelta(days=max_call_days - 1)

    failed_windows = set()
    total_api_items = 0
    total_upserted_rows = 0
    total_bad_rows = 0
    total_deduped_rows = 0

    logger.info("===== %s =====", script_name)
    logger.info("period       : %s ~ %s", start_date.date(), end_date.date())
    logger.info("chunk_days   : %s", chunk_days)
    logger.info("bid_types    : %s", ",".join(bid_types))
    logger.info("only_bid_no  : %s", only_bid_no)
    logger.info("inqry_div    : %s (%s)", int(actual_inqry_div), INQRY_DIV_LABELS[actual_inqry_div])

    conn = get_connection()

    try:
        if actual_inqry_div == InqryDiv.BID_NO:
            windows = [(None, None)]
        else:
            windows = iter_windows(start_date, end_date, min(chunk_days, max_call_days))

        for win in windows:
            if actual_inqry_div == InqryDiv.BID_NO:
                bgn = end = None
                logger.info("============== BID_NO MODE ==============")
            else:
                bgn, end = win
                logger.info("============== WINDOW %s ~ %s ==============", bgn.date(), end.date())

            for btype in bid_types:
                endpoint = ENDPOINTS[btype]

                info = fetch_all(
                    endpoint=endpoint,
                    inqry_div=actual_inqry_div,
                    logger=logger,
                    bgn=bgn,
                    end=end,
                    bid_no=only_bid_no,
                    rows_per_page=rows_per_page,
                    retry_per_page=retry_per_page,
                    sleep_sec=sleep_sec,
                )

                items = filter_items(
                    items=info.items,
                    inqry_div=actual_inqry_div,
                    bgn=bgn,
                    end=end,
                    bid_no=only_bid_no,
                    post_filter=post_filter,
                )

                api_cnt = len(items)
                total_api_items += api_cnt

                rows, bad_rows = rows_from_items(items, btype)
                total_bad_rows += bad_rows

                rows, dup_count = dedupe_rows(rows)
                total_deduped_rows += dup_count

                if not rows:
                    logger.info("[%s] API=%s UPSERT=0 bad_rows=%s deduped=%s complete=%s",
                                btype, api_cnt, bad_rows, dup_count, info.complete)
                    if not info.complete:
                        failed_windows.add((btype, str(bgn.date()) if bgn else "-", str(end.date()) if end else "-"))
                    continue

                try:
                    inserted = upsert_rows(conn, rows, logger)
                    total_upserted_rows += inserted
                    logger.info("[%s] API=%s UPSERT=%s bad_rows=%s deduped=%s complete=%s",
                                btype, api_cnt, inserted, bad_rows, dup_count, info.complete)
                except Exception as e:
                    logger.error("[%s] DB ERROR: %s", btype, e)
                    failed_windows.add((btype, str(bgn.date()) if bgn else "-", str(end.date()) if end else "-"))

                if not info.complete:
                    failed_windows.add((btype, str(bgn.date()) if bgn else "-", str(end.date()) if end else "-"))

                time.sleep(sleep_sec)

    finally:
        conn.close()

    logger.info("============== SUMMARY ==============")
    logger.info("total_api_items     = %s", total_api_items)
    logger.info("total_upserted_rows = %s", total_upserted_rows)
    logger.info("total_bad_rows      = %s", total_bad_rows)
    logger.info("total_deduped_rows  = %s", total_deduped_rows)
    logger.info("failed_windows      = %s", len(failed_windows))

    if failed_windows:
        logger.warning("rerun recommended for:")
        for fw in sorted(failed_windows):
            logger.warning("  - %s / %s ~ %s", fw[0], fw[1], fw[2])
        return 1

    logger.info("all windows completed without fetch/db error")
    return 0


# =========================================================
# 단독 실행: 과거 전체 재수집용
# =========================================================
START_DATE = datetime(2024, 5, 24)
END_DATE = datetime.today()
CHUNK_DAYS = 7


def main():
    rc = run_sync(
        script_name="collect_award_db_fixed",
        bid_types=("공사", "물품"),
        start_date=START_DATE,
        end_date=END_DATE,
        chunk_days=CHUNK_DAYS,
        only_bid_no=None,
        inqry_div=InqryDiv.REG_DATE,
        post_filter=None,
        rows_per_page=100,
        retry_per_page=5,
        sleep_sec=1.0,
        max_call_days=30,
    )
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
