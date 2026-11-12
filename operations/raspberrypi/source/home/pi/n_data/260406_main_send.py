import os

# ============================================================

# 운영용 TB0485 수신자 규칙 – 최종 한방 블록

# ------------------------------------------------------------

# [전제] PresmptPrce(추정가격) 기준 전국/지역 1차 분리(최우선)

#   - 추정가격 >= 10억  => 대표지역을 "전국"으로 간주

#   - 추정가격 <  10억  => 대표지역은 참고값(흔들릴 수 있음)

#

# [수신자 규칙]

#   (A) 공종 0038/0039/0040/6202:

#       - 전국(>=10억): REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

#       - 지역(<10억): 대표지역이 (세종/충북/대구/경북)일 때만 지역룰 적용,

#                    그 외 지역은 폭주 방지로 최소 수신자(REDACTED_PRIVATE_VALUE)만.

#

#   (B) 공종 0037:

#       - 전국(>=10억): REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

#       - 지역(<10억): 최소 수신자(REDACTED_PRIVATE_VALUE)만.

#

# [공종코드 필터]

#   - 문서에서 4자리 숫자가 과다 추출되는 문제 방지:

#     0037/0038/0039/0040/6202만 인정

# ============================================================
def _get_force_suffix():

    try:

        _ff = (os.getenv("FORCE_FROM") or "").strip()

        _ft = (os.getenv("FORCE_TO") or "").strip()

        if _ff or _ft:

            return f"_FORCE_{_ff or 'NA'}_{_ft or 'NA'}"

    except Exception:

        pass

    return ""








def _tb0485_override_receivers_FINAL(row, receivers, log_fn=None):

    import re



    def _log(msg):

        try:

            if callable(log_fn):

                log_fn(msg)

        except Exception:

            pass



    r = row if isinstance(row, dict) else {"__row__": str(row)}



    # 1) 대표지역 추출/정규화

    rep = ""

    for k in ("대표지역", "rep_region", "지역", "지역명", "prtcptLmtRgnNm"):

        v = r.get(k)

        if v:

            rep = str(v).strip()

            break



    rep = rep.replace("특별자치시", "").replace("특별자치도", "").replace("광역시", "").replace(" 특별시", "").strip()

    if rep in ("충청북도", "충북"):

        rep = "충북"

    elif rep in ("세종", "세종시", "세종특별자치시"):

        rep = "세종"

    elif rep in ("대구", "대구시", "대구광역시"):

        rep = "대구"

    elif rep in ("경상북도", "경북"):

        rep = "경북"

    elif "전국" in rep:

        rep = "전국"



    # 2) PresmptPrce(추정가격) -> 10억 기준 전국/지역

    pres = r.get("PresmptPrce")

    if pres in (None, ""):

        for k in ("추정가격", "presmptprce", "PRESMPTPRCE", "presmptPrce"):

            if r.get(k) not in (None, ""):

                pres = r.get(k)

                break



    amt = None

    try:

        if isinstance(pres, (int, float)):

            amt = int(pres)

        else:

            nums = re.findall(r"\d+", str(pres))

            if nums:

                amt = int("".join(nums))

    except Exception:

        amt = None



    is_nation = False

    if amt is not None and amt >= 1_000_000_000:

        if rep != "전국":

            _log(f"[OVERRIDE][AMT] PresmptPrce={amt} >= 10억 -> rep {rep} => 전국")

        rep = "전국"

        is_nation = True



    # 3) 공종코드 추출 + 필터(오염 방지)

    blob = ""

    try:

        for k in ("공종", "공종코드", "공종코드1", "업종", "업종코드", "indstrytyCd", "indstrytyNm", "공종명", "업종명"):

            v = r.get(k)

            if v:

                blob += " " + str(v)

    except Exception:

        pass

    if not blob.strip():

        blob = str(r)



    raw_codes = set(re.findall(r"(?<!\d)(\d{4})(?!\d)", blob))

    allowed_codes = {"0037", "0038", "0039", "0040", "6202"}

    codes = set(c for c in raw_codes if c in allowed_codes)



    # 4) 룰

    groupA = {"0038", "0039", "0040", "6202"}

    ruleA = {

        "전국": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

        "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

        "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

        "대구": ["REDACTED_PRIVATE_VALUE"],

        "경북": ["REDACTED_PRIVATE_VALUE"],

    }



    # 0037 예외

    if "0037" in codes:

        if is_nation:

            out = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

            _log(f"[OVERRIDE][FINAL] code=0037 nation(>=10억) rep={rep} -> {out}")

            return out

        out = ["REDACTED_PRIVATE_VALUE"]

        _log(f"[OVERRIDE][FINAL] code=0037 local(<10억) rep={rep} -> MIN={out}")

        return out



    # A그룹

    hitA = sorted(codes.intersection(groupA))

    if hitA:

        if is_nation:

            out = ruleA["전국"]

            _log(f"[OVERRIDE][FINAL] codes={hitA} nation(>=10억) rep={rep} -> {out}")

            return out



        if rep in ruleA and rep != "전국":

            out = ruleA[rep]

            _log(f"[OVERRIDE][FINAL] codes={hitA} local(<10억) rep={rep} -> {out}")

            return out



        out = ["REDACTED_PRIVATE_VALUE"]

        _log(f"[OVERRIDE][FINAL] codes={hitA} local(<10억) rep={rep} not in local-rule -> NORECV={out}")

        return out



    _log(f"[OVERRIDE][FINAL] no match (rep={rep}, amt={amt}, codes={sorted(codes)}) -> keep={receivers}")

    return receivers

def _dbg_get_key_from_row(row: dict) -> str:

    """row에서 key 생성/추출 (공고번호/차수 우선)"""

    try:

        if isinstance(row, dict):

            k = (row.get('_key') or row.get('key') or row.get('send_key') or '').strip()

            if k:

                return k

            bid_no = (row.get('공고번호') or row.get('bidNtceNo') or row.get('bid_no') or '').strip()

            bid_ord = (row.get('차수') or row.get('bidNtceOrd') or row.get('bid_ord') or '').strip()

            if bid_no and bid_ord:

                return f"{bid_no}-{bid_ord}"

            if bid_no:

                return bid_no

    except Exception:

        pass

    return ''



def _dbg_bid_match(key: str, row: dict) -> bool:

    """DBG_BID_LIST 매칭: (1) 공고번호 동일 (2) key startswith '공고번호-' (3) key contains 공고번호"""

    try:

        bids = globals().get('DBG_BID_LIST') or []

        if not bids:

            return False



        key = (key or '').strip()

        bid_no = ''

        bid_ord = ''

        if isinstance(row, dict):

            bid_no = (row.get('공고번호') or row.get('bidNtceNo') or row.get('bid_no') or '').strip()

            bid_ord = (row.get('차수') or row.get('bidNtceOrd') or row.get('bid_ord') or '').strip()



        for b in bids:

            b = (b or '').strip()

            if not b:

                continue  # empty bid filter
            # (A) 사용자가 공고번호만 넣는 케이스 (R26BK...)

            if bid_no and bid_no == b:

                return True

            if key:

                if key == b:

                    return True

                if key.startswith(b + "-"):

                    return True

                if b in key:

                    return True



            # (B) 사용자가 공고번호-차수로 넣는 케이스 (R26BK...-000)

            if bid_no and bid_ord:

                full = f"{bid_no}-{bid_ord}"

                if full == b:

                    return True



        return False

    except Exception:

        return False



# ----------------------------------------------

# wrapper(run_main_send.sh)에서 락을 이미 잡은 경우 내부 락은 생략

# ----------------------------------------------

import os as _os

MAIN_SEND_LOCKED = (_os.environ.get("MAIN_SEND_LOCKED", "").strip() == "1")

LOCK_FILE_PATH = os.environ.get("MAIN_SEND_LOCK_FILE", os.environ.get("LOCK_FILE", "/tmp/main_send.lock"))
# __ALARM_FILTER_V3__

def _should_block_by_method_text(method_text: str) -> bool:



    if not method_text:

        return False



    t = str(method_text).replace(" ", "")



    if (

        "50억원미만30억원이상" in t

        or "30억원이상" in t

        or "10억원이상" in t

        or "10억이상" in t

    ):

        return False



    if "소액수의" in t:

        return False



    if "지방자치단체입찰시낙찰자결정기준" in t and "10억원미만" in t:

        return True



    return False

# __ALARM_FILTER_V3__ END





def _read_lock_holder(path):
    try:
        txt = open(path, 'r', encoding='utf-8', errors='ignore').read()
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        return lines[-1] if lines else ''
    except Exception:
        return ''

def _lock_stat(path: str) -> str:

    try:

        st = __import__("os").stat(path)

        return f"size={st.st_size} mtime={int(st.st_mtime)}"

    except Exception:

        return "stat=NA"


# -*- coding: utf-8 -*-



"""

main_send.py — 2025 통합 리팩토링 + 조달청 공고수집 collect_bids_range 버전



[실운영 경로 매칭(확정)]

- 라즈베리: /mnt/vol1/bid/n_data  (또는 /mnt/vol1/bid/bid/n_data 환경도 자동 대응)

- PC:       Z:\VOL1\bid\bid\n_data



기능 요약:

- 조달청 입찰공고 API(공사)에서 0037/0038/0039/0040/6202 업종 기준 공고 조회

- nara_public_collect.collect_bids_range 사용

- last_run.txt 기반 "연속 구간" 조회 + GRACE_MINUTES(버퍼)로 시간 경계 누락 방지

- "--hours N" 을 명시하면 last_run.txt를 무시하고 최근 N시간 강제 조회

- bidNtceNo/bidNtceOrd 기준 중복 제거 + 발송 이력 CSV로 재발송 방지

- region_filter.classify_region / decide_receivers 로 대표지역·수신자 자동 결정

- raw/split/report 엑셀 + HTML 리포트 저장 및 backup/로테이트

- 알림톡 성공/실패 로그(data_gd/kakao_logs) 자동 저장 + 실패 시 3회 재시도

- (중요) fcntl 없는 Windows에서도 돌아가도록 락 처리 분기

"""




import sys

import csv

import shutil

import traceback

import time as _time
import argparse

from datetime import datetime, timedelta

from pathlib import Path



import pandas as pd



from kakao_send_tb0485 import send_for_item as kakao_send_for_item
from seri_n_data.outbox_shadow import make_send_key, db_outbox_shadow

try:
    from nara_public_collect import (
        collect_bids_range,
        enrich_cnstwk_sucs_method,
    )
except Exception:
    from nara_public_collect import collect_bids_range
    enrich_cnstwk_sucs_method = None
from seri_n_data.region_filter import classify_region, decide_receivers


# TEST_SAFETY_GUARD_NAS_BASE (module-level, no indent risk)

import os as _os

_cwd = _os.getcwd().replace("\\", "/")

_env_base = (_os.environ.get("N_DATA_BASE") or "").strip()



if "/home/pi/n_data_test" in _cwd:

    # 1) env가 없으면 테스트 NAS_BASE로 강제

    if _env_base == "":

        _os.environ["N_DATA_BASE"] = "/mnt/vol1/bid/n_data_test"

    # 2) env가 실환경을 가리키면 즉시 중단

    elif _env_base == "/mnt/vol1/bid/n_data":

        print("[FATAL] TEST MODE but N_DATA_BASE points to PROD:", _env_base)

        raise SystemExit(2)

try:
    from seri_n_data.region_filter import infer_region_when_etc
except Exception:
    infer_region_when_etc = None





# ---------------------------------------------

# 파일락(리눅스/윈도우 분기)

# ---------------------------------------------



try:

    import fcntl  # Linux

except Exception:

    fcntl = None



try:

    import msvcrt  # Windows

except Exception:

    msvcrt = None





# ---------------------------------------------

# 경로/파일 설정 (실운영 기준)

# ---------------------------------------------

BASE_DIR = Path("/home/pi/n_data")  # 스크립트 위치(로컬)



