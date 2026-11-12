# -*- coding: utf-8 -*-
"""
Seri N-Data - main_send.py
입찰공고 수집 → 필터링 → 엑셀 저장 → 리포트 생성 → 알림톡 전송(TB_0485)
"""

import argparse
import sys
import csv
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path

import pandas as pd

from seri_n_data.utils import log
from seri_n_data.lockutil import acquire_lock
from seri_n_data.fetcher import fetch_ind, filter_rows
from seri_n_data.excel_export import save_excel
from seri_n_data.reporter import generate_all_reports
from seri_n_data.config import TARGET_INDS
from alligo import Alligo

# --------------------------------------------------------------------
# 경로 설정
# --------------------------------------------------------------------
OUTDIR = Path("/mnt/vol1/n_data")
OUTDIR.mkdir(parents=True, exist_ok=True)

# 공고 중복 발송 방지용 기록 파일
SENT_HISTORY_CSV = OUTDIR / "sent_history.csv"


# ============================================================
# 파라미터 처리
# ============================================================

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=1, help="조회 시간 범위(시간 단위)")
    ap.add_argument("--no-send", action="store_true", help="알림톡 전송 생략")
    return ap.parse_args()


# ============================================================
# 공고 수집
# ============================================================

def collect_data(bgn_dt: str, end_dt: str) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    for ind in TARGET_INDS:
        log(f"[FETCH] ind={ind} from {bgn_dt} to {end_dt}")
        rows = fetch_ind(ind, bgn_dt, end_dt)
        all_rows.extend(rows)
    return all_rows


# ============================================================
# 금액 / 공종 / 지역 규칙 헬퍼
# ============================================================

def extract_code_from_name(name: str) -> str:
    """예: '기계설비공사업(6202)' → '6202' """
    if not name:
        return ""
    m = re.search(r"\((\d{3,4})\)", name)
    if m:
        return m.group(1)
    return ""


def get_all_industry_codes(raw: Dict[str, Any]) -> set:
    """
    원문(raw)에서 주업종/부업종/indstrytyCd 등을 포함한 모든 업종코드 추출
    """
    codes = set()

    for key in [
        "mainCnsttyNm",
        "subsiCnsttyNm1",
        "subsiCnsttyNm2",
        "subsiCnsttyNm3",
    ]:
        c = extract_code_from_name(str(raw.get(key, "")))
        if c:
            codes.add(c)

    # indstrytyCd 가 4자리 코드 그대로 오는 경우도 있음
    base_code = str(raw.get("indstrytyCd", "")).strip()
    if base_code.isdigit() and len(base_code) in {3, 4}:
        codes.add(base_code)

    return codes


# 발송 대상 업종:
#   0037(전기), 0038(소방기계), 0039(소방전기), 0040(전문소방), 6202(기계설비)
TARGET_CODES = {"0037", "0038", "0039", "0040", "6202"}


def _parse_amount(val) -> int:
    """추정금액(문자열/숫자)을 정수로 변환. 변환 실패 시 0."""
    if val is None:
        return 0
    s = str(val)
    s = s.replace(",", "").strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return 0
    try:
        return int(digits)
    except ValueError:
        return 0


def _get_region_strings(row) -> Dict[str, str]:
    """
    지역 관련 필드를 모두 모아서 dict로 반환.
    - 참가가능/제한지역
    - 공동도급지역
    - 공사위치/수요지역
    """
    raw = row.get("원문") or {}

    prtcpt_region = (
        str(raw.get("bidPrtcptLmtRgnNm") or "")
        or str(raw.get("prtcptLmtRgnNm") or "")
    ).strip()

    joint_region = (
        str(raw.get("jntcontrctDutyRgnNm1") or "")
        or str(raw.get("jntcontrctDutyRgnNm2") or "")
        or str(raw.get("jntcontrctDutyRgnNm3") or "")
    ).strip()

    etc_region = (
        str(row.get("공동도급지역") or "")
        or str(row.get("수요지역") or "")
        or str(raw.get("cnstrtsiteRgnNm") or "")
    ).strip()

    return {
        "prtcpt": prtcpt_region,
        "joint": joint_region,
        "etc": etc_region,
    }