def _resolve_nas_base() -> Path:

    """

    우선순위:

    1) 환경변수 N_DATA_BASE

    2) /mnt/vol1/bid/n_data

    3) /mnt/vol1/bid/bid/n_data

    """

    env = os.environ.get("N_DATA_BASE", "").strip()

    if env:

        return Path(env)



    candidates = [

        Path("/mnt/vol1/bid/n_data"),

        Path("/mnt/vol1/bid/bid/n_data"),

    ]

    for p in candidates:

        if p.exists():

            return p

    return candidates[0]



NAS_BASE = _resolve_nas_base()  # ✅ 데이터/이력/락 모두 여기만 사용



STATE_FILE    = NAS_BASE / "last_run.txt"

LAST_RUN_FILE = STATE_FILE



LOCK_FILE     = NAS_BASE / "main_send.lock"

API_KEY_FILE  = NAS_BASE / "bid_api_key.txt"



RAW_DIR       = NAS_BASE / "raw"

SPLIT_DIR     = NAS_BASE / "split"

REPORT_DIR    = NAS_BASE / "report"



# -------------------------------------------------

# FORCE mode: 산출물 전용 디렉토리로 분리

#   - FORCE_FROM/TO가 설정되면 _get_force_suffix() != ""

#   - raw/split/report 경로를 /force 하위로 스위칭

# -------------------------------------------------

FORCE_BASE      = NAS_BASE / "force"

FORCE_RAW_DIR   = FORCE_BASE / "raw"

FORCE_SPLIT_DIR = FORCE_BASE / "split"

FORCE_REPORT_DIR= FORCE_BASE / "report"



if _get_force_suffix():

    RAW_DIR    = FORCE_RAW_DIR

    SPLIT_DIR  = FORCE_SPLIT_DIR

    REPORT_DIR = FORCE_REPORT_DIR

    try:

        log(f"[OVERRIDE] FORCE DIRS -> raw={RAW_DIR} split={SPLIT_DIR} report={REPORT_DIR}")

    except Exception:

        pass



LOG_DIR       = NAS_BASE / "logs"



HISTORY_FILE  = NAS_BASE / "split/history/send_history.csv"



DATA_GD_DIR   = NAS_BASE / "data_gd"

KAKAO_LOG_DIR = DATA_GD_DIR / "kakao_logs"



# 필요한 폴더 자동 생성

for d in (RAW_DIR, SPLIT_DIR, REPORT_DIR, LOG_DIR, HISTORY_FILE.parent, KAKAO_LOG_DIR):

    d.mkdir(parents=True, exist_ok=True)



RUN_LOG_FILE = LOG_DIR / "run_main_send.log"



# 업종코드 / 기간 / 버퍼

TARGET_INDS = ["0037", "0038", "0039", "0040", "6202"]

MAX_DAYS = 15

GRACE_MINUTES = 3

MIN_BUDGET = 30_000_000  # 3천만 이상만 수집





# ---------------------------------------------

# 유틸

# ---------------------------------------------
def apply_joint_contract_fields(rows):
    """
    rows(list[dict])에 아래 필드 반영:
      - 공동도급지역: jntcontrctDutyRgnNm1
      - 공동도급지역_추가: jntcontrctDutyRgnNm2
      - 공동도급비율: rgnDutyJntcontrctRt (숫자면 % 붙임)
    그리고 요청대로:
      - 대표지역 <- 공동도급지역 (있으면 덮어쓰기)
      - 공고업종명 <- 공동도급비율 (있으면 덮어쓰기)
    """
    def _norm_region(v):
        v = ("" if v is None else str(v)).strip()
        if not v or v.lower() in ("none", "null", "nan") or v == "해당없음":
            return ""
        return v

    def _norm_ratio(v):
        v = ("" if v is None else str(v)).strip()
        if not v or v.lower() in ("none", "null", "nan"):
            return ""
        if "%" in v:
            return v
        # 숫자면 % 붙이기
        try:
            num = float(v)
            if abs(num - int(num)) < 1e-9:
                return f"{int(num)}%"
            return f"{num}%"
        except Exception:
            return v

    for row in rows:
        raw = row.get("원문") or {}
        if not isinstance(raw, dict):
            raw = {}

        r1 = _norm_region(raw.get("jntcontrctDutyRgnNm1"))
        r2 = _norm_region(raw.get("jntcontrctDutyRgnNm2"))
        ratio = _norm_ratio(raw.get("rgnDutyJntcontrctRt"))

        # ✅ 1열 추가(다음열): 공동도급지역_추가
        row["공동도급지역"] = r1
        row["공동도급지역_추가"] = r2
        row["공동도급비율"] = ratio

        # ✅ 요청한 “삽입(덮어쓰기)”
        if r1:
            row["대표지역"] = r1
        if ratio:
            row["공고업종명"] = ratio
def log(msg: str) -> None:
    ts = datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')
    line = f"{ts} {msg}"

    # 1) stdout
    try:
        print(line, flush=True)
    except Exception:
        pass

    # 2) wrapper 환경이면 파일 기록 생략
    try:
        if os.environ.get('MAIN_SEND_LOCKED', '').strip() == '1':
            return
    except Exception:
        return

    # 3) 단독 실행 시 파일 기록
    try:
        with open(RUN_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

def ymdhm(dt: datetime) -> str:

    return dt.strftime("%Y%m%d%H%M")


def load_api_key() -> str:

    if not API_KEY_FILE.exists():

        raise RuntimeError("API 키 파일 없음: " + str(API_KEY_FILE))

    return API_KEY_FILE.read_text().strip()





def _parse_amount(v):

    """문자/숫자 금액 → int"""

    if v is None:

        return 0

    try:

        return int(str(v).replace(",", ""))

    except Exception:

        return 0





def build_detail_url(bid_no: str, bid_ord: str) -> str:

    """나라장터 상세조회 URL (대략적인 기본형)"""

    bid_no = (bid_no or "").strip()

    bid_ord = (bid_ord or "000").strip()

    if not bid_no:

        return ""

    return (

        "https://www.g2b.go.kr:8101/ep/result/serviceList.do"

        f"?bidno={bid_no}&bidseq={bid_ord}"

    )





def _append_csv_row(path: Path, fieldnames: list, row: dict):

    path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:

        w = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:

            w.writeheader()

        w.writerow(row)





# ---------------------------------------------

# Excel / 리포트 / 로테이트



# ---------------------------------------------

# 출력용 DF 변환 (시작일시 + 추정금액 콤마 + bidBeginDt 제거 + 컬럼 위치 조정)

# ---------------------------------------------

# ============================================================

# FINAL RULE ENGINE (single source of truth)

# ============================================================



def _fr_norm_text(v):

    return str(v or "").strip()



def _fr_clean_phone(v):

    import re

    return re.sub(r"[^0-9]", "", str(v or ""))



def _fr_parse_int(v):

    s = str(v or "").replace(",", "").strip()

    if not s:

        return 0

    try:

        return int(float(s))

    except Exception:

        return 0



def _fr_normalize_region(region):

    region = _fr_norm_text(region)

    mapping = {

        "세종특별자치시": "세종",

        "세종시": "세종",

        "충청북도": "충북",

        "경상북도": "경북",

        "대구광역시": "대구",

        "전국": "전국",

    }

    return mapping.get(region, region)



def _fr_get_raw(row):

    raw = row.get("원문") if isinstance(row, dict) else {}

    return raw if isinstance(raw, dict) else {}



def _fr_get_industry_code(row):

    raw = _fr_get_raw(row)



    for key in [

        "공고업종코드", "업종코드", "indstrytyCd", "indutyCd",

        "mainCnsttyCd", "cnsttyCd"

    ]:

        v = _fr_norm_text(row.get(key) if isinstance(row, dict) else "")

        if v in {"0037", "0038", "0039", "0040", "6202"}:

            return v

        v2 = _fr_norm_text(raw.get(key))

        if v2 in {"0037", "0038", "0039", "0040", "6202"}:

            return v2



    main_name = _fr_norm_text(raw.get("mainCnsttyNm") or row.get("공고업종명"))

    title = _fr_norm_text(raw.get("bidNtceNm") or row.get("공고명"))

    blob = f"{main_name} {title}"



    if "전기공사" in blob:

        return "0037"

    if "소방" in blob and "전기" in blob:

        return "0038"

    if "소방" in blob and "기계" in blob:

        return "0039"

    if (

        "기계설비공사업" in blob

        or "기계설비·가스공사업" in blob

        or "기계설비ㆍ가스공사업" in blob

        or "기계설비" in blob

        or "냉난방" in blob

    ):

        return "6202"



    return ""



def _fr_get_method_text(row):

    raw = _fr_get_raw(row)

    return _fr_norm_text(

        raw.get("sucsfbidMthdNm")

        or row.get("낙찰방법세부기준")

        or row.get("sucsfbidMthdNm")

        or row.get("낙찰자결정기준")

        or ""

    )



def _fr_get_presmpt_price(row):

    raw = _fr_get_raw(row)

    return _fr_parse_int(

        raw.get("presmptPrce")

        or raw.get("PresmptPrce")

        or row.get("PresmptPrce")

        or row.get("presmptPrce")

        or row.get("추정가격")

        or raw.get("presmptPrceAmt")

        or raw.get("estimatPrce")

        or raw.get("estimatPrice")

        or 0

    )



def _fr_decide_scope(row):

    method = _fr_get_method_text(row).replace(" ", "")

    presmpt = _fr_get_presmpt_price(row)



    if "소액수의" in method:

        return "지역"

    if ("10억원미만" in method) or ("10억미만" in method):

        return "지역"

    if ("10억원이상" in method) or ("10억이상" in method):

        return "전국"

    if presmpt >= 1_000_000_000:

        return "전국"

    return "지역"



def _fr_decide_local_region(row):

    raw = _fr_get_raw(row)



    for key in [

        "jntcontrctDutyRgnNm1",

        "prtcptLmtRgnNm",

        "prtcptPsblRgnNm",

        "대표지역",

        "지역",

    ]:

        v = _fr_normalize_region(raw.get(key) or (row.get(key) if isinstance(row, dict) else ""))

        if v in {"세종", "충북", "대구", "경북"}:

            return v



    site = _fr_norm_text(raw.get("cnstrtsiteRgnNm"))

    title = _fr_norm_text(raw.get("bidNtceNm") or row.get("공고명"))



    for src, dst in [

        ("세종", "세종"),

        ("충청북도", "충북"),

        ("충북", "충북"),

        ("경상북도", "경북"),

        ("경북", "경북"),

        ("대구", "대구"),

    ]:

        if src in site or src in title:

            return dst



    return ""





def _fr_decide_receivers(row):

    ind = _fr_get_industry_code(row)

    scope = _fr_decide_scope(row)

    local_region = _fr_decide_local_region(row)



    nation_common = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

    nation_0037 = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]



    local_common = {

        "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

        "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

        "대구": ["REDACTED_PRIVATE_VALUE"],

        "경북": ["REDACTED_PRIVATE_VALUE"],

    }



    if scope == "전국":

        if ind == "0037":

            return nation_0037

        if ind in {"0038", "0039", "0040", "6202"}:

            return nation_common

        return []



    if scope == "지역":

        if ind == "0037":

            return []

        if ind in {"0038", "0039", "0040", "6202"}:

            return local_common.get(local_region, [])

        return []



    return []

def _fr_apply_final_rule(row, log_fn=None):

    def _log(msg):

        try:

            if callable(log_fn):

                log_fn(msg)

        except Exception:

            pass



    scope = _fr_decide_scope(row)

    local_region = _fr_decide_local_region(row)

    ind = _fr_get_industry_code(row)

    receivers = _fr_decide_receivers(row)

    rep = "전국" if scope == "전국" else local_region



    if isinstance(row, dict):

        row["대표지역"] = rep

        row["수신번호"] = ",".join(receivers) if receivers else ""

        row["알림대상"] = "Y" if receivers else "N"

        row["_force_norecv"] = "" if receivers else "1"



    try:

        raw = _fr_get_raw(row)

        key = f"{_fr_norm_text(raw.get('bidNtceNo') or row.get('공고번호'))}-{_fr_norm_text(raw.get('bidNtceOrd') or row.get('차수') or '000')}"

    except Exception:

        key = ""



    _log(

        f"[FINAL_RULE] key={key} ind={ind} scope={scope} local_region={local_region} "

        f"rep={rep} recv={receivers} method={_fr_get_method_text(row)!r} presmpt={_fr_get_presmpt_price(row)}"

    )

    return row


def prepare_df_for_output(rows):

    import pandas as _pd

    import re as _re



    def _fmt_amount(v):

        if _pd.isna(v):

            return v

        ss = str(v).strip()

        if ss == "":

            return ss

        ss2 = _re.sub(r"[^\d\-]", "", ss)

        if ss2 in ("", "-"):

            return v

        try:

            n = int(ss2)

            return f"{n:,}"

        except Exception:

            return v



    def _extract_begin(raw):

        if not isinstance(raw, dict):

            return ""

        for k in ("bidBeginDt", "bidBeginDtTm", "bidBgnDt", "bidBgnDtTm", "bidBeginDttm"):

            v = raw.get(k)

            if v not in (None, "", "None", "nan"):

                return v

        return ""



    df = _pd.DataFrame(rows)



    # 1) 시작일시 생성/대체

    if "시작일시" in df.columns:

        # 값이 비어있는 경우만 원문에서 보강

        try:

            mask = df["시작일시"].isna() | (df["시작일시"].astype(str).str.strip() == "")

            if "원문" in df.columns:

                df.loc[mask, "시작일시"] = df.loc[mask, "원문"].apply(_extract_begin)

        except Exception:

            pass

    else:

        # bidBeginDt가 있으면 rename, 없으면 원문에서 생성

        if "bidBeginDt" in df.columns:

            df = df.rename(columns={"bidBeginDt": "시작일시"})

        else:

            if "원문" in df.columns:

                df["시작일시"] = df["원문"].apply(_extract_begin)

            else:

                df["시작일시"] = ""



    # 2) 최종적으로 bidBeginDt 컬럼은 제거(정책: 시작일시로 대체)

    if "bidBeginDt" in df.columns:

        df = df.drop(columns=["bidBeginDt"])



    # 3) 시작일시를 입찰마감일시 바로 앞에 배치

    if "시작일시" in df.columns and "입찰마감일시" in df.columns:

        cols = list(df.columns)

        cols.remove("시작일시")

        cols.insert(cols.index("입찰마감일시"), "시작일시")

        df = df[cols]



    # 4) 추정금액 콤마 포맷(저장 시 표시 목적)

    if "추정금액" in df.columns:

        df["추정금액"] = df["추정금액"].apply(_fmt_amount)



    return df



# ---------------------------------------------

def save_raw_excel(rows, timestamp: str):

    if not rows:

        return None

    # --- FORCE TAG (raw filename suffix) ---

    _ff = (os.getenv("FORCE_FROM") or "").strip()

    _ft = (os.getenv("FORCE_TO") or "").strip()

    force_suffix = ""

    if _ff or _ft:

        force_suffix = f"_FORCE_{_ff or 'NA'}_{_ft or 'NA'}"

    # --- END FORCE TAG ---

    filename = f"입찰공고_{timestamp}{force_suffix}.xlsx"

    out_path = RAW_DIR / filename

    df = prepare_df_for_output(rows)

    try:

        df.to_excel(out_path, index=False)

        log(f"[SAVE] raw: {out_path}")

    except Exception as e:

        log(f"[SAVE][ERR] raw 엑셀 저장 실패: {e}")

        return None

    return out_path





def save_split_by_region(rows, timestamp: str):

    if not rows:

        return []

    df = prepare_df_for_output(rows)

    if "대표지역" not in df.columns:

        log("[SAVE][WARN] '대표지역' 컬럼 없음 → split 생략")

        return []

    results = []

    for region in df["대표지역"].dropna().unique():

        region = ("" if region is None else str(region)).strip()
        safe_region = region if region else "미분류"

        region_df = df[df["대표지역"] == region].copy()

        fname = f"입찰공고_{timestamp}_{safe_region}{_get_force_suffix()}.xlsx"

        out = SPLIT_DIR / fname

        try:

            region_df.to_excel(out, index=False)

            results.append(out)

            log(f"[SAVE] split for region={safe_region} -> {out}")

        except Exception as e:

            log(f"[SAVE][ERR] split 저장 실패({safe_region}): {e}")

    return results




def _best_row_score(row):

    try:

        score = 0



        recv = str((row.get("수신번호") or "")).strip()

        if recv:

            score += 100



        rep = str((row.get("대표지역") or "")).strip()

        if rep and rep != "미분류":

            score += 30



        area = str((row.get("공동도급지역") or "")).strip()

        if area and area != "해당없음":

            score += 20



        ratio = str((row.get("공동도급비율") or "")).strip()

        if ratio and ratio != "해당없음":

            score += 10



        amt_raw = (

            row.get("추정금액")

            or row.get("추정가격")

            or row.get("PresmptPrce")

            or row.get("presmptPrce")

            or 0

        )

        try:

            amt = int(float(str(amt_raw).replace(",", "").strip() or "0"))

        except Exception:

            amt = 0

        if amt > 0:

            score += 5



        title = str((row.get("공고명") or "")).strip()

        if title:

            score += 1



        return score

    except Exception:

        return 0









def dedup_by_bid(rows):

    """

    같은 공고번호+차수는 1건만 남긴다.

    우선순위:

      1) 추정금액이 0이 아닌 row

      2) 공동도급비율/공동도급지역 정보가 더 풍부한 row

      3) 먼저 나온 row 유지

    """

    def _norm(v):

        return "" if v is None else str(v).strip()



    def _amt_score(row):

        amt = _norm(row.get("추정금액"))

        return 0 if amt in ("", "0", "0원", "0.0", "0.0원") else 1



    def _joint_score(row):

        score = 0

        jr = _norm(row.get("공동도급지역"))

        rr = _norm(row.get("공동도급비율"))

        if jr and jr not in ("해당없음", "nan", "None"):

            score += 1

        if rr and rr not in ("해당없음", "nan", "None", "0", "0%"):

            score += 1

        return score



    def _row_score(row):

        return (

            _amt_score(row),

            _joint_score(row),

        )



    best = {}

    order = []



    for row in rows:

        raw = row.get("원문") or {}

        bid_no = _norm(raw.get("bidNtceNo") or row.get("공고번호"))

        bid_ord = _norm(raw.get("bidNtceOrd") or row.get("차수") or "000")

        if not bid_no:

            continue



        key = f"{bid_no}-{bid_ord}"



        if key not in best:

            best[key] = row

            order.append(key)

            continue



        prev = best[key]

        if _row_score(row) > _row_score(prev):

            best[key] = row



    return [best[k] for k in order]




def _dedupe_best_rows(rows, log_fn=print):

    try:

        grouped = {}

        for row in rows:

            key = str((row.get("공고번호") or row.get("bidNtceNo") or row.get("key") or "")).strip()

            ordv = str((row.get("공고차수") or row.get("bidNtceOrd") or "")).strip()



            if key and ordv and "-" not in key:

                bid_key = f"{key}-{ordv}"

            else:

                bid_key = key or ordv



            if not bid_key:

                title = str((row.get("공고명") or "")).strip()

                bid_key = f"NO_KEY::{title}"



            grouped.setdefault(bid_key, []).append(row)



        out = []

        reduced = 0



        for bid_key, items in grouped.items():

            if len(items) == 1:

                out.append(items[0])

                continue



            best = sorted(items, key=lambda r: _best_row_score(r), reverse=True)[0]

            out.append(best)

            reduced += (len(items) - 1)



            try:

                scores = [_best_row_score(x) for x in items]

                log_fn(f"[DEDUPE][BESTROW] {bid_key} {len(items)} -> 1 scores={scores}")

            except Exception:

                pass



        try:

            log_fn(f"[DEDUPE][BESTROW] rows {len(rows)} -> {len(out)} (reduced={reduced})")

        except Exception:

            pass



        return out



    except Exception as e:

        try:

            log_fn(f"[DEDUPE][BESTROW][ERR] {e}")

        except Exception:

            pass

        return rows












def _prepare_report_df(df: pd.DataFrame) -> pd.DataFrame:

    # (1) 추정금액: 천단위 콤마 문자열로 고정

    if "추정금액" in df.columns:

        def _fmt_amt(v):

            try:

                if v is None:

                    return ""

                x = str(v).replace(",", "").strip()

                if x == "" or x.lower() in ("none","nan","null"):

                    return ""

                return f"{int(float(x)):,}"

            except Exception:

                return str(v)

        df["추정금액"] = df["추정금액"].apply(_fmt_amt)



    # (2) 시작일시가 있으면 '입찰마감일시' 바로 앞에 오도록 재배치

    if "시작일시" in df.columns and "입찰마감일시" in df.columns:

        cols = list(df.columns)

        cols.remove("시작일시")

        pos = cols.index("입찰마감일시")

        cols.insert(pos, "시작일시")

        df = df[cols]



    return df




def generate_html_report(rows, timestamp: str):

    df = prepare_df_for_output(rows)

    out_html = REPORT_DIR / f"입찰리포트_{timestamp}{_get_force_suffix()}.html"

    try:

        df.to_html(out_html, index=False)

        log(f"[REPORT] HTML 생성: {out_html}")

    except Exception as e:

        log(f"[REPORT][ERR] HTML 생성 실패: {e}")

    return out_html





def generate_excel_report(rows, timestamp: str):

    df = prepare_df_for_output(rows)

    out_xlsx = REPORT_DIR / f"입찰리포트_{timestamp}{_get_force_suffix()}.xlsx"

    try:

        df.to_excel(out_xlsx, index=False)

        log(f"[REPORT] EXCEL 생성: {out_xlsx}")

    except Exception as e:

        log(f"[REPORT][ERR] EXCEL 생성 실패: {e}")

    return out_xlsx





def update_report_index():

    index_file = REPORT_DIR / "입찰리포트_index.html"

    try:

        html_files = sorted(REPORT_DIR.glob("입찰리포트_*.html"))

        lines = ["<html><body><h2>입찰 리포트 Index</h2><ul>"]

        for f in html_files:

            name = f.name

            lines.append(f'<li><a href="{name}">{name}</a></li>')

        lines.append("</ul></body></html>")

        index_file.write_text("\n".join(lines), encoding="utf-8")

        log(f"[REPORT] index HTML 갱신: {index_file}")

    except Exception as e:

        log(f"[REPORT][ERR] index 생성 실패: {e}")





def save_split_excels(rows, prtcpt_map, timestamp: str):

    # prtcpt_map 은 확장용 — 지금은 region 기준 split

    return save_split_by_region(rows, timestamp)





def save_report_files(rows, timestamp: str):

    html = generate_html_report(rows, timestamp)

    xlsx = generate_excel_report(rows, timestamp)

    update_report_index()

    return [html, xlsx]





def backup_and_rotate_excels():

    """

    1일 지난 데이터는 backup/ 하위로 이동

    15일 지난 backup/* 파일은 삭제

    """

    today = datetime.now().date()

    backup_threshold = today - timedelta(days=1)

    delete_threshold = today - timedelta(days=15)



    targets = [RAW_DIR, SPLIT_DIR, REPORT_DIR]



    for base in targets:

        if not base.exists():

            continue



        backup_dir = base / "backup"

        backup_dir.mkdir(exist_ok=True)



        # 1일 지난 파일은 backup_dir 로 이동

        for f in base.glob("*"):

            if not f.is_file():

                continue

            if f.parent == backup_dir:

                continue

            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()

            if mtime <= backup_threshold:

                dest = backup_dir / f.name

                try:

                    shutil.move(str(f), str(dest))

                    log(f"[ROTATE] backup 이동: {f} -> {dest}")

                except Exception as e:

                    log(f"[ROTATE][ERR] backup 이동 실패: {f} ({e})")



        # backup_dir 안에서 15일 지난 파일은 삭제

        for f in backup_dir.glob("*"):

            if not f.is_file():

                continue

            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()

            if mtime <= delete_threshold:

                try:

                    f.unlink()

                    log(f"[ROTATE] 오래된 backup 삭제: {f}")

                except Exception as e:

                    log(f"[ROTATE][ERR] backup 삭제 실패: {f} ({e})")