def _get_receivers_by_rule(row) -> list:
    """
    추정금액 / 공종 / 지역 기준으로 수신자 리스트 결정.

    규칙:
      1) 업종: {0037, 0038, 0039, 0040, 6202} 에 해당하는 경우만 발송

      2) 추정금액 >= 11억  → 전국 공고로 간주, 전체 수신자 발송

      3) 추정금액 < 11억  → 지역 분기
         - 지역: 대구, 경북/경상북도 -> REDACTED_PRIVATE_VALUE
         - 지역: 세종              -> REDACTED_PRIVATE_VALUE, REDACTED_PRIVATE_VALUE
         - 지역: 충북/충청북도     -> REDACTED_PRIVATE_VALUE, REDACTED_PRIVATE_VALUE

      ※ 지역 판정 순서 (11억 미만일 때):
         - 1순위: 참가가능/제한지역 (bidPrtcptLmtRgnNm / prtcptLmtRgnNm)
         - 2순위: 공동도급지역(jntcontrctDutyRgnNm1~3)
         - 3순위: 공사위치/수요지역(cnstrtsiteRgnNm, '수요지역', '공동도급지역')
    """
    raw = row.get("원문") or {}

    # ---- 업종 판별 ----
    industry_codes = get_all_industry_codes(raw)
    if not (industry_codes & TARGET_CODES):
        return []  # 공종 미대상

    # ---- 추정금액 ----
    amt_raw = raw.get("presmptPrce") or raw.get("bdgtAmt")
    amount = _parse_amount(amt_raw)

    # ---- 지역 문자열들 ----
    rgn = _get_region_strings(row)
    prtcpt_region = rgn["prtcpt"]
    joint_region = rgn["joint"]
    etc_region = rgn["etc"]

    THRESHOLD = 1_100_000_000  # 11억

    # 1) 11억 이상: 전국 공고 → 전체 수신
    if amount >= THRESHOLD:
        return [
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
        ]

    # 2) 11억 미만: 참가가능지역 → 공동도급지역 → 기타 순서로 사용
    region_for_rule = prtcpt_region or joint_region or etc_region
    r = region_for_rule

    # 대구 / 경북
    if ("대구" in r) or ("경북" in r) or ("경상북도" in r):
        return ["REDACTED_PRIVATE_VALUE"]

    # 세종
    if "세종" in r:
        return ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

    # 충북 / 충청북도
    if ("충북" in r) or ("충청북도" in r):
        return ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

    # 그 외 지역은 현재 발송 대상 아님
    return []


def _extract_joint_rate(raw: Dict[str, Any], amount: int) -> str:
    """
    도급비율 추출.
    - 우선 rgnDutyJntcontrctRt 사용
    - 추정금액 11억 이상인데 위 값이 비어 있고,
      cnsttyAccotShreRateList 가 있으면 그 값을 그대로 사용
      (예: [기계설비ㆍ가스공사업^100])
    """
    jr = str(raw.get("rgnDutyJntcontrctRt") or "").strip()
    if jr:
        return jr

    if amount >= 1_100_000_000:
        s = str(raw.get("cnsttyAccotShreRateList") or "").strip()
        if s:
            return s

    return ""


# ============================================================
# 알림톡 메시지(TB_0485)
# ============================================================

ALIMTALK_TEMPLATE_TB0485 = (
    "[세리공영]\n\n"
    "공고명 : #{bidNtceNm}\n"
    "입찰마감일시 : #{bidClseDt}\n"
    "공동도급지역 : #{jntcontrctDutyRgnNm1}\n"
    "공동도급비율 : #{rgnDutyJntcontrctRt}\n"
    "추정금액 : #{presmptPrce}\n"
    "공고번호 : #{bidNtceNo} - #{bidNtceOrd}"
)