# ---------------------------------------------

# 상태(last_run) + 히스토리

# ---------------------------------------------

def load_last_run_ts():

    if not LAST_RUN_FILE.exists():

        log("[STATE] last_run.txt 없음")

        return None

    try:

        text = LAST_RUN_FILE.read_text().strip()

        if not text:

            raise ValueError("빈 last_run.txt")

        dt = datetime.strptime(text, "%Y%m%d%H%M")

        log(f"[STATE] last_run.txt 로드: {text}")

        return dt

    except Exception as e:

        log(f"[STATE][ERR] last_run.txt 파싱 실패: {e}")

        return None





def save_last_run_ts(dt):

    """

    dt: datetime 또는 'YYYYMMDDHHMM' 문자열

    """

    try:

        if isinstance(dt, str):

            ts = dt

        else:

            ts = dt.strftime("%Y%m%d%H%M")

        with open(STATE_FILE, "w", encoding="utf-8") as f:

            f.write(ts)

        log(f"[STATE] last_run.txt 저장: {ts}")

    except Exception as e:

        log(f"[STATE][ERR] last_run.txt 저장 실패: {e}")





def load_send_history(keep_days: int = 30):

    """

    발송 이력 CSV를 읽어 최근 keep_days일 이내 공고만 유지.

    key = "bid_no-bid_ord"

    """

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not HISTORY_FILE.exists():

        return set(), []



    rows = []

    try:

        with open(HISTORY_FILE, newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for r in reader:

                rows.append(r)

    except Exception as e:

        log(f"[HISTORY][ERR] load_send_history 실패: {e}")

        return set(), []



    today = datetime.now().date()

    filtered = []

    for r in rows:

        s = r.get("sent_date") or r.get("sent_dt") or ""

        if not s:

            filtered.append(r)

            continue

        try:

            d = datetime.strptime(s, "%Y%m%d").date()

        except Exception:

            filtered.append(r)

            continue

        if (today - d).days <= keep_days:

            filtered.append(r)



    keys = set()

    for r in filtered:

        bid_no = str(r.get("bid_no") or "").strip()

        bid_ord = str(r.get("bid_ord") or "").strip()

        if bid_no:

            keys.add(f"{bid_no}-{bid_ord}")



    return keys, filtered





def save_send_history(rows: list):

    """

    ✅ history 소실 방지 버전



    문제: 동시에 2개 실행이 history_rows를 각각 읽고 '전체 덮어쓰기' 하면

         나중에 저장한 쪽이 앞 실행의 신규 기록을 지워버리는 lost-update 발생.



    해결:

      - HISTORY_FILE.lock 파일로 배타 락을 잡고,

      - 저장 직전에 "현재 HISTORY_FILE"을 다시 읽어서 rows와 병합,

      - tmp -> replace 로 원자적 교체

    """

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    tmp = HISTORY_FILE.with_suffix(".tmp")

    lock_path = HISTORY_FILE.with_suffix(HISTORY_FILE.suffix + ".lock")



    fieldnames = ["bid_no", "bid_ord", "sent_date", "sent_ts"]



    lock_fd = None

    try:

        # 1) lock (가능하면)

        try:

            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)

            if fcntl is not None:

                fcntl.lockf(lock_fd, fcntl.LOCK_EX)

        except Exception:

            lock_fd = None



        # 2) 현재 파일을 다시 읽어서 병합(중요)

        merged = []

        keys = set()



        def _add_row(r):

            if not isinstance(r, dict):

                return

            bid_no = str(r.get("bid_no") or "").strip()

            bid_ord = str(r.get("bid_ord") or "").strip() or "000"

            if not bid_no:

                return

            k = f"{bid_no}-{bid_ord}"

            if k in keys:

                return

            keys.add(k)

            merged.append({

                "bid_no": bid_no,

                "bid_ord": bid_ord,

                "sent_date": str(r.get("sent_date") or ""),

                "sent_ts": str(r.get("sent_ts") or ""),

            })



        # (a) 현재 HISTORY_FILE의 기존 데이터 먼저

        if HISTORY_FILE.exists():

            try:

                with open(HISTORY_FILE, newline="", encoding="utf-8") as f:

                    reader = csv.DictReader(f)

                    for r in reader:

                        _add_row(r)

            except Exception:

                pass



        # (b) 호출자가 준 rows(= history_rows + new_history)도 추가

        for r in (rows or []):

            _add_row(r)



        # 3) tmp로 저장 후 replace

        with open(tmp, "w", newline="", encoding="utf-8") as f:

            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()

            for r in merged:

                writer.writerow(r)



        tmp.replace(HISTORY_FILE)

        log(f"[HISTORY] save_send_history OK -> {HISTORY_FILE} (rows={len(merged)})")



    except Exception as e:

        log(f"[HISTORY][ERR] save_send_history 실패: {e}")



    finally:

        if lock_fd is not None:

            try:

                if fcntl is not None:

                    fcntl.lockf(lock_fd, fcntl.LOCK_UN)

            except Exception:

                pass

            try:

                os.close(lock_fd)

            except Exception:

                pass


def acquire_lock():
    if MAIN_SEND_LOCKED:
        log(f"[LOCK] wrapper lock already held -> skip internal lock (lock={LOCK_FILE_PATH})")
        log(f"[LOCK][DEBUG] wrapper-held lock={LOCK_FILE_PATH} holder={_read_lock_holder(LOCK_FILE_PATH)} {_lock_stat(LOCK_FILE_PATH)}")
        return -1
    try:

        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)



        # Linux

        if fcntl is not None:

            try:

                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                return fd

            except OSError:

                log("[LOCK] 이미 다른 main_send 실행 중 → 이번 실행은 건너뜀")
                log(f"[LOCK][DEBUG] lock={LOCK_FILE_PATH} holder={_read_lock_holder(LOCK_FILE_PATH)} {_lock_stat(LOCK_FILE_PATH)}")

                os.close(fd)

                return None



        # Windows

        if msvcrt is not None:

            try:

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

                return fd

            except OSError:

                log("[LOCK] 이미 다른 main_send 실행 중 → 이번 실행은 건너뜀")
                log(f"[LOCK][DEBUG] lock={LOCK_FILE_PATH} holder={_read_lock_holder(LOCK_FILE_PATH)} {_lock_stat(LOCK_FILE_PATH)}")

                os.close(fd)

                return None



        log("[LOCK][WARN] 파일락 모듈 없음 → 락 없이 진행")

        return fd



    except Exception as e:

        log(f"[LOCK][ERR] 락 파일 열기 실패: {e}")

        return None





# ---------------------------------------------

# 수집 → 정규화 → 지역/수신자

# ---------------------------------------------

def normalize_rows(api_rows):

    normalized = []

    for raw in api_rows:

        ind_code = str(raw.get("indstrytyCd") or "").strip()

        ind_name = str(raw.get("indstrytyNm") or "").strip()

        row = {

            "공고업종코드": ind_code,

            "공고업종명": ind_name,

            "공고번호": raw.get("bidNtceNo", ""),

            "차수": raw.get("bidNtceOrd", ""),

            "공고명": raw.get("bidNtceNm", ""),

            "입찰마감일시": raw.get("bidClseDt", ""),
            "낙찰방법세부기준": raw.get("sucsfbidMthdNm", ""),

            "게시일시": raw.get("bidNtceDt", ""),

            "추정금액": _parse_amount(

                raw.get("bdgtAmt")

                or raw.get("presmptPrce")

                or raw.get("indutyVAT")

                or raw.get("VAT")

            ),

            "대표지역": "",

            "수신번호": "",

            "알림대상": "",

            "원문": raw,

        }

        # --- PATCH:SUCSFBIDMTHDNM_TO_COL_V2 ---

        # 원문(dict)에 있는 sucsfbidMthdNm(낙찰방법세부기준)을 컬럼으로 끌어올림

        try:

            raw_obj = row.get("원문") or {}

            if isinstance(raw_obj, dict):

                v = raw_obj.get("sucsfbidMthdNm")

                if v is not None and str(v).strip() != "":

                    row["낙찰방법세부기준"] = str(v).strip()

        except Exception:

            pass

        # --- /PATCH:SUCSFBIDMTHDNM_TO_COL_V2 ---

        normalized.append(row)

    return normalized





def apply_region_classification(rows):



    for row in rows:

        raw = row.get("원문") or {}

        if not isinstance(raw, dict):

            raw = {}



        region_text = " ".join(

            [

                str(raw.get("jntcontrctDutyRgnNm1") or ""),

                str(raw.get("jntcontrctDutyRgnNm2") or ""),

                str(raw.get("jntcontrctDutyRgnNm3") or ""),

                str(raw.get("prtcptPsblRgnNm") or ""),

                str(raw.get("prtcptLmtRgnNm") or ""),

                str(raw.get("dlvrRgnNm") or ""),

                str(raw.get("bidNtceNm") or row.get("공고명") or ""),

            ]

        )



        rep = classify_region(region_text)
        # --- SUCS FIRST NATION RULE (2026-02-02) ---
        # sucsfbidMthdNm/낙찰방법세부기준 문구를 최우선으로 전국/지역 보정
        # - "10억원 미만"/"10억 미만" 포함: 전국 금지
        # - "10억원 이상"/"10억 이상" 포함: 전국
        try:
            rep
        except Exception:
            rep = (row.get("대표지역") or "") if isinstance(row, dict) else ""
        try:
            rep2
        except Exception:
            rep2 = ""
        try:
            raw
        except Exception:
            raw = {}  # 안전장치
        mt = (raw.get("sucsfbidMthdNm") or (row.get("낙찰방법세부기준") if isinstance(row, dict) else "") or "")
        mt2 = str(mt).replace(" ", "")
        if ("10억원미만" in mt2) or ("10억미만" in mt2):
            pass  # 전국 금지
        elif ("10억원이상" in mt2) or ("10억이상" in mt2):
            rep2 = "전국"
        # 대표지역 확정(rep2 우선) — 여기서 강제로 반영
        if isinstance(row, dict):
            row["대표지역"] = (rep2 or rep or row.get("대표지역") or "")
        # --- /SUCS FIRST NATION RULE ---





        # ✅ '기타'면 텍스트에서 시/도명을 추가로 추출해서 보정

        rep2 = ""

        if rep == "기타":

            try:

                rep2 = (infer_region_when_etc(region_text) if infer_region_when_etc else "") or ""

            except Exception:

                rep2 = ""



        # --- PATCH:NATION_RULE_10EOK_OR_JOINT_AND_RATE (2026-01-07) ---

        # 전국조건:
        # ✅ presmptPrce(추정가격) 최우선 규칙
        #    - 10억 이상: 무조건 '전국'
        #    - 10억 미만: 절대 '전국'으로 올리지 않음(키워드/문구 무시)
        v_price = raw.get("presmptPrce") or raw.get("presmptPrceAmt") or raw.get("estimatPrce") or raw.get("estimatPrice")
        def _to_int_amount(v):
            if v is None:
                return None
            ss = str(v).strip().replace(',', '')
            if ss == '' or ss.lower() in ('none','nan','n/a'):
                return None
            try:
                return int(float(ss))
            except Exception:
                return None
        amt = _to_int_amount(v_price)
        if amt is not None:
            if amt >= 1_000_000_000:
                rep2 = "전국"
            else:
                rep2 = ""   # 10억 미만이면 전국 금지
        else:
            # 추정가격이 없으면 기존 흐름 유지(지역 텍스트 기반)
            pass
        # --- SUCS FIRST NATION RULE (2026-02-02) ---
        # sucsfbidMthdNm(낙찰방법세부기준) 문구를 최우선으로 전국/지역 보정
        # - "10억원 미만"/"10억 미만" 포함: 전국 금지
        # - "10억원 이상"/"10억 이상" 포함: 전국
        mt = (raw.get("sucsfbidMthdNm") or row.get("낙찰방법세부기준") or "")
        mt2 = str(mt).replace(" ", "")
        if ("10억원미만" in mt2) or ("10억미만" in mt2):
            pass  # 전국 금지 (기존 rep/rep2 유지)
        elif ("10억원이상" in mt2) or ("10억이상" in mt2):
            rep2 = "전국"
        # --- /SUCS FIRST NATION RULE ---

        row["대표지역"] = (rep2 if (locals().get("rep2") == "전국") else (rep or ""))



        # --- FINAL REP REGION GUARD (2026-02-02) ---
        # 대표지역이 허용목록 밖이면 무조건 수신자 차단(규칙 위반 방지)
        try:
            _allowed_regions = {
                "전국","세종","충북","대구","경북",
                "서울","경기","인천","충남","전남","전북","경남",
                "부산","대전","강원","제주","광주","기타"
            }
            _rep_final = (row.get("대표지역") or "").strip()
            if _rep_final and (_rep_final not in _allowed_regions):
                row["_force_norecv"] = "1"
                row["수신번호"] = ""
                try:
                    log(f"[FILTER][REGION-NO-RULE][FINAL] key={row.get(_key,)} rep={_rep_final!r} -> FORCE NORECV")
                except Exception:
                    pass
        except Exception:
            pass
                        











def apply_final_rule_all_rows(rows, log_fn=log):

    for row in rows:

        _fr_apply_final_rule(row, log_fn=log_fn)

    return rows





def parse_receivers(row):

    recv_csv = str(row.get("수신번호") or "").strip()

    return list(dict.fromkeys([x.strip() for x in recv_csv.split(",") if x.strip()]))



def apply_receivers(rows):

    for row in rows:

        _fr_apply_final_rule(row, log_fn=log)

    return rows

def filter_rows(rows):

    out = []

    for row in rows:

        raw = row.get("원문") or {}

        bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "").strip()

        if not bid_no:

            continue



        ind = str(

            row.get("공고업종코드")

            or raw.get("indstrytyCd")

            or raw.get("indstrytyNm")

            or ""

        ).strip()

        if ind and ind not in TARGET_INDS:

            continue



        out.append(row)

    return out





def dedupe_by_bid(rows):

    seen = set()

    out = []

    for row in rows:

        raw = row.get("원문") or {}

        bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "").strip()

        bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "").strip()

        key = f"{bid_no}-{bid_ord}"
        # DBG_BID: 디버그 대상 1건만 처리하고 나머지는 스킵/종료
        _dbg_bid = (os.environ.get('DBG_BID') or '').strip()
        _dbg_once = os.environ.get('DBG_BID_ONLY_ONCE', '1').strip()
        if _dbg_bid and _dbg_bid not in str(key):
            continue
        _DBG_HIT = True

        if not bid_no:

            out.append(row)

            continue

        if key in seen:

            continue

        seen.add(key)

        out.append(row)

    return out





def _fetch_prtcpt_region_map_for_rows(rows):

    # 확장용 스텁

    return {}





def collect_data(bgn_dt_str: str, end_dt_str: str):

    start_dt = datetime.strptime(bgn_dt_str, "%Y%m%d%H%M")

    end_dt = datetime.strptime(end_dt_str, "%Y%m%d%H%M")

    api_key = load_api_key()



    log(

        f"[NARA] collect_bids_range 기간 {bgn_dt_str} ~ {end_dt_str}, "

        f"inds={TARGET_INDS}, min_budget={MIN_BUDGET}"

    )

    api_rows = collect_bids_range(

        api_key=api_key,

        indstry_codes=TARGET_INDS,

        start_dt=start_dt,

        end_dt=end_dt,

        min_budget=MIN_BUDGET,

    )

    # ✅ sucsfbidMthdNm(낙찰방법세부기준) 보강(가능한 경우만)
    try:
        try:
            _n0 = (len(api_rows) if isinstance(api_rows, list) else (0 if not api_rows else -1))
            if _n0:
                log(f"[NARA][DBG] before enrich_sucs len(api_rows)={_n0} type={type(api_rows)}")
        except Exception as _e:
            log(f"[NARA][DBG][WARN] before enrich_sucs log fail: {_e}")
        api_rows, injected = _safe_enrich_sucs(api_key, api_rows, start_dt, end_dt)
        try:
            _n1 = (len(api_rows) if isinstance(api_rows, list) else (0 if not api_rows else -1))
            if _n1:
                log(f"[NARA][DBG] after enrich_sucs injected={injected} len(api_rows)={_n1} type={type(api_rows)}")
        except Exception as _e:
            log(f"[NARA][DBG][WARN] after enrich_sucs log fail: {_e}")
    except Exception as e:
        log(f"[NARA][WARN] enrich_cnstwk_sucs_method 실패: {e}")





    # [PATCH] 낙찰방법세부기준(sucsfbidMthdNm) 보강
    try:
        if injected:
            log(f"[NARA] sucsfbidMthdNm injected={injected}")
    except Exception as e:
        try:
            log("[NARA][DBG][WARN] after enrich_sucs log fail: %s" % e)
        except Exception:
            pass

    # __A_RULE_OVERRIDE_APPLIED__

    # ============================================================

    # A안 규칙 최종 오버라이드 (2026-02-13)

    # - 전국/지역: PresmptPrce(추정가격) 10억 기준

    # - sucsfbidMthdNm/낙찰방법세부기준 문구 최우선(10억 이상/미만)

    # - 대상 공종: 0037/0038/0039/0040/6202

    # - 수신자:

    #   * (0038/0039/0040/6202) 전국: REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

    #   * (0037) 전국: REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

    #   * 세종: REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

    #   * 충북: REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

    #   * 대구/경북: REDACTED_PRIVATE_VALUE

    # - 허용 대표지역: 전국/세종/충북/대구/경북 (그 외는 강제 차단)

    # ============================================================

    try:

        import re

    

        def _a_norm(x):

            return str(x or "").strip()

    

        def _a_extract_codes(row):

            want = {"0037","0038","0039","0040","6202"}

            pat = re.compile(r"\\b(0037|0038|0039|0040|6202)\\b")

            found = set()

            try:

                items = list(getattr(row, "items", lambda: [])())

            except Exception:

                items = []

            for k,v in items:

                txt = _a_norm(v)

                if not txt:

                    continue

                for m in pat.findall(txt):

                    if m in want:

                        found.add(m)

            for k in list(getattr(row, "keys", lambda: [])()):

                kk = _a_norm(k)

                for m in pat.findall(kk):

                    if m in want:

                        found.add(m)

            return found

    

        def _a_classify_rep(presmpt_prce, sucs_text, rep_guess):

            # 원문(sucsfbidMthdNm/낙찰방법세부기준) 문구로 전국/지역 판정

            # - "소액수의" => 지역(전국 금지)

            # - "추정가격 ... 10억원 이상" (예: 50억원 미만 10억원 이상) => 전국

            # - "추정가격 ... 10억원 미만" 또는 상한 < 10억 (예: 4억원 미만 2억원 이상) => 지역(전국 금지)

            # - 없으면 PresmptPrce(추정가격)로 10억 기준



            t_raw = _a_norm(sucs_text)

            t = t_raw.replace(" ", "")



            # 1) 소액수의는 무조건 지역(전국 금지)

            if "소액수의" in t:

                return _a_norm(rep_guess)



            # 2) 기존 키워드(10억 이상/미만) 즉시 판정

            if ("10억원이상" in t) or ("10억이상" in t):

                return "전국"

            if ("10억원미만" in t) or ("10억미만" in t):

                return _a_norm(rep_guess)



            # 3) "추정가격 ... N억원 미만 M억원 이상" 같은 범위 문구 해석

            #    - lower(이상) >= 10 => 전국

            #    - upper(미만) < 10 => 지역

            upper = None

            lower = None

            try:

                # 미만(상한)

                ups = re.findall(r"(\d+(?:\.\d+)?)\s*억\s*원?\s*미만", t_raw)

                if ups:

                    upper = float(ups[0])  # 보통 첫 상한이 가장 명확

                # 이상(하한)

                lows = re.findall(r"(\d+(?:\.\d+)?)\s*억\s*원?\s*이상", t_raw)

                if lows:

                    # 문구에 여러 개면 보수적으로 가장 큰 하한을 사용

                    lower = max(float(x) for x in lows if x)

            except Exception:

                upper = None

                lower = None



            if (lower is not None) and (lower >= 10.0):

                return "전국"

            if (upper is not None) and (upper < 10.0):

                return _a_norm(rep_guess)



            # 4) 마지막: PresmptPrce(추정가격) 숫자로 판정

            amt = None

            try:

                if presmpt_prce is not None and _a_norm(presmpt_prce) != "":

                    amt = int(float(str(presmpt_prce).replace(",", "").strip()))

            except Exception:

                amt = None



            if amt is not None:

                return "전국" if amt >= 1_000_000_000 else _a_norm(rep_guess)



            return _a_norm(rep_guess)


        def _a_receivers(codes, rep):

            rep = _a_norm(rep)

            A = {"0038","0039","0040","6202"}

            E = {"0037"}

            codes = set([_a_norm(c) for c in (codes or []) if _a_norm(c)])

            map_local = {

                "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

                "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],

                "대구": ["REDACTED_PRIVATE_VALUE"],

                "경북": ["REDACTED_PRIVATE_VALUE"],

            }

            allA = ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"]

            allE = ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"]

            if codes & E:

                if rep == "전국":

                    return allE

                return map_local.get(rep, [])

            if codes & A:

                if rep == "전국":

                    return allA

                return map_local.get(rep, [])

            return []

    

        _force = (os.environ.get("FORCE_RECV") or "").strip()

        if _force:

            row["_force_norecv"] = ""

            # removed: row["수신번호"] = _force
        else:

            presmpt = (row.get("PresmptPrce") or row.get("presmptPrce") or row.get("추정가격") or row.get("추정가") or row.get("PresmptPrice") or row.get("bdgtAmt") or ((row.get("원문") or {}).get("PresmptPrce") if isinstance(row.get("원문"), dict) else None) or ((row.get("원문") or {}).get("bdgtAmt") if isinstance(row.get("원문"), dict) else None))

            sucs = row.get("sucsfbidMthdNm") or row.get("낙찰방법세부기준") or row.get("낙찰자결정기준") or ""

            rep_guess = row.get("대표지역") or ""

            rep_final = _a_classify_rep(presmpt, sucs, rep_guess)

            row["대표지역"] = rep_final

            # [PATCH] 모든 지역 허용
            # 앞단에서 계산된 알림대상/수신번호를 존중한다.
            codes = _a_extract_codes(row)
            rcv = _a_receivers(codes, rep_final)

    except Exception:

        pass



    if api_rows:
        log("[NARA][WARN] sucsfbidMthdNm enrich failed")

    if not api_rows:

        log("[NARA] collect_bids_range 결과 0건")

        return []



    log(f"[NARA] collect_bids_range 원시 건수 = {len(api_rows)}")
    # === DBG_RAW_KEYS: dump first raw item keys (TEST only) ===
    if (os.environ.get('DBG_RAW_KEYS') or '').strip() in ('1','Y','y','true','True'):
        try:
            _r0 = (api_rows[0] if isinstance(api_rows, list) and api_rows else None)
            if isinstance(_r0, dict):
                _keys = list(_r0.keys())
                log(f"[DBG_RAW_KEYS] raw[0] type=dict keys({len(_keys)})={_keys[:40]}")
                for _k in ('bidNtceNo','bidNtceOrd','bidntceno','bidntceord','bid_ntce_no','bid_ntce_ord'):
                    if _k in _r0:
                        log(f"[DBG_RAW_KEYS] raw[0][{_k}]={_r0.get(_k)}")
            else:
                log(f"[DBG_RAW_KEYS] raw[0] type={type(_r0)} value={str(_r0)[:200]}")
        except Exception as _e:
            log(f"[DBG_RAW_KEYS][ERR] {_e}")



    rows = normalize_rows(api_rows)
    # --- FILTER: drop zero/empty presmpt ---
    _before_amt_filter = len(rows)
    def _is_bad_amt(r):
        v = str(r.get('추정금액') or '').strip().replace(',', '')
        return v in ('', '0', '0원', '0.0', '0.0원')
    rows = [r for r in rows if not _is_bad_amt(r)]
    log(f"[FILTER][AMT] rows {_before_amt_filter} -> {len(rows)} (dropped={_before_amt_filter-len(rows)})")

    # ✅ 여기 추가 (공동도급지역/추가/비율 반영 + 대표지역/공고업종명 덮어쓰기)
    apply_joint_contract_fields(rows)
    _before_bid_dedup = len(rows)
    rows = dedup_by_bid(rows)
    log(f"[DEDUPE][BID] rows {_before_bid_dedup} -> {len(rows)} (reduced={_before_bid_dedup-len(rows)})")



    apply_region_classification(rows)

    apply_receivers(rows)



    for row in rows:

        try:

            _fr_apply_final_rule(row, log_fn=log)

        except Exception as e:

            log(f"[FINAL_RULE][ERR][COLLECT] {e}")



    rows = dedupe_by_bid(rows)

    rows = _dedupe_best_rows(rows, log_fn=log)
    log(f"[COLLECT] normalized+dedupe rows = {len(rows)}")
    if enrich_cnstwk_sucs_method:
        try:
            # enrich sucsfbidMthdNm into rows (in-place)
            enrich_cnstwk_sucs_method(api_key, rows, timeout=20)
            # ensure report field: 낙찰방법세부기준
            for _r in rows:
                if isinstance(_r, dict):
                    v = _r.get('sucsfbidMthdNm')
                    if v is not None and str(v).strip() != '':
                        _r.setdefault('낙찰방법세부기준', str(v))
        except Exception as e:
            log(f"[NARA][WARN] enrich_cnstwk_sucs_method 실패: {e}")

    return rows