def build_tb0485_message(row) -> str:
    raw = row.get("원문") or {}

    # ---- 지역: 메시지에 넣을 때도 참가가능지역 우선 ----
    rgn = _get_region_strings(row)
    joint_region_for_msg = (
        rgn["joint"]        # 공동도급지역이 있으면 우선
        or rgn["prtcpt"]    # 없으면 참가가능/제한지역
        or rgn["etc"]       # 그래도 없으면 기타 지역
    )

    amt_raw = raw.get("presmptPrce") or raw.get("bdgtAmt")
    amount = _parse_amount(amt_raw)

    # 도급비율
    joint_rate = _extract_joint_rate(raw, amount)

    v = {
        "bidNtceNm": str(raw.get("bidNtceNm") or row.get("공고명") or ""),
        "bidClseDt": str(raw.get("bidClseDt") or row.get("입찰마감일시") or ""),
        "jntcontrctDutyRgnNm1": joint_region_for_msg,
        "rgnDutyJntcontrctRt": joint_rate,
        "presmptPrce": str(raw.get("presmptPrce") or ""),
        "bidNtceNo": str(raw.get("bidNtceNo") or row.get("공고번호") or ""),
        "bidNtceOrd": str(raw.get("bidNtceOrd") or row.get("차수") or ""),
    }

    msg = ALIMTALK_TEMPLATE_TB0485
    for k, val in v.items():
        msg = msg.replace(f"#{{{k}}}", val)

    return msg


# ============================================================
# 발송 이력 CSV
# ============================================================

def load_sent_history() -> set:
    """
    이미 알림톡을 보낸 공고번호-차수 목록을 CSV에서 읽어서 set으로 반환.
    형식: bid_no-bid_ord (예: 'R25BK01183646-000')
    """
    sent = set()
    try:
        if SENT_HISTORY_CSV.exists():
            with SENT_HISTORY_CSV.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = f"{row.get('bid_no', '')}-{row.get('bid_ord', '')}"
                    if key != "-":
                        sent.add(key)
    except Exception as e:
        log(f"[WARN] SENT_HISTORY_CSV 읽기 실패: {e}", tag="SEND")

    return sent


def append_sent_history(bid_no: str, bid_ord: str) -> None:
    """
    새로 발송한 공고번호-차수를 CSV에 한 줄 추가 저장.
    """
    try:
        file_exists = SENT_HISTORY_CSV.exists()
        with SENT_HISTORY_CSV.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["bid_no", "bid_ord", "sent_at"])
            writer.writerow([bid_no, bid_ord, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    except Exception as e:
        log(f"[WARN] SENT_HISTORY_CSV 쓰기 실패: {e}", tag="SEND")


# ============================================================
# 알림톡 발송 (TB_0485 + 지역/금액/공종 규칙 + 중복발송 방지)
# ============================================================

def send_kakao_tb0485(df_send: pd.DataFrame) -> None:
    if df_send is None or len(df_send) == 0:
        log("[SEND] 발송 대상 없음")
        return

    log(f"[DEBUG] DF columns: {df_send.columns.tolist()}")
    if len(df_send) > 0:
        log(f"[DEBUG] FIRST ROW: {df_send.iloc[0].to_dict()}")

    tpl_code = "TB_0485"
    sender = "REDACTED_PRIVATE_VALUE"  # 발신번호
    alligo = Alligo()

    # 이미 보낸 목록 로드
    sent_history = load_sent_history()
    log(f"[SEND] TB_0485 템플릿 사용, 대상={len(df_send)}건, 기존 발송 이력={len(sent_history)}건")

    for idx, row in df_send.iterrows():
        raw = row.get("원문") or {}

        bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "")
        bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "")
        bid_name = str(raw.get("bidNtceNm") or row.get("공고명") or "")

        key = f"{bid_no}-{bid_ord}"

        # 1) 공종/금액/지역 규칙 미해당 → 스킵
        receivers = _get_receivers_by_rule(row)
        if not receivers:
            log(f"[SEND][SKIP][RULE] {key} / {bid_name} : 수신자 없음(규칙 미해당)")
            continue

        # 2) 이미 발송된 공고 → 스킵
        if key in sent_history:
            log(f"[SEND][SKIP][HISTORY] {key} / {bid_name} : 이미 발송된 공고")
            continue

        # 3) 템플릿 메시지 생성
        msg = build_tb0485_message(row)

        log(f"[SEND] try {key} / {bid_name} -> {receivers}")
        ok = alligo.sendTalk(
            tpl_code=tpl_code,
            sender=sender,
            msgHead="[세리공영] 입찰 알림",
            message=msg,
            receiverList=receivers,
        )

        if ok:
            log(f"[SEND] SUCCESS {key}")
            # 실제 발송 성공 시에만 엑셀/리포트에 남길 수신번호 기록
            df_send.at[idx, "수신번호"] = ",".join(receivers)

            amt_raw = raw.get("presmptPrce") or raw.get("bdgtAmt")
            amount = _parse_amount(amt_raw)
            df_send.at[idx, "도급비율"] = _extract_joint_rate(raw, amount)

            append_sent_history(bid_no, bid_ord)
            sent_history.add(key)
        else:
            log(f"[SEND][FAIL] {key}")

    log("[SEND] TB_0485 전체 발송 완료")