# ---------------------------------------------
# Kakao TB_0485 필드/메시지 빌드  (✅ kakao_send_tb0485.py 와 "완전 일치" 버전)
# ---------------------------------------------

def build_tb0485_fields(row: dict) -> dict:
    """
    kakao_send_tb0485.py 가 기대하는 keys:
      - bid_name, close_time, joint_region, joint_rate, amount_str(or amount), bid_no, bid_ord
    """
    raw = row.get("원문") or {}

    def _g(*names, default=""):
        for name in names:
            if isinstance(raw, dict) and raw.get(name) not in (None, "", " "):
                return raw.get(name)
            if row.get(name) not in (None, "", " "):
                return row.get(name)
        return default

    # ----------------------------
    # 공고번호 / 차수
    # ----------------------------
    bid_no = str(_g("bidNtceNo", "공고번호", default="")).strip()
    bid_ord = str(_g("bidNtceOrd", "차수", default="000")).strip() or "000"

    # ----------------------------
    # 공고명 / 마감일시
    # ----------------------------
    bid_name = _g("bidNtceNm", "공고명", default="공고명미기재")
    close_time = _g("bidClseDt", "입찰마감일시", default="미기재")

    # ----------------------------
    # ✅ 공동도급지역: "참가능지역" 지역명 넣기
    #    (우선순위: prtcptPsblRgnNm -> prtcptLmtRgnNm -> joint/jntcontrctDutyRgnNm*)
    # ----------------------------
    prtcpt_region = _g(
        "prtcptPsblRgnNm",   # 참가가능지역(가능)
        "prtcptLmtRgnNm",    # 참가제한지역(제한)
        default=""
    )

    # 혹시 위 두 값이 없으면 공동도급지역 후보를 fallback
    fallback_joint_region = " ".join([
        str(_g("jntcontrctDutyRgnNm1", default="")),
        str(_g("jntcontrctDutyRgnNm2", default="")),
        str(_g("jntcontrctDutyRgnNm3", default="")),
    ]).strip()

    joint_region = (str(prtcpt_region).strip() or fallback_joint_region or "없음").strip()
    if joint_region.lower() in ("none", "n/a", "nan", ""):
        joint_region = "없음"

    # ----------------------------
    # ✅ 공동도급비율: 없으면 "없음", 숫자(또는 문자열) 있으면 그대로
    #    (키 후보: jntcontrctRt / jntcontrctRate / jntcontrctRatio 등 혼재 가능성 대비)
    # ----------------------------
    jr = _g(
        "rgnDutyJntcontrctRt",   # ✅ 추가
        "공동도급비율",             # ✅ 추가(우리가 만들어둔 컬럼)
        "jntcontrctRt",
        "jntcontrctRate",
        "jntcontrctRatio",
        "jntcontrctPercent",
        default=""
    )
    joint_rate = str(jr).strip()
    if not joint_rate or joint_rate.lower() in ("none", "n/a", "nan"):
        joint_rate = "없음"

    # ----------------------------
    # 금액: amount(int) + amount_str(콤마)
    # ----------------------------
    amt_raw = _g("presmptPrce", "bdgtAmt", "추정금액", default=0)
    try:
        amt_int = int(str(amt_raw).replace(",", "").strip() or "0")
    except Exception:
        amt_int = 0
    amount_str = f"{amt_int:,}"

    # ----------------------------
    # 상세 URL(있으면 사용, 없으면 기본 생성)
    # ----------------------------
    detail_url = (
        _g("bidNtceDtlUrl", "detail_url", "URL", default="")
        or build_detail_url(bid_no, bid_ord)
    )

    # ✅ kakao_send_tb0485.py 완전 호환 필드
    fields = {
        "bid_name": bid_name,
        "close_time": close_time,
        "joint_region": joint_region,     # ✅ 메시지의 "공동도급지역"에 사용됨(요청사항 반영)
        "joint_rate": joint_rate,         # ✅ 메시지의 "공동도급비율"에 사용됨(없으면 '없음')
        "amount": amt_int,
        "amount_str": amount_str,         # ✅ kakao_send_tb0485.py 1순위 사용
        "bid_no": bid_no,
        "bid_ord": bid_ord,
        "detail_url": detail_url,
        "region": _g("대표지역", "지역", default=""),     # (추가정보: 있어도 무해)
        "org_name": _g("dminsttNm", "ntceInsttNm", "발주기관", default=""),  # (추가정보)
        "낙찰방법세부기준": _g("sucsfbidMthdNm", "낙찰방법세부기준", default=""),
    }
    return fields

# ---------------------------------------------

# Alligo TB_0485 발송 래퍼 + 재시도/로그

# ---------------------------------------------

def send_tb0485_one(phone: str, fields: dict, dry_run: bool = False) -> dict:

    bid_no = fields.get("bid_no", "")

    bid_ord = fields.get("bid_ord", "")

    bid_name = fields.get("bid_name", "")

    key = f"{bid_no}-{bid_ord}" if bid_no else ""



    log(f"[SEND] TRY TB0485 {key} / {bid_name} -> {phone}, dry_run={dry_run}")



    if dry_run:

        return {"sent": False, "dry_run": True}



    try:

        res = None

        try:

            # [AUTO] alarm filter v3 (method text) - block before sending

            try:

                _m = ''

                try:

                    _m = fields.get('낙찰방법세부기준', '') if isinstance(fields, dict) else ''

                except Exception:

                    _m = ''

                if _should_block_by_method_text(_m):

                    try:

                        log(f"[FILTER][SKIP] TB_0485 blocked by method: {_m}")

                    except Exception:

                        pass

                    return {'sent_ok': 0, 'skipped': 1, 'reason': 'method_block'}

            except Exception as _e:

                try:

                    log(f"[FILTER][WARN] method check failed: {_e}")

                except Exception:

                    pass


            res = kakao_send_for_item(phone, fields, dry_run=False)

        except TypeError:

            res = kakao_send_for_item(fields, phone, dry_run=False)



        log(f"[SEND] RES TB0485 {key} -> {phone}: {res}")

        ok = False
        if isinstance(res, dict):
            # {'ok': True} / {'ok': 'true'} / {'ok': '1'} 모두 성공 처리
            if str(res.get("ok", "")).strip().lower() in ("true", "1", "y", "yes"):
                ok = True
            elif res.get("sent") is True:
                ok = True
            else:
                code = str(res.get("code") or res.get("result_code") or "").strip()
                if code in ("0", "1"):
                    ok = True
                else:
                    sc = res.get("success_cnt")
                    if sc is not None and str(sc) not in ("0", "0.0", "", "None"):
                        ok = True
        elif res is True or str(res).upper() in ("OK", "SUCCESS"):
            ok = True





        return {"sent": ok, "raw": res}



    except Exception as e:

        log(f"[SEND][ERR-INNER] TB0485 {key} -> {phone}: {e}")

        return {"sent": False, "error": str(e)}





def send_tb0485_retry_and_log(phone: str, fields: dict, key: str, title: str, max_retry: int = 3) -> dict:

    """

    - TB_0485 발송을 max_retry 만큼 재시도

    - 성공/실패를 data_gd/kakao_logs 에 CSV로 누적 기록

    """
    # [PATCH] NO_SEND -> max_retry=1 (blocked는 실패가 아니라 정상차단)
    if (os.getenv('HARD_NO_SEND','')=='1') or (os.getenv('FORCE_NO_SEND','')=='1'):
        max_retry = 1


    day = datetime.now().strftime("%Y%m%d")

    ok_path = KAKAO_LOG_DIR / f"alimtalk_success_{day}.csv"

    fail_path = KAKAO_LOG_DIR / f"alimtalk_fail_{day}.csv"

    log_fields = ["ts", "key", "phone", "title", "try_no", "sent", "error", "raw"]



    last_res = None

    for i in range(1, max_retry + 1):

        res = send_tb0485_one(phone, fields, dry_run=False)

        last_res = res



        # [PATCH] HARD_NO_SEND 등 'blocked'는 실패가 아니라 정상 차단이므로 재시도/FAIL 처리하지 않음
        if isinstance(res, dict) and res.get('blocked') is True:
            return {'sent': False, 'try_no': i, 'raw': res, 'blocked': True}
        # [PATCH] HARD_NO_SEND 등 'blocked'는 실패가 아니라 정상 차단이므로 재시도/FAIL 처리하지 않음
        if isinstance(res, dict) and res.get('blocked') is True:
            return {'sent': False, 'try_no': i, 'raw': res, 'blocked': True}
        sent = bool(isinstance(res, dict) and res.get("sent") is True)

        err = ""

        raw = ""

        try:

            if isinstance(res, dict):

                err = str(res.get("error") or "")

                raw = str(res.get("raw") or "")

            else:

                raw = str(res)

        except Exception:

            pass



        row = {

            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "key": key,

            "phone": phone,

            "title": title,

            "try_no": i,

            "sent": "Y" if sent else "N",

            "error": err,

            "raw": raw[:500],

        }



        if sent:

            _append_csv_row(ok_path, log_fields, row)

            return {"sent": True, "try_no": i, "raw": res}



        _append_csv_row(fail_path, log_fields, row)



    return {"sent": False, "try_no": max_retry, "raw": last_res}
# ---------------------------------------------

# Argument 파서

# ---------------------------------------------

def parse_args():

    p = argparse.ArgumentParser()

    p.add_argument("--hours", type=int, default=1, help="기본 조회 시간(시간 단위, 기본 1시간)")

    p.add_argument("--no-send", action="store_true", help="알림톡 전송 없이 조회/저장만 수행")

    return p.parse_args()





def _user_explicitly_set_hours() -> bool:

    for arg in sys.argv[1:]:

        if arg.startswith("--hours"):

            return -1

    return False





# ---------------------------------------------
# 메인
# ---------------------------------------------

# === TEST SAFETY PATCH: force single receiver in TEST ===

TEST_FORCE_SINGLE_RECEIVER = (os.environ.get('TEST_FORCE_SINGLE_RECEIVER') == '1')
TEST_SINGLE_RECEIVER = "REDACTED_PRIVATE_VALUE"
def _force_test_dry_run(dry_run: bool) -> bool:

    """In TEST env, force DRY RUN unless ALLOW_SEND=1."""

    try:

        env = (os.environ.get("N_DATA_ENV") or "").strip().upper()

        allow_send = (os.environ.get("ALLOW_SEND") or "").strip() == "1"

        if env == "TEST" and not allow_send:

            return True

    except Exception:

        # 안전 우선: 예외면 DRY RUN

        return True

    return dry_run





def _force_test_receivers(receivers):

    """In TEST env, force notifications to a single safe number to prevent accidents."""

    try:

        env = (os.environ.get("N_DATA_ENV") or "").strip().upper()

    except Exception:

        env = ""

    if env == "TEST" and TEST_FORCE_SINGLE_RECEIVER:

        return [TEST_SINGLE_RECEIVER]

    return receivers

# === END TEST SAFETY PATCH ===


def main():
    args = parse_args()
    SMOKE_MAX_SEND = int(os.environ.get('SMOKE_MAX_SEND','0') or '0')
    if SMOKE_MAX_SEND:
        log(f"[SMOKE] SMOKE_MAX_SEND={SMOKE_MAX_SEND} (성공 발송 제한)")
    now = datetime.now()
    now_ts = ymdhm(now)

    log("[MAIN] === main_send.py START ===")


    # --- FORCE start marker ---

    try:

        _suffix = _get_force_suffix()

        if _suffix:

            _ff = (os.getenv("FORCE_FROM") or "")

            _ft = (os.getenv("FORCE_TO") or "")

            log(f"[FORCE] ON from={_ff} to={_ft} suffix={_suffix}")

    except Exception:

        pass

    log(f"[CONF] NAS_BASE={NAS_BASE}")

    lock_fd = acquire_lock()
    if lock_fd is None:
        log("[LOCK] 이미 실행 중인 main_send.py 가 있어서 종료합니다.")
        return

    success = False

    try:
        backup_and_rotate_excels()

        explicit_hours = _user_explicitly_set_hours()
        last_run = load_last_run_ts()

        if explicit_hours:
            hours = max(1, int(args.hours))
            start_dt = now - timedelta(hours=hours)
            log(f"[MAIN] --hours={hours} 명시 → 최근 {hours}시간 강제 조회 (last_run 무시)")
        else:
            last_dt = last_run if isinstance(last_run, datetime) else None
            today = now.date()
            first_run_today = (last_dt is None) or (last_dt.date() < today)

            if first_run_today and 6 <= now.hour <= 9:
                start_dt = datetime.combine(today - timedelta(days=1), datetime.min.time())
                log("[MAIN] 오늘 첫 실행(아침) → 전날 00:00부터 조회 (A안)")
            elif last_dt is not None:
                start_dt = last_dt - timedelta(minutes=GRACE_MINUTES)
                log(f"[MAIN] last_run 기반 조회 시작: {ymdhm(start_dt)} (버퍼 {GRACE_MINUTES}분 포함)")
            else:
                hours = args.hours if args.hours is not None else 1
                start_dt = now - timedelta(hours=hours)
                log(f"[MAIN] last_run 없음/이상 → --hours={hours} 기준 조회 적용")

        end_dt = now

        max_span = timedelta(days=MAX_DAYS)
        if end_dt - start_dt > max_span:
            adj = end_dt - max_span
            log(f"[MAIN][WARN] 조회기간이 {MAX_DAYS}일 초과 → {ymdhm(adj)}부터로 조정")
            start_dt = adj

        bgn_dt_str = ymdhm(start_dt)
        end_dt_str = ymdhm(end_dt)
        


        # --- BEGIN FORCE_FROM/TO override ---
        try:
            _ff = (os.getenv("FORCE_FROM") or "").strip()
            _ft = (os.getenv("FORCE_TO") or "").strip()
            if _ff or _ft:
                if _ff and (len(_ff) == 12) and _ff.isdigit():
                    bgn_dt_str = _ff
                if _ft and (len(_ft) == 12) and _ft.isdigit():
                    end_dt_str = _ft
                try:
                    log(f"[OVERRIDE] FORCE_FROM/TO -> {bgn_dt_str} ~ {end_dt_str}")
                except Exception:
                    pass
        except Exception as _e:
            try:
                log(f"[WARN] FORCE_FROM/TO override failed: {_e}")
            except Exception:
                pass
        # --- END FORCE_FROM/TO override ---


        # --- FORCE TAG (file name suffix) ---
        _force_ff = (os.getenv("FORCE_FROM") or "").strip()
        _force_ft = (os.getenv("FORCE_TO") or "").strip()
        force_suffix = ""
        if _force_ff or _force_ft:
            force_suffix = f"_FORCE_{_force_ff or 'NA'}_{_force_ft or 'NA'}"
        # --- END FORCE TAG ---
        log(f"[MAIN] 조회기간 {bgn_dt_str} ~ {end_dt_str}")

        # -------------------------------------------------
        # 1) 수집
        # -------------------------------------------------
        rows = collect_data(bgn_dt_str, end_dt_str)
        log(f"[FETCH] total collected rows = {len(rows)}")

        if not rows:
            log("[COLLECT] 조회 결과 없음 (rows=0)")
            if not args.no_send:
                save_last_run_ts(now_ts)
            else:
                log('[STATE] --no-send 이므로 last_run.txt 저장 생략')
            success = True
            return

        # -------------------------------------------------
        # 2) 업종/기본 필터
        # -------------------------------------------------
        rows = filter_rows(rows)
        log(f"[FILTER] 업종/기본 필터 후 rows = {len(rows)}")

        if not rows:
            log("[FILTER] 필터 후 남은 공고 없음.")
            if not args.no_send:
                save_last_run_ts(now_ts)
            else:
                log('[STATE] --no-send 이므로 last_run.txt 저장 생략')
            success = True
            return

        # -------------------------------------------------
        # 3) history 기준 제외 (저장/발송 대상에서 제거)
        # -------------------------------------------------
        history_keys, history_rows = load_send_history()
        before = len(rows)
        filtered_rows = []
        skipped_keys = []

        for r in rows:
            raw = r.get("원문") or {}
            bid_no = str(raw.get("bidNtceNo") or r.get("공고번호") or "").strip()
            bid_ord = str(raw.get("bidNtceOrd") or r.get("차수") or "000").strip()
            key = f"{bid_no}-{bid_ord}" if bid_no else ""

            if key and key in history_keys:
                skipped_keys.append(key)
                continue

            filtered_rows.append(r)

        rows = filtered_rows
        log(f"[FILTER] history 기준 저장/발송 대상 제외: {before} -> {len(rows)}")
        if skipped_keys:
            log(
                "[FILTER][HISTORY-SKIP] "
                + ", ".join(skipped_keys[:20])
                + (" ..." if len(skipped_keys) > 20 else "")
            )

        if not rows:
            log("[FILTER] history 제외 후 남은 공고 없음.")
            if not args.no_send:
                save_last_run_ts(now_ts)
            else:
                log('[STATE] --no-send 이므로 last_run.txt 저장 생략')
            success = True
            return
        # -------------------------------------------------
        # 3-1) report 기준 중복 제거 
        # -------------------------------------------------
        report_keys = load_existing_report_keys()

        before = len(rows)
        rows = [
            r for r in rows
            if f"{str((r.get('원문') or {}).get('bidNtceNo') or r.get('공고번호')).strip()}-"
            f"{str((r.get('원문') or {}).get('bidNtceOrd') or r.get('차수') or '000').strip()}"
            not in report_keys
        ]

        log(f"[FILTER][REPORT-DEDUP] {before} -> {len(rows)} (removed={before-len(rows)})")   
        # -------------------------------------------------
        # 4) 참가가능지역 맵(확장용) + 저장물 생성
        # -------------------------------------------------
        prtcpt_map = {}
        try:
            prtcpt_map = _fetch_prtcpt_region_map_for_rows(rows)
        except Exception as e:
            log(f"[PRTCPT][ERR] 참가가능지역 조회 실패: {e}")



        # ============================================================





        save_raw_excel(rows, now_ts)
        save_split_excels(rows, prtcpt_map, now_ts)
        save_report_files(rows, now_ts)

        # -------------------------------------------------
        # 5) 발송 / 중복 방지
        # -------------------------------------------------
        new_history = []
        sent_keys = set()  # ✅ 같은 실행 내 key 중복 발송 방지
        send_cnt = 0
        skip_history = 0

        sent_in_run_keys = set()

        for row in rows:
            try:
                _fr_apply_final_rule(row, log_fn=log)
            except Exception as e:
                log(f"[FINAL_RULE][ERR][SEND] {e}")
            raw = row.get("원문") or {}

            bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "").strip()
            bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "000").strip()
            if not bid_no:
                continue

            key = f"{bid_no}-{bid_ord}"
            title = str(raw.get("bidNtceNm") or row.get("공고명") or "").strip()
            if key in sent_keys:
                log(f"[SEND][SKIP][DUP-IN-RUN] {key} / {title}")
                continue
            sent_keys.add(key)


            # --- ENFORCE allowed 대표지역 (ALWAYS, even if 수신번호 prefilled) ---

            try:

                _repX = (row.get("대표지역") or "").strip()

                # [PATCH] 모든 지역 허용

                # 발송단에서는 지역으로 재차단하지 않는다.

                pass

            except Exception as _e:

                try:

                    log(f"[WARN] ENFORCE-ALLOWED-REP failed: {_e}")

                except Exception:

                    pass

            # --- END ENFORCE allowed 대표지역 ---




            # --- FINAL: _force_norecv rows must NEVER be sent (before history) ---
            if str(row.get("_force_norecv") or "").strip() == "1":
                row["알림대상"] = "N"
                row["수신번호"] = ""
                log(f"[SEND][SKIP][FORCE_NORECV] {key} / {title}")
                continue

            # 실행 중 중복 방지
            if key in sent_in_run_keys:
                log(f"[SEND][SKIP][DUP-KEY-IN-RUN] {key} / {title}")
                continue

            if key in history_keys:
                skip_history += 1
                log(f"[SEND][SKIP][HISTORY] {key} / {title}")
                continue
                row["알림대상"] = "Y"
                row["수신번호"] = _force_recv
                log(f"[OVERRIDE] FORCE_RECV active -> bypass FORCE_NORECV: {_force_recv} key={key}")
            # --- END FORCE_RECV override ---


            # --- ENFORCE allowed 대표지역 (ALWAYS, even if 수신번호 prefilled) ---

            try:

                _repX = (row.get("대표지역") or "").strip()

                # [PATCH] 모든 지역 허용

                # 발송단에서는 지역으로 재차단하지 않는다.

                pass

            except Exception as _e:

                try:

                    log(f"[WARN] ENFORCE-ALLOWED-REP failed: {_e}")

                except Exception:

                    pass

            # --- END ENFORCE allowed 대표지역 ---




            # --- FINAL: _force_norecv rows must NEVER be sent (before history) ---
            if str(row.get("_force_norecv") or "").strip() == "1":
                row["알림대상"] = "N"
                row["수신번호"] = ""
                log(f"[SEND][SKIP][FORCE_NORECV] {key} / {title}")
                continue

            # 실행 중 중복 방지
            if key in sent_in_run_keys:
                log(f"[SEND][SKIP][DUP-KEY-IN-RUN] {key} / {title}")
                continue

            if key in history_keys:
                skip_history += 1
                log(f"[SEND][SKIP][HISTORY] {key} / {title}")
                continue

            # 수신번호가 비어있으면 규칙으로 자동 생성 (decide_receivers)
            if not (row.get("수신번호") or "").strip():
                auto_recv = decide_receivers(row) or []
                if auto_recv:
                    row["수신번호"] = ",".join(auto_recv)

            # --- DBG: recv source ---
            _has_recv_field = bool((row.get('수신번호') or '').strip())
            log("[DBG][RECV-SRC] %s rep=%r has_field=%s field=%r" % (key, (row.get('대표지역') or ''), _has_recv_field, (row.get('수신번호') or '')))
            recv_csv = (row.get("수신번호") or "").strip()
            recv_list = [x.strip() for x in recv_csv.split(",") if x.strip()]
            recv_list = list(dict.fromkeys(recv_list))  # 순서 유지 + 중복 제거
            # DUP CHECK (SAFE)
            bid_key = str(key or '').strip()
            recv_key = ','.join(sorted(recv_list))
            hash_key = f"{bid_key}|{recv_key}"
            if not hasattr(main, "_sent_hash"):
                main._sent_hash = set()
            if hash_key in main._sent_hash:
                log(f"[SEND][SKIP][DUP-IN-RUN] {bid_key} -> {recv_key}")
                continue
            main._sent_hash.add(hash_key)

            # --- FORCE: log per-row then skip early (before args.no_send path) ---

            if _get_force_suffix():

                try:

                    _rep_dbg = (row.get("대표지역") or "").strip() if isinstance(row, dict) else ""

                    # --- FORCE ROW debug (extended) ---
                    _raw_dbg = row.get('원문') or {}
                    _amt_dbg = (row.get('PresmptPrce') or _raw_dbg.get('PresmptPrce') or _raw_dbg.get('bdgtAmt') or row.get('bdgtAmt') or row.get('추정가격') or row.get('추정금액'))
                    _mt_dbg = str(_raw_dbg.get('sucsfbidMthdNm') or row.get('낙찰방법세부기준') or row.get('sucsfbidMthdNm') or '')
                    _mt2_dbg = _mt_dbg.replace(' ', '')
                    log("[SEND][SKIP][FORCE][ROW] %s / %s rep=%r recv=%s amt=%r mt2=%r" % (key, title, _rep_dbg, recv_list, _amt_dbg, _mt2_dbg[:120]))

                except Exception:

                    pass

                continue

            # --- END FORCE ROW SKIP ---

            
            if not recv_list:
                # 기본: 수신자 없으면 SKIP
                # 필요할 때만 강제발송: FORCE_ON_NORECV=1
                force_on_norecv = (os.environ.get('FORCE_ON_NORECV','').strip().lower() in ('1','y','yes','true'))
                if force_on_norecv:
                    recv_list = ['REDACTED_PRIVATE_VALUE']  # FORCE_ON_NORECV
                    log('[SEND][FORCE][NORECV] {} / {}'.format(key, title))
                else:
                    log('[SEND][SKIP][NORECV] {} / {}'.format(key, title))
                    continue

            fields = build_tb0485_fields(row)

            if args.no_send:

                log(f"[SAFE] DRY RUN TB0485: key={key}, receivers={recv_list}")

                continue



            ok_any = False
            ok_phones = []



            # ============================================================

            # __FINAL_GUARD_BEFORE_SEND__
            # --- FORCE MODE (B-option): log and block BEFORE FINAL_GUARD ---
            if _get_force_suffix():
                try:
                    log('[SEND][SKIP][FORCE][BEFORE_FINAL_GUARD] %s / %s rep=%r recv=%s' % (key, title, rep, recv_list))
                except Exception:
                    pass
                continue

            # === FINAL_GUARD (clean) ===
            try:
                _base = recv_list if isinstance(recv_list, list) else []
                _rep = (row.get('대표지역') or '').strip() if isinstance(row, dict) else ''
                _allowed = {'전국','세종','충북','대구','경북'}
                if _rep and _rep not in _allowed:
                    recv_list = []
                else:
                    recv_list = list(dict.fromkeys(_base))
            except Exception as e:
                log(f'[WARN] FINAL_GUARD failed: {e}')


            # [PATCH] FINAL_GUARD 직전 수신번호 복원

            # 앞단/중간단에서 이미 계산된 row["수신번호"]가 있으면 그 값을 최우선으로 존중한다.

            if not recv_list:

                _recv_csv_guard = (row.get("수신번호") or "").strip()

                _recv_guard = [x.strip() for x in _recv_csv_guard.split(",") if x.strip()]

                _recv_guard = list(dict.fromkeys(_recv_guard))

                if _recv_guard:

                    recv_list = _recv_guard

                    try:

                        log(f"[PATCH][FINAL_GUARD][RESTORE-RECV] {key} rep={_repX!r} recv={recv_list}")

                    except Exception:

                        pass



            # --- FINAL_GUARD: no receivers -> SKIP (not FAIL) ---
            if not recv_list:
                _rep_dbg = (row.get("대표지역") or "").strip() if isinstance(row, dict) else ""
                log(f"[SEND][SKIP][FINAL_GUARD] {key} / {title} rep={_repX!r}")
                continue
            # --- END FINAL_GUARD SKIP ---
            for phone in recv_list:
                try:
                    # --- FORCE MODE: block actual sending (B-option) ---
                    if _get_force_suffix():
                        try:
                            log('[SEND][SKIP][FORCE] %s / %s -> %s' % (key, title, phone))
                        except Exception:
                            pass
                        ok = False
                        continue
                    # --- END FORCE MODE ---
                    res = send_tb0485_retry_and_log(
                        phone=phone,
                        fields=fields,
                        key=key,
                        title=title,
                        max_retry=3,
                    )
                    ok = bool(isinstance(res, dict) and res.get("sent") is True)
                except Exception as e:
                    ok = False
                    log(f"[SEND][ERR] {key} -> {phone}: {e}")

                if ok:
                    ok_any = True
                    if not (isinstance(res, dict) and res.get('blocked') is True):
                        ok_phones.append(phone)

                    send_cnt += 1
                    if 'SMOKE_MAX_SEND' in globals() and SMOKE_MAX_SEND and send_cnt >= SMOKE_MAX_SEND:
                        log(f"[SMOKE] send_cnt={send_cnt} 도달 → 스모크 테스트 종료")
                        save_last_run_ts(now_ts) if ((not args.no_send) and (not _get_force_suffix())) else None
                        success = True
                        return

            if ok_any:
                history_keys.add(key)
                new_history.append(
                    {
                        "bid_no": bid_no,
                        "bid_ord": bid_ord,
                        "sent_date": now.strftime("%Y%m%d"),
                        "sent_ts": now_ts,
                    }
                )
                sent_in_run_keys.add(key)
                log(f"[SEND][OK] {key} / {title} -> {ok_phones}")
            else:
                log(f"[SEND][FAIL] {key} / {title} -> {recv_list}")

        if (not args.no_send) and new_history and (not _get_force_suffix()):
            save_send_history(history_rows + new_history)
        elif (not args.no_send) and new_history and _get_force_suffix():
            log('[HISTORY] FORCE mode -> send_history.csv 저장 생략')

        log(
            f"[SEND] 성공(수신자 기준)={send_cnt}, "
            f"history 신규={len(new_history)}, "
            f"history로 skip={skip_history}"
        )

        # -------------------------------------------------
        # 6) 상태 저장
        # -------------------------------------------------
        if not args.no_send:
            if not _get_force_suffix():
                save_last_run_ts(now_ts)
            else:
                log('[STATE] FORCE mode -> last_run.txt 저장 생략')
        else:
            log('[STATE] --no-send 이므로 last_run.txt 저장 생략')
        success = True

    except Exception as e:
        log(f"[FATAL] main() exception: {e}")
        log(traceback.format_exc())

    finally:
        if (isinstance(lock_fd, int) and not isinstance(lock_fd, bool) and lock_fd >= 0):
            try:
                os.close(lock_fd)
            except Exception:
                pass
        log(f"[MAIN] === main_send.py END (success={success}) ===")