# ------------------------------------------------------------
# (참고용) 예전 엑셀 기반 발송 훅 - 지금은 사용하지 않음
# ------------------------------------------------------------

def send_notifications_from_excel(xlsx_path: str) -> None:
    """
    (현재는 사용하지 않음)
    나중에 seri_n_data.sender.send_all 과 연동하고 싶을 때 참고용으로 남겨둔 훅.
    """
    try:
        df = pd.read_excel(xlsx_path)
    except Exception as e:
        log(f"[SEND][ERR] 엑셀 로드 실패: {e}")
        return

    log(f"[SEND] (deprecated) 엑셀 {xlsx_path}에서 {len(df)}건 로드됨 - 현재는 미사용")


# ============================================================
# 메인 실행 로직
#   - "전송 → 수신번호/도급비율 컬럼 반영 → 엑셀 저장" 순서
# ============================================================

def main():
    args = parse_args()

    # 중복 실행 방지 락
    lock_fd = acquire_lock()
    if lock_fd is None:
        return

    start_ts = datetime.now()
    log("[MAIN] === main_send.py START ===")

    try:
        # 조회 기간 계산
        end_dt = start_ts.strftime("%Y%m%d%H%M")
        bgn_dt = (start_ts - timedelta(hours=args.hours)).strftime("%Y%m%d%H%M")
        log(f"[MAIN] 기간 {bgn_dt} ~ {end_dt}")

        # 공고 수집
        raw_rows = collect_data(bgn_dt, end_dt)
        log(f"[FETCH] total rows = {len(raw_rows)}")

        # 필터링
        rows = filter_rows(raw_rows)
        log(f"[FILTER] filtered rows = {len(rows)}")

        # DataFrame 변환 후 알림톡 발송
        df_send = pd.DataFrame(rows)
        if not args.no_send:
            try:
                send_kakao_tb0485(df_send)
            except Exception as e:
                log(f"[SEND][ERR] 전송단계 오류: {e}")
        else:
            log("[MAIN] --no-send 옵션으로 알림톡 전송 생략")

        # 수신번호/도급비율 반영된 상태로 dict 리스트 변환
        rows_with_send_info = df_send.to_dict(orient="records")

        # 엑셀 저장
        try:
            xlsx_path = save_excel(rows_with_send_info)
        except Exception as e:
            log(f"[ERR] save_excel failed: {e}")
            return

        if not xlsx_path:
            log("[MAIN] 저장할 데이터 없음. 종료.")
            return

        log(f"[MAIN] 엑셀 저장 완료: {xlsx_path}")

        # 리포트 생성 (HTML + XLSX)
        try:
            generate_all_reports(
                excel_path=xlsx_path,
                bgn_dt_str=bgn_dt,
                end_dt_str=end_dt,
            )
        except Exception as e:
            log(f"[REPORT][ERR] report generation failed: {e}")

    except Exception as e:
        log(f"[FATAL] main crashed: {e}")
        sys.exit(1)
    finally:
        end_ts = datetime.now()
        log(f"[MAIN] === main_send.py END (took {end_ts - start_ts}) ===")
        try:
            import os
            if lock_fd is not None:
                os.close(lock_fd)
        except Exception:
            pass


# ============================================================
# 엔트리포인트
# ============================================================

if __name__ == "__main__":
    main()