# ================================

# ENVIRONMENT GUARD (PROD / TEST)

# ================================

import os

import sys

from pathlib import Path as _Path



def _fatal(msg):

    print(f"[FATAL][ENV] {msg}", file=sys.stderr)

    sys.exit(2)



def env_guard():

    env = os.getenv("N_DATA_ENV", "").upper().strip()

    cwd = _Path.cwd().resolve()

    nas = (os.getenv("N_DATA_BASE", "") or "").strip()



    EXPECT = {

        "PROD": {"cwd": _Path("/home/pi/n_data"),      "nas": "/mnt/vol1/bid/n_data"},

        "TEST": {"cwd": _Path("/home/pi/n_data_test"), "nas": "/mnt/vol1/bid/n_data_test"},

    }



    if env not in EXPECT:

        _fatal(f"N_DATA_ENV not set or invalid: '{env}' (use PROD or TEST)")



    exp = EXPECT[env]

    if cwd != exp["cwd"]:

        _fatal(f"CWD mismatch: now={cwd} expected={exp['cwd']}")



    if nas != exp["nas"]:

        _fatal(f"N_DATA_BASE mismatch: now='{nas}' expected='{exp['nas']}'")



    print(f"[ENV] OK: {env} cwd={cwd} nas={nas}")



# 실행 즉시 가드







# ================================

# SAFE ENRICH WRAPPER (sucs method)

# ================================

def _safe_enrich_sucs(api_key, api_rows, start_dt, end_dt):

    """

    Safe wrapper for enrich_cnstwk_sucs_method.



    핵심 정책:

      - enrich 함수가 in-place로 값을 주입하고, 반환은 None/[] 등으로 올 수 있음

      - 그러므로 반환값을 신뢰하지 않고, 항상 원본 api_rows를 유지한다.

      - 실패해도 절대 raise 하지 않는다.



    Returns:

        (api_rows, injected_bool)

    """

    injected = False

    try:

        fn = globals().get("enrich_cnstwk_sucs_method")

        if not callable(fn):

            return api_rows, False



        # best-effort signature matching (반환값은 무시)

        try:

            fn(api_key, api_rows, start_dt, end_dt)

        except TypeError:

            try:

                fn(api_key, api_rows, start_dt)

            except TypeError:

                fn(api_key, api_rows)



        injected = True

        return api_rows, injected



    except Exception as e:

        try:

            log(f"[NARA][WARN] enrich_cnstwk_sucs_method 실패: {e}")

        except Exception:

            pass

        return api_rows, False

        # Try flexible signatures

        try:

            rows2 = fn(api_key, api_rows, start_dt, end_dt)

        except TypeError:

            try:

                rows2 = fn(api_key, api_rows, start_dt)

            except TypeError:

                rows2 = fn(api_key, api_rows)



        if rows2 is not None and rows2 is not api_rows:

            injected = True



        return (rows2 if rows2 is not None else api_rows), injected



    except Exception as e:

        try:

            log(f"[NARA][WARN] enrich_cnstwk_sucs_method 실패: {e}")

        except Exception:

            pass

        return api_rows, False



# ================================
# ENTRYPOINT
# ================================
def load_existing_report_keys():

    keys = set()

    try:

        files = sorted(REPORT_DIR.glob("입찰리포트_*.xlsx"), reverse=True)

        if not files:

            return keys



        latest = files[0]

        log(f"[DEDUP][REPORT] 기준파일: {latest}")



        df = pd.read_excel(latest)



        for _, r in df.iterrows():

            bid_no = str(r.get("공고번호") or "").strip()

            bid_ord = str(r.get("차수") or "000").strip()

            if bid_no:

                keys.add(f"{bid_no}-{bid_ord}")



    except Exception as e:

        log(f"[DEDUP][REPORT][ERR] {e}")



    return keys

if __name__ == '__main__':
    env_guard()
    main()



# =============================================================================




# =============================================================================

# [TB0485 수신자 Override 운영 규칙]

#

# 적용 공종

#   - 0038 : 소방기계

#   - 0039 : 소방전기

#   - 0040 : 전문소방

#   - 6202 : 기계설비

#

# 공종 0038/0039/0040/6202

#   전국 → REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

#   세종 → REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

#   충북 → REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

#   대구 → REDACTED_PRIVATE_VALUE

#   경북 → REDACTED_PRIVATE_VALUE

#

# 공종 0037 (전기공사) 예외

#   전국 → REDACTED_PRIVATE_VALUE,REDACTED_PRIVATE_VALUE

#

# 그 외 지역

#   → override 하지 않음 (기존 receivers 유지)

#

# TEST 모드

#   N_DATA_ENV=TEST && N_DATA_RULE_MODE!=PROD

#   → 항상 REDACTED_PRIVATE_VALUE 단일 수신

# =============================================================================











