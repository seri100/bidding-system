
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import requests
import pandas as pd
import pymysql
from urllib.parse import unquote
import csv
# ===========================
# 실행 중복 방지용 파일 락
# (cron, systemd 어디서 실행하든 공통 적용)
# ===========================
import fcntl

LOCK_FILE = "/run/lock/seri-main-send.lock"

def acquire_lock():
    """
    /run/lock/seri-main-send.lock 에 대한 비차단(LOCK_NB) 락.
    이미 다른 main_send 가 잡고 있으면 None 을 리턴하고, 이번 프로세스는 종료.
    """
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o644)
        # 이미 잡힌 락이 있으면 BlockingIOError 발생
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # PID 를 파일에 적어두면 디버깅할 때 편함
        try:
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
        except Exception:
            pass
        return fd
    except BlockingIOError:
        # 다른 인스턴스가 이미 실행 중
        try:
            log("[LOCK] another main_send instance is running; exit.")
        except Exception:
            print("[LOCK] another main_send instance is running; exit.")
        return None
    except Exception as e:
        # 락이 안 걸려도 최악의 경우 그냥 진행 (원하면 여기서도 종료 가능)
        try:
            log(f"[LOCK][WARN] failed to acquire lock: {e}")
        except Exception:
            print(f"[LOCK][WARN] failed to acquire lock: {e}")
        return None

# =========================
# 알림톡 발송 CSV 로그
# =========================
import csv
from pathlib import Path
from datetime import datetime

# CSV 로그 저장 위치
SENDLOG_DIR = Path("/mnt/vol1/n_data")
SENDLOG_DIR.mkdir(parents=True, exist_ok=True)
SENDLOG_PATH = SENDLOG_DIR / "alimtalk_sendlog.csv"


def append_send_log(
    bid_no: str,
    bid_ord: str,
    bid_name: str,
    ind_code: str,
    region: str,
    phone: str,
    status: str,
    detail: str = "",
):
    """
    알림톡 발송 이력을 CSV 파일로 남김.

    - status: "OK", "FAIL", "SKIP_RULE", "DEDUP", "NO_RECV", "DRY" 등
    - detail: 에러 메시지나 스킵 사유 등 자유 텍스트
    """
    try:
        is_new = not SENDLOG_PATH.exists()
        with SENDLOG_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(
                    [
                        "ts",          # 로그 시간
                        "bid_no",      # 공고번호
                        "bid_ord",     # 차수
                        "bid_name",    # 공고명
                        "ind_code",    # 공종코드
                        "region",      # 지역(필요 시)
                        "phone",       # 수신번호
                        "status",      # OK / FAIL / SKIP_RULE / DEDUP / NO_RECV / DRY ...
                        "detail",      # 에러/사유
                    ]
                )
            writer.writerow(
                [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    bid_no or "",
                    bid_ord or "",
                    bid_name or "",
                    ind_code or "",
                    region or "",
                    phone or "",
                    status,
                    detail or "",
                ]
            )
    except Exception as e:
        # CSV 기록 실패는 서비스 죽이면 안 됨
        try:
            print(f"[WARN] append_send_log error: {e}")
        except Exception:
            pass



# --------------------
# API 호출용 안전 래퍼 (타임아웃 + 재시도)
# --------------------

from requests.exceptions import RequestException



def safe_get(url, params=None, timeout=30, max_retries=3, sleep_sec=3):

    """

    외부 API 호출용 래퍼

    - timeout: 초 (기본 30초)

    - max_retries: 최대 재시도 횟수

    """

    last_err = None

    for i in range(1, max_retries + 1):

        try:

            resp = requests.get(url, params=params, timeout=timeout)

            resp.raise_for_status()

            return resp

        except RequestException as e:

            last_err = e

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # main_send 로그 포맷 맞춰서 출력

            print(f"[{now}] [ERR] safe_get try={i}/{max_retries} url={url} err={e}")

            sys.stdout.flush()

            if i < max_retries:

                time.sleep(sleep_sec)

    # 여기까지 오면 계속 실패

    raise last_err


# -----------------------------
# Alligo 모듈 (같은 폴더의 alligo.py)
# -----------------------------

try:

    from alligo import Alligo

except ImportError:

    Alligo = None

# 테스트용: 한 번호만 보내는 모드 (기본 OFF)
#KAKAO_SINGLE_MODE=1 이면 “테스트 모드: 한 번호만 발송”
#KAKAO_SINGLE_PHONE은 기본값이 REDACTED_PRIVATE_VALUE (원하시면 나중에 env로 바꿀 수 있게 해둔 것)
TEST_SINGLE_MODE = os.getenv("KAKAO_SINGLE_MODE", "0") == "1"
TEST_SINGLE_PHONE = os.getenv("KAKAO_SINGLE_PHONE", "REDACTED_PRIVATE_VALUE")

# -----------------------------
# DB 설정
# -----------------------------

DB_CONFIG = {

    "host": "REDACTED_PRIVATE_VALUE",

    "user": 'REDACTED_PRIVATE_VALUE',

    "password": 'REDACTED_PRIVATE_VALUE',

    "db": "kakao",

    "charset": "utf8",

    "cursorclass": pymysql.cursors.DictCursor,

    "autocommit": True,

}

def get_db_conn():

    return pymysql.connect(**DB_CONFIG)

# -----------------------------
# 환경 / 상수
# -----------------------------
SERVICE_KEY_ENV = os.getenv("SERVICE_KEY")
KEY_PATH = "/home/pi/n_data/bid_api_key.txt"
API_BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"

# 대상 업종 (원래 사용하던 값 유지)

TARGET_INDS = ["6202", "0040", "0037", "0038", "0039"]
OUTDIR = Path("/mnt/vol1/n_data")
OUTDIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_CODE = os.getenv("ALLIGO_TPL_CODE", "TB_0485")
SENDER_NUM = os.getenv("ALLIGO_SENDER", "REDACTED_PRIVATE_VALUE")
# 표준 폴더 구조
NDATA_BASE   = OUTDIR              # = /mnt/vol1/n_data
DIR_RAW      = NDATA_BASE / "raw"      # 원본 통합 엑셀
DIR_SPLIT    = NDATA_BASE / "split"    # 지역/공종 분할 엑셀
DIR_REPORT   = NDATA_BASE / "report"   # 리포트(HTML/XLSX)
DIR_LOG      = NDATA_BASE / "logs"     # 로그 공용
DIR_LOG_KAKAO = DIR_LOG / "kakao"      # 알림톡 발송 로그
DIR_LOG_MAIN  = DIR_LOG / "main_send"  # main_send 자체 로그 (필요 시 사용)

for d in [NDATA_BASE, DIR_RAW, DIR_SPLIT, DIR_REPORT, DIR_LOG, DIR_LOG_KAKAO, DIR_LOG_MAIN]:
    d.mkdir(parents=True, exist_ok=True)

# 보존 기간(일 단위) - 필요하면 값만 나중에 조정
RETENTION_RAW_DAYS    = 90    # RAW 통합 엑셀
RETENTION_SPLIT_DAYS  = 60    # 분할 엑셀
RETENTION_REPORT_DAYS = 180   # 리포트(HTML/XLSX)
RETENTION_LOG_DAYS    = 365   # 로그
# -----------------------------------
# 템플릿 자동 매핑 (업종/지역별 확장용)
# -----------------------------------
# 예시:
#  - 6202(기계설비): 기본 템플릿 TB_0485
#  - 0040(소방), 0038(전기), 0039(정보통신) 등은
#    나중에 별도 템플릿을 만들면 아래에 매핑만 추가하면 됨.
TEMPLATE_MAP_BY_IND = {
    # "6202": "TB_0485",   # 기계설비
    # "0040": "TB_0040",   # 소방 (예시)
    # "0038": "TB_0038",   # 전기 (예시)
    # "0039": "TB_0039",   # 정보통신 (예시)
}

def choose_template(row) -> str:
    """
    공고 1건(row)에 대해 사용할 템플릿 코드를 결정.

    1순위: 업종코드 기반 매핑(TEMPLATE_MAP_BY_IND)
    2순위: 기본값 TEMPLATE_CODE

    나중에 지역, 금액대, 발주기관까지 보고 싶으면
    이 함수 안에서 조건만 추가하면 됨.
    """
    ind = str(row.get("공고업종코드") or "").strip()
    tpl = TEMPLATE_MAP_BY_IND.get(ind)
    if tpl:
        return tpl

    # TODO: 필요하면 여기서 지역/금액대별 분기 추가
    # tags = extract_region_tags(row)
    # est_str, est_val, _ = parse_estimate_and_joint(row)
    # if "대구" in tags and ind == "6202": return "TB_6202_DG"  # 예시

    return TEMPLATE_CODE


# 금액 필터: 0이면 사용 안 함

MIN_ESTIMATE_FOR_TARGET = 0
REQUIRE_JOINT_RATE = False

# -----------------------------
# 유틸
# -----------------------------

def log(msg: str):

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{ts}] {msg}", flush=True)

def _norm(x):

    if isinstance(x, list):

        return " ".join(_norm(v) for v in x)

    if isinstance(x, dict):

        return " ".join(_norm(v) for v in x.values())

    if x is None:

        return ""

    return str(x).strip()

def clamp_len(s, n=80):

    s = _norm(s)

    return s if len(s) <= n else s[: n - 1] + "..."

# 엑셀에서 허용하지 않는 제어문자 제거용

_ILLEGAL_EXCEL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def sanitize_for_excel(value):

    """openpyxl이 싫어하는 제어문자를 제거한다."""

    if not isinstance(value, str):

        return value

    return _ILLEGAL_EXCEL_CHARS.sub("", value)

def get_service_key():

    key = None

    if SERVICE_KEY_ENV:

        key = SERVICE_KEY_ENV.strip()

    else:

        try:

            key = Path(KEY_PATH).read_text(encoding="utf-8").strip()

        except Exception:

            log(f"[ERR] API key file not found: {KEY_PATH}")

            return ""

    if "%" in key:

        try:

            key = unquote(key)

        except Exception as e:

            log(f"[WARN] unquote SERVICE_KEY failed: {e}")


    return key

# -----------------------------
# DB 테이블 정의
# -----------------------------

def ensure_tables():

    sql_ntce = """

    CREATE TABLE IF NOT EXISTS ntcedata (

      bid_no      varchar(40) NOT NULL,

      bid_ord     varchar(8)  NOT NULL DEFAULT '000',

      ind         varchar(10) DEFAULT NULL,

      ind_nm      varchar(50) DEFAULT NULL,

      title       varchar(255) DEFAULT NULL,

      region_text text,

      raw_json    json DEFAULT NULL,

      created_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,

      PRIMARY KEY (bid_no, bid_ord)

    ) CHARSET=utf8mb4;

    """

    sql_sendlog = """

    CREATE TABLE IF NOT EXISTS sendlog (

      bid_no   varchar(40) NOT NULL,

      bid_ord  varchar(8)  NOT NULL DEFAULT '000',

      receiver varchar(20) NOT NULL,

      tpl      varchar(32) NOT NULL DEFAULT 'TB_0485',

      sent_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,

      PRIMARY KEY (bid_no, bid_ord, receiver, tpl)

    ) CHARSET=utf8mb4;

    """

    sql_recv = """

    CREATE TABLE IF NOT EXISTS recvdata (

      bidNtceCode varchar(40) NOT NULL,

      bidNtceOrd  varchar(8)  NOT NULL DEFAULT '000',

      recvPhone   varchar(20) DEFAULT NULL,

      receivers   text,

      sent_at     timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,

      PRIMARY KEY (bidNtceCode, bidNtceOrd)

    ) CHARSET=utf8mb4;

    """

    cn = get_db_conn()

    try:

        with cn.cursor() as c:

            c.execute(sql_ntce)

            c.execute(sql_sendlog)

            c.execute(sql_recv)

    finally:

        cn.close()


def already_sent(bid_no, bid_ord, phone, tpl):

    cn = get_db_conn()

    try:

        with cn.cursor() as c:

            sql = """SELECT 1 FROM sendlog

                     WHERE bid_no=%s AND bid_ord=%s AND receiver=%s AND tpl=%s LIMIT 1"""

            c.execute(sql, (bid_no, bid_ord, phone, tpl))

            return bool(c.fetchone())

    finally:

        cn.close()


def mark_sent(bid_no, bid_ord, phone, tpl):

    cn = get_db_conn()

    try:

        with cn.cursor() as c:

            sql = """INSERT IGNORE INTO sendlog (bid_no, bid_ord, receiver, tpl)

                     VALUES (%s, %s, %s, %s)"""

            c.execute(sql, (bid_no, bid_ord, phone, tpl))

    finally:

        cn.close()



def recv_upsert_db(conn, bid_no, bid_ord, receivers):

    main_phone = receivers[0] if receivers else ""

    recv_str = ",".join(receivers)



    sql = """

    INSERT INTO recvdata (bidNtceCode, bidNtceOrd, recvPhone, sent_at, receivers)

    VALUES (%s, %s, %s, NOW(), %s)

    ON DUPLICATE KEY UPDATE

        recvPhone=VALUES(recvPhone),

        sent_at=VALUES(sent_at),

        receivers=VALUES(receivers)

    """

    with conn.cursor() as c:

        c.execute(sql, (bid_no, bid_ord, main_phone, recv_str))

def upsert_ntcedata(conn, row):

    bid_no = str(row.get("공고번호") or "").strip()

    bid_ord = str(row.get("차수") or "000").strip()

    ind = str(row.get("공고업종코드") or "")

    title = _norm(row.get("공고명"))

    region = _norm(row.get("공동도급지역") or row.get("수요지역"))

    raw = row.get("원문") or {}

    sql = """

    INSERT INTO ntcedata (bid_no, bid_ord, ind, ind_nm, title, region_text, raw_json)

    VALUES (%s, %s, %s, NULL, %s, %s, %s)

    ON DUPLICATE KEY UPDATE

        ind=VALUES(ind),

        title=VALUES(title),

        region_text=VALUES(region_text),

        raw_json=VALUES(raw_json)

    """

    try:

        with conn.cursor() as c:

            c.execute(sql, (bid_no, bid_ord, ind, title, region, json.dumps(raw, ensure_ascii=False)))

    except Exception as e:

        log(f"[NTCEDB][ERR] {bid_no}/{bid_ord}: {e}")

# -----------------------------
# 백업
# -----------------------------

def backup_old_excels(base_dir=OUTDIR, keep_days=1):

    try:

        today = datetime.now().date()

        cutoff = today - timedelta(days=keep_days)



        backup_root = base_dir / "backup"

        backup_root.mkdir(exist_ok=True)



        for f in base_dir.glob("*.xlsx"):

            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()

            if mtime <= cutoff:

                dstdir = backup_root / mtime.strftime("%Y%m%d")

                dstdir.mkdir(parents=True, exist_ok=True)

                dst = dstdir / f.name

                log(f"[BACKUP] move {f} -> {dst}")

                f.replace(dst)

    except Exception as e:

        log(f"[WARN] backup_old_excels: {e}")

# -----------------------------
# API fetch (모든 페이지 수집)
# -----------------------------
def fetch_ind(ind, bgn_dt, end_dt, retries=3, timeout=15):
    key = get_service_key()
    if not key:
        log("[ERR] SERVICE_KEY missing")
        return []

    num = 999  # 한 페이지 최대 999행
    all_rows = []
    page = 1

    while True:
        params = {
            "serviceKey": key,
            "type": "json",
            "numOfRows": num,
            "pageNo": page,
            "inqryDiv": 1,
            "inqryBgnDt": bgn_dt,
            "inqryEndDt": end_dt,
            "indstrytyCd": ind,
        }

        tries = 0
        while True:
            tries += 1
            try:
                r = safe_get(API_BASE, params=params, timeout=timeout)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                if tries >= retries:
                    log(f"[ERR] fetch_ind {ind} page={page}: {e}")
                    return all_rows
                time.sleep(1.0 * tries)

        response = data.get("response", {})
        body = response.get("body", {})
        items = body.get("items")

        if items is None:
            rows = []
        elif isinstance(items, dict):
            rows = [items]
        else:
            rows = items

        out = []
        for it in rows:
            row = {
                "공고업종코드": _norm(ind),
                "공고번호": _norm(it.get("bidNtceNo")),
                "차수": _norm(it.get("bidNtceOrd")),
                "공고명": _norm(it.get("bidNtceNm")),
                "입찰마감일시": _norm(it.get("bidClseDt")),
                "공동도급지역": _norm(it.get("prtcptLmtRgnNm")),   # 참가제한/공동도급지역
                "수요지역": _norm(it.get("dmndInsttLocplcNm")),     # 수요기관 지역
                "원문": it,
            }
            out.append(row)

        log(f"[HTTP] ind={ind} page={page} count={len(out)}")
        all_rows.extend(out)

        # 마지막 페이지면 종료
        if len(out) < num:
            break

        page += 1

    log(f"[HTTP] ind={ind} total={len(all_rows)}")
    return all_rows

# -----------------------------

# 1차 필터 (업종 필터)

# -----------------------------

def filter_rows(rows):

    filtered = [r for r in rows if (r.get("공고업종코드") in TARGET_INDS)]

    log(f"[FILTER] {len(filtered)} rows")

    return filtered

# -----------------------------
# 지역 태그 / 대상 판정 / 수신번호 로직
# -----------------------------

def normalize_region(name):

    """API 지역 문자열 → 내부 지역 태그 변환"""

    if not name:

        return None

    s = str(name)

    if "전국" in s or "대한민국" in s:

        return "전국"

    if "충북" in s or "충청북도" in s:

        return "충북"

    if "세종" in s:

        return "세종"

    if "경북" in s or "경상북도" in s:

        return "경북"

    if "대구" in s:

        return "대구"

    if "강원" in s or "강원특별자치도" in s:

        return "강원"

    return None

def extract_region_tags(row):

    """

    지역 태그 추출 + 전국공고 판정 규칙 반영

    규칙 요약:

      1) 문자열 안에 '전국' / '대한민국'이 있으면 전국

      2) jntcontrctDutyRgnNm1(지역의무공동도급 지역) + rgnDutyJntcontrctRt(의무지분율) 이 있으면

         → 의무지분 있는 공동이행/분담이행 전국공고로 보고 '전국' 태그 추가

      3) 지역의무공동도급이 아니고, 참가제한/공동도급지역이 없고, 시공지역 정보도 없으면

         → 지역제한 없음 = 전국공고로 보고 '전국' 태그 추가

         (수요지역은 단순 위치이므로 제한으로 보지 않음)

    """

    tags = set()

    # 1차: 기본 필드에서 지역 태그 추출

    t1 = normalize_region(_norm(row.get("공동도급지역")))

    # 수요지역은 제한이 아니라 참고라서 태그는 안 뽑아도 됨(원하면 아래 주석 해제)

    # t2 = normalize_region(_norm(row.get("수요지역")))

    if t1:

        tags.add(t1)

    raw = row.get("원문") or {}

    t3 = normalize_region(_norm(raw.get("cnstrtsiteRgnNm")))   # 시공지역

    t4 = normalize_region(_norm(raw.get("jntcontrctDutyRgnNm1")))  # 의무공동도급 지역

    if t3:

        tags.add(t3)

    if t4:

        tags.add(t4)

    # 2차: 지역의무공동도급(공동/분담) → 전국공고 처리

    jnt_region = _norm(raw.get("jntcontrctDutyRgnNm1"))

    jnt_rate_str = _norm(raw.get("rgnDutyJntcontrctRt"))

    try:

        jnt_rate = float(jnt_rate_str) if jnt_rate_str else None

    except:

        jnt_rate = None

    if jnt_region and jnt_rate is not None:

        # 의무지분율이 있으면 전국공고로 간주

        tags.add("전국")

        jr = normalize_region(jnt_region)

        if jr:

            tags.add(jr)

    # 3차: 지역의무공동도급 아니고, 참가제한/공동도급/시공지역이 모두 없으면 전국공고

    has_prtcpt = bool(_norm(row.get("공동도급지역")))             # 참가제한/공동도급지역

    has_cnstr = bool(_norm(raw.get("cnstrtsiteRgnNm")))          # 시공지역

    has_jnt = bool(jnt_region)                                   # 의무공동도급 지역

    # 수요지역은 has_demand로 잡지 않는다 (제한 아님)

    if not tags and not (has_prtcpt or has_cnstr or has_jnt):

        tags.add("전국")

    return tags

def parse_estimate_and_joint(row):

    raw = row.get("원문") or {}

    est_str = _norm(raw.get("presmptPrce"))

    jnt_str = _norm(raw.get("rgnDutyJntcontrctRt"))

    try:

        est_val = int(est_str) if est_str else 0

    except:

        est_val = 0

    return est_str, est_val, jnt_str

def get_skip_reason(row):

    ind = str(row.get("공고업종코드") or "")

    special = {"0038", "0039", "0040", "6202"}

    if ind not in special:

        return "업종제외"

    tags = extract_region_tags(row)

    if not tags:

        return "지역태그없음"

    target_tags = {"전국", "충북", "세종", "경북", "대구", "강원"}

    if not (tags & target_tags):

        return "지역제외"

    est_str, est_val, jnt_str = parse_estimate_and_joint(row)

    if MIN_ESTIMATE_FOR_TARGET and est_val < MIN_ESTIMATE_FOR_TARGET:

        return "금액미달"

    return ""

def is_target_row(row):

    ind = str(row.get("공고업종코드") or "")

    special = {"0038", "0039", "0040", "6202"}

    if ind not in special:

        return False

    tags = extract_region_tags(row)

    if not tags:

        return False

    # 강원 단독 제외

    if tags == {"강원"}:

        return False

    target_tags = {"전국", "충북", "세종", "경북", "대구"}

    if not (tags & target_tags):

        return False

    est_str, est_val, jnt_str = parse_estimate_and_joint(row)

    if MIN_ESTIMATE_FOR_TARGET and est_val < MIN_ESTIMATE_FOR_TARGET:

        return False

    return True
def decide_receivers(row):
    """
    지역 태그에 따라 수신번호 분배

    - 전국: 4명
      REDACTED_PHONE, REDACTED_PHONE, 010-5464-33560, REDACTED_PHONE
    - 충북: 2명
      REDACTED_PHONE, REDACTED_PHONE
    - 세종: 2명
      010-5464-33560, REDACTED_PHONE
    - 경북/대구: 1명
      REDACTED_PHONE
    - 강원 단독: 제외 (is_target_row에서 이미 필터)
    """
    ind = str(row.get("공고업종코드") or "")
    # 타깃 업종만 발송
    if ind not in {"0038", "0039", "0040", "6202"}:
        return []

    tags = extract_region_tags(row)
    phones = set()

    # 전국이면 4명
    if "전국" in tags:
        phones.update([
            "REDACTED_PRIVATE_VALUE",  # 충북
            "REDACTED_PRIVATE_VALUE",  # 충북 서브
            "REDACTED_PRIVATE_VALUE",  # 세종
            "REDACTED_PRIVATE_VALUE",  # 대구/경북
        ])
    else:

        # 강원 단독은 상위 is_target_row에서 필터하지만, 안전하게 한 번 더 제외
        if tags == {"강원"}:
            return []

        # 지역별 규칙
        if "충북" in tags:
            phones.update(["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"])
        if "세종" in tags:
            phones.update(["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"])
        if "경북" in tags or "대구" in tags:
            phones.add("REDACTED_PRIVATE_VALUE")
   
    # 여기서 최종 리스트 정리
    phones_list = sorted(phones)
    if not phones_list:
        return []
    # 테스트 모드: 한 번호만 강제로 사용   
    if TEST_SINGLE_MODE:
        # TEST_SINGLE_PHONE이 기존 리스트에 없더라도, 무조건 이 번호만 사용
        return [TEST_SINGLE_PHONE]
    # 일반 모드: 기존 로직 그대로 여러 번호 발송    
    return phones_list

# -----------------------------
# 엑셀 저장 (통합 + 지역/공종별 추가 저장)
# -----------------------------
def save_excel(rows):
    if not rows:
        return None

    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    main_path = OUTDIR / f"입찰공고_{now_str}.xlsx"

    def conv(r):
        raw = r.get("원문") or {}

        # 공동도급지역 표시값
        region_display = _norm(r.get("공동도급지역"))
        if not region_display:
            region_display = _norm(raw.get("jntcontrctDutyRgnNm1"))
            if not region_display:
                region_display = _norm(raw.get("cnstrtsiteRgnNm"))

        # 추정금액 / 공동도급비율
        est_str, est_val, jnt_str = parse_estimate_and_joint(r)

        # 게시일시
        bid_notice_dt = _norm(raw.get("bidNtceDt"))

        # 1) 기본 컬럼
        base = {
            "공고업종코드": r.get("공고업종코드", ""),
            "공고번호": r.get("공고번호", ""),
            "차수": r.get("차수", ""),
            "공고명": r.get("공고명", ""),
            "입찰마감일시": r.get("입찰마감일시", ""),
            "공동도급지역": region_display,
            "수요지역": r.get("수요지역", ""),
            "게시일시": bid_notice_dt,
        }

        # 2) 지역 태그 / 대상 여부 / SKIP 이유 / 수신번호
        tags = extract_region_tags(r)
        tags_str = ",".join(sorted(tags)) if tags else ""
        skip_reason = get_skip_reason(r)

        if is_target_row(r):
            base["알림대상"] = "Y"
            base["SKIP이유"] = ""
            recv_list = decide_receivers(r)
            base["지역태그"] = tags_str
            base["수신번호"] = ",".join(recv_list)
        else:
            base["알림대상"] = "N"
            base["SKIP이유"] = skip_reason
            base["지역태그"] = tags_str
            base["수신번호"] = ""

        # 3) 금액 / 공동도급비율 / 원문
        base["추정금액"] = est_str
        base["추정금액_원"] = est_val
        base["공동도급비율"] = jnt_str
        base["원문"] = json.dumps(raw, ensure_ascii=False)

        # 엑셀 제어문자 제거
        for k, v in list(base.items()):
            base[k] = sanitize_for_excel(v)

        return base

    df = pd.DataFrame([conv(r) for r in rows])

    # 컬럼 순서를 강제로 맞춤
    cols_order = [
        "공고업종코드", "공고번호", "차수", "공고명",
        "입찰마감일시", "공동도급지역", "수요지역", "게시일시",
        "알림대상", "SKIP이유", "지역태그", "수신번호",
        "추정금액", "추정금액_원", "공동도급비율", "원문",
    ]
    df = df.reindex(columns=cols_order)

    # 1) 통합 파일 저장
    df.to_excel(main_path, index=False)
    log(f"[SAVE] {main_path}")

    # 2) 지역·공종별 추가 저장
    #    - 지역태그: '전국,충북' 이런 식이면 첫 번째 태그만 파일명에 사용
    #    - 공고업종코드: 6202, 0040, 0038, 0039 등
    if "지역태그" in df.columns and "공고업종코드" in df.columns:
        grouped = df.groupby(["지역태그", "공고업종코드"], dropna=False)

        for (tag_str, ind_code), g in grouped:
            # 지역태그가 비어 있으면 굳이 분리 저장 안 함
            if not isinstance(tag_str, str) or not tag_str.strip():
                continue

            # '전국,충북' 같이 여러 개면 첫 번째만 사용
            first_tag = tag_str.split(",")[0].strip() or "미지정지역"

            # 파일명에 쓸 수 있도록 정리
            safe_region = re.sub(r"[^0-9A-Za-z가-힣]+", "_", first_tag).strip("_") or "미지정지역"
            safe_ind = re.sub(r"[^0-9A-Za-z]+", "_", str(ind_code)).strip("_") or "미지정업종"

            split_name = f"입찰공고_{safe_region}_{safe_ind}_{now_str}.xlsx"
            split_path = OUTDIR / split_name
            g.to_excel(split_path, index=False)
            log(f"[SAVE][SPLIT] {split_path}")

    return str(main_path)


# -----------------------------
# 메시지 생성
# -----------------------------

def _mk_subject(row):

    title = _norm(row.get("공고명"))

    return clamp_len(title, 40)

def _mk_message(row):

    bid_no = _norm(row.get("공고번호"))

    bid_ord = _norm(row.get("차수") or "000")

    title = _norm(row.get("공고명"))

    close = _norm(row.get("입찰마감일시"))

    region = _norm(row.get("공동도급지역"))

    if not region:

        raw = row.get("원문") or {}

        region = _norm(raw.get("jntcontrctDutyRgnNm1"))

        if not region:

            region = _norm(raw.get("cnstrtsiteRgnNm"))

    est_str, est_val, jnt_str = parse_estimate_and_joint(row)

    lines = [

        "[세리공영]",

        "",

        f"공고명 : {title}",

        f"입찰마감일시 : {close}",

        f"공동도급지역 : {region}",

        f"공동도급비율 : {jnt_str}",

        f"추정금액 : {est_str}",

        f"공고번호 : {bid_no} - {bid_ord}",

    ]

    return "\n".join(lines)
# -----------------------------
# 행(r) 에서 지역/공종코드 추출 헬퍼
# -----------------------------
def _extract_region(r: dict) -> str:
    """
    파일 로그용 지역 문자열 추출.
    - 내부의 extract_region_tags() 를 그대로 활용해서
      '전국,충북' 이런 형태로 정렬된 문자열을 만든다.
    """
    if not r:
        return ""
    try:
        tags = extract_region_tags(r)
    except Exception:
        return ""
    if not tags:
        return ""
    return ",".join(sorted(tags))


def _extract_ind_code(r: dict) -> str:
    """
    파일 로그용 공종코드(업종코드) 추출.
    - fetch_ind() 에서 이미 '공고업종코드' 키로 넣어두었으므로
      그 값을 그대로 사용한다.
    """
    if not r:
        return ""
    v = r.get("공고업종코드")
    return str(v).strip() if v is not None else ""

# -----------------------------
# 알림톡 발송 (운영용 + 테스트 모드 + 파일 로그: 지역/공종 포함)
# -----------------------------
def send_all(rows, test: bool = False) -> int:
    """
    전체 rows에 대해:
      - ntcedata / recvdata / sendlog DB 기록
      - is_target_row / decide_receivers / choose_template 로 발송 대상 판정
      - Alligo.sendTalk 로 알림톡 발송
      - sendlog 기반 '완전 중복 방지' (INSERT IGNORE 선반영)
      - 별도 파일 로그로 발송 내역 기록 (지역, 공종코드 포함)

    test=True:
      - DB 기록은 정상
      - 실제 알리고 발송하지 않음(DRY)
    """
    if not rows:
        log("[ALIMTALK] no rows to send")
        return 0

    if Alligo is None:
        log("[ALIMTALK] alligo module not found")
        return 0

    # -----------------------------
    # 내부 헬퍼: 별도 발송 로그 파일 남기기
    # -----------------------------
    def _filelog(status: str, bid_no: str, bid_ord: str,
                 ph: str, region: str, ind_code: str,
                 tpl_code: str,
                 note: str = "") -> None:
        """
        status: 'DRY', 'OK', 'FAIL' 등
        region: 추출된 지역 문자열
        ind_code: 공종코드 (예: 6202, 0040 등)
        tpl_code: 실제 사용한 템플릿 코드 (예: TB_0485, TZ_4492 등)
        note  : 에러 메시지 등 추가 정보

        저장 경로:
          /mnt/vol1/n_data/logs/kakao/kakao_send_YYYYMMDD.log
          (Windows: Z:\\VOL1\\bid\\n_data\\logs\\kakao\\...)
        """
        try:
            from datetime import datetime

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 카카오 로그 폴더
            DIR_LOG_KAKAO.mkdir(parents=True, exist_ok=True)

            fname = DIR_LOG_KAKAO / f"kakao_send_{datetime.now().strftime('%Y%m%d')}.log"

            # 탭(\t) 구분: 시간, 상태, 공고번호, 차수, 전화번호, 템플릿코드, 지역, 공종코드, note
            line = (
                f"{ts}\t{status}\t{bid_no}\t{bid_ord}\t{ph}\t"
                f"{tpl_code}\t{region}\t{ind_code}\t{note}\n"
            )

            with open(fname, "a", encoding="utf-8") as f:
                f.write(line)

        except Exception as e:
            log(f"[WARN][FILELOG] write failed: {e}")


    # =========================================================
    # DRY-RUN 처리
    # =========================================================
    env_dry = (
        os.getenv("KAKAO_DRY_RUN", "0") == "1"
        or os.getenv("KAKAO_TEST", "0") == "1"
    )
    dry = test or env_dry

    ensure_tables()

    # =========================================================
    # DB 연결
    # =========================================================
    try:
        cn = get_db_conn()
    except Exception as e:
        log(f"[ERROR][DB] send_all() DB 연결 실패: {e}")
        return 0

    a = Alligo()
    sent = 0
    total_rows = len(rows)

    # =========================================================
    # 메인 LOOP
    # =========================================================
    try:
        for r in rows:

            bid_no = str(r.get("공고번호") or "").strip()
            bid_ord = str(r.get("차수") or "000").strip()

            region = _extract_region(r)
            ind_code = _extract_ind_code(r)

            # 1) 공고 원문 저장
            try:
                upsert_ntcedata(cn, r)
            except Exception as e:
                log(f"[ERROR][DB] upsert_ntcedata 실패 {bid_no}/{bid_ord}: {e}")
                continue

            # 2) 발송대상인지 체크
            try:
                if not is_target_row(r):
                    log(f"[SKIP][RULE] {bid_no}/{bid_ord}")
                    continue
            except Exception as e:
                log(f"[ERROR][RULE] is_target_row 실패 {bid_no}/{bid_ord}: {e}")
                continue

            # 3) 수신번호 결정
            try:
                receivers = decide_receivers(r)
            except Exception as e:
                log(f"[ERROR][RECV] decide_receivers 실패 {bid_no}/{bid_ord}: {e}")
                continue

            if not receivers:
                log(f"[SKIP][NO-RECV] {bid_no}/{bid_ord}")
                continue

            # 4) recvdata DB 기록
            try:
                recv_upsert_db(cn, bid_no, bid_ord, receivers)
            except Exception as e:
                log(f"[ERROR][DB] recv_upsert_db 실패 {bid_no}/{bid_ord}: {e}")

            # 5) 템플릿 자동 선택
            try:
                tpl_code = choose_template(r)    # *** 자동 템플릿 선택 ***
            except Exception as e:
                tpl_code = TEMPLATE_CODE        # fallback
                log(f"[WARN][TPL] choose_template 실패 {bid_no}/{bid_ord}: {e}")

            # 6) 메시지 생성
            try:
                subj = _mk_subject(r)
                msg = _mk_message(r)
            except Exception as e:
                log(f"[ERROR][FMT] 메시지 생성 실패 {bid_no}/{bid_ord}: {e}")
                continue

            # 7) 발송 LOOP
            for ph in receivers:
                ph = (ph or "").strip()
                if not ph:
                    continue

                # -----------------------------
                # DB 선삽입(중복 방지)
                # -----------------------------
                try:
                    with cn.cursor() as cur:
                        sql = """
                            INSERT IGNORE INTO sendlog (bid_no, bid_ord, receiver, tpl)
                            VALUES (%s, %s, %s, %s)
                        """
                        cur.execute(sql, (bid_no, bid_ord, ph, tpl_code))
                        affected = cur.rowcount
                except Exception as e:
                    log(f"[ERROR][DB] sendlog pre-insert 실패 {bid_no}/{bid_ord} -> {ph}: {e}")
                    continue

                if affected == 0:
                    log(f"[DEDUP] skip {bid_no}/{bid_ord} -> {ph}")
                    continue

                # -----------------------------
                # DRY-RUN이면 여기서 끝
                # -----------------------------
                if dry:
                    log(f"[DRY] {bid_no}/{bid_ord} -> {ph} tpl={tpl_code}")
                    _filelog("DRY", bid_no, bid_ord, ph, region, ind_code, tpl_code, "dry-run")
                    sent += 1
                    continue

                # -----------------------------
                # 실제 발송
                # -----------------------------
                log(f"[DEBUG][SEND] {bid_no}/{bid_ord} -> {ph} tpl={tpl_code}")
                try:
                    ok = a.sendTalk(tpl_code, SENDER_NUM, subj, msg, [ph])
                except Exception as e:
                    log(f"[SEND][ERR] {bid_no}/{bid_ord} -> {ph}: {e}")
                    _filelog("FAIL", bid_no, bid_ord, ph, region, ind_code, tpl_code, f"exception:{e}")

                    # 롤백
                    try:
                        with cn.cursor() as cur:
                            cur.execute(
                                "DELETE FROM sendlog WHERE bid_no=%s AND bid_ord=%s AND receiver=%s AND tpl=%s",
                                (bid_no, bid_ord, ph, tpl_code),
                            )
                    except Exception as e2:
                        log(f"[WARN][DB] rollback 실패 {bid_no}/{bid_ord} -> {ph}: {e2}")
                    continue

                # -----------------------------
                # 응답 FAIL
                # -----------------------------
                if not ok:
                    log(f"[SEND][FAIL] {bid_no}/{bid_ord} -> {ph}")
                    _filelog("FAIL", bid_no, bid_ord, ph, region, ind_code, tpl_code, "sendTalk returned False")
                    try:
                        with cn.cursor() as cur:
                            cur.execute(
                                "DELETE FROM sendlog WHERE bid_no=%s AND bid_ord=%s AND receiver=%s AND tpl=%s",
                                (bid_no, bid_ord, ph, tpl_code),
                            )
                    except Exception:
                        pass
                    continue

                # -----------------------------
                # 성공!
                # -----------------------------
                log(f"[SEND][OK] {bid_no}/{bid_ord} -> {ph}")
                _filelog("OK", bid_no, bid_ord, ph, region, ind_code, tpl_code, "")
                sent += 1

        log(f"[ALIMTALK] sent={sent}/{total_rows}")

    finally:
        try:
            cn.close()
        except Exception:
            pass

    return sent

# -----------------------------
# 리포트용 matplotlib 설정 (한글 폰트 포함)
# -----------------------------
plt = None
try:
    import matplotlib
    matplotlib.use("Agg")  # GUI 없는 서버/라즈베리파이용 백엔드
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, rcParams

    # 한글 폰트 설정 (NanumGothic 기준)
    try:
        nanum_path_candidates = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # 일반적인 경로
            "/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf",
        ]
        font_path = None
        for cand in nanum_path_candidates:
            if os.path.exists(cand):
                font_path = cand
                break

        if font_path:
            font_prop = font_manager.FontProperties(fname=font_path)
            rcParams["font.family"] = font_prop.get_name()
            log(f"[REPORT] matplotlib 한글 폰트 사용: {font_prop.get_name()}")
        else:
            log("[REPORT][WARN] NanumGothic.ttf 폰트를 찾지 못했습니다. 기본 폰트 사용.")

        # 마이너스(-) 깨짐 방지
        rcParams["axes.unicode_minus"] = False

    except Exception as e:
        log(f"[REPORT][WARN] 폰트 설정 중 오류: {e}")

except Exception as e:
    plt = None
    log(f"[REPORT][WARN] matplotlib 로드 실패, 차트 생략: {e}")

# -----------------------------
# 실행 결과 리포트(웹 대시보드용 HTML + 엑셀) 생성
# -----------------------------

def make_report(
    excel_path: str,
    bgn_dt_str: str,
    end_dt_str: str,
    report_dir: Path = OUTDIR,
):
    """
    excel_path : save_excel() 이 생성한 통합 엑셀 경로
    bgn_dt_str : 조회 시작 시각 (YYYYMMDDHHMM)
    end_dt_str : 조회 종료 시각 (YYYYMMDDHHMM)
    report_dir : 리포트 저장 폴더 (/mnt/vol1/n_data)
    """
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        log(f"[REPORT][ERR] 엑셀 로드 실패: {e}")
        return None, None

    if df.empty:
        log("[REPORT] 데이터가 없어 리포트 생성을 건너뜁니다.")
        return None, None

    # 대표 지역(지역태그의 첫 번째 값)
    def _first_tag(v):
        if not isinstance(v, str) or not v.strip():
            return ""
        return v.split(",")[0].strip()

    df["대표지역"] = df.get("지역태그", "").apply(_first_tag)

    now = datetime.now()
    ts_id = now.strftime("%Y%m%d_%H%M")
    date_str = now.strftime("%Y-%m-%d %H:%M")

    report_html = report_dir / f"입찰리포트_{ts_id}.html"
    report_xlsx = report_dir / f"입찰리포트_{ts_id}.xlsx"

    # ------------------------
    # 1. 통계 요약
    # ------------------------
    total_cnt = len(df)
    target_cnt = int((df.get("알림대상") == "Y").sum())
    by_region = df["대표지역"].value_counts().to_dict()
    by_ind = df["공고업종코드"].value_counts().to_dict()

    # ------------------------
    # 2. 최근 30일 추세 (ntcedata 기준)
    # ------------------------
    trend_daily = None
    trend_ind = None
    try:
        cn = get_db_conn()
        q = """
        SELECT DATE(created_at) AS d, ind, COUNT(*) AS cnt
        FROM ntcedata
        WHERE created_at >= (CURDATE() - INTERVAL 29 DAY)
        GROUP BY d, ind
        ORDER BY d, ind
        """
        trend_df = pd.read_sql(q, cn)
        if not trend_df.empty:
            # 일자별 전체 공고 수
            trend_daily = (
                trend_df.groupby("d")["cnt"].sum()
                .reset_index()
                .rename(columns={"cnt": "total_cnt"})
            )
            # 일자 x 업종 피벗
            trend_ind = trend_df.pivot_table(
                index="d", columns="ind", values="cnt", aggfunc="sum"
            ).fillna(0).reset_index()
    except Exception as e:
        log(f"[REPORT][WARN] 추세 데이터 조회 실패: {e}")
    finally:
        try:
            cn.close()
        except Exception:
            pass

    # ------------------------
    # 3. 오늘 발송 내역 (sendlog + ntcedata join)
    # ------------------------
    sms_df = None
    try:
        cn = get_db_conn()
        q_sms = """
        SELECT s.sent_at,
               s.bid_no,
               s.bid_ord,
               s.receiver,
               s.tpl,
               n.ind,
               n.title,
               n.region_text
        FROM sendlog s
        LEFT JOIN ntcedata n
          ON s.bid_no = n.bid_no AND s.bid_ord = n.bid_ord
        WHERE DATE(s.sent_at) = CURDATE()
        ORDER BY s.sent_at DESC
        """
        sms_df = pd.read_sql(q_sms, cn)
    except Exception as e:
        log(f"[REPORT][WARN] 발송 내역 조회 실패: {e}")
    finally:
        try:
            cn.close()
        except Exception:
            pass

    # ------------------------
    # 4. 차트 생성 (matplotlib, Agg)
    # ------------------------
    chart_files = {}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        log(f"[REPORT][WARN] matplotlib 로드 실패, 차트 생략: {e}")
        plt = None

    if plt is not None:
        try:
            # 4-1. 지역별 공고 수
            if by_region:
                fig = plt.figure(figsize=(6, 3))
                labels = list(by_region.keys())
                values = list(by_region.values())
                plt.bar(labels, values)
                plt.xticks(rotation=30, ha="right")
                plt.title("지역별 공고 수")
                fig.tight_layout()
                img_path = report_dir / f"입찰리포트_{ts_id}_region.png"
                fig.savefig(img_path)
                plt.close(fig)
                chart_files["region"] = img_path.name

            # 4-2. 업종별 공고 수
            if by_ind:
                fig = plt.figure(figsize=(6, 3))
                labels = list(by_ind.keys())
                values = list(by_ind.values())
                plt.bar(labels, values)
                plt.title("업종별 공고 수")
                fig.tight_layout()
                img_path = report_dir / f"입찰리포트_{ts_id}_ind.png"
                fig.savefig(img_path)
                plt.close(fig)
                chart_files["ind"] = img_path.name

            # 4-3. 최근 30일 일별 전체 공고 수 추이
            if trend_daily is not None and not trend_daily.empty:
                fig = plt.figure(figsize=(6, 3))
                plt.plot(trend_daily["d"], trend_daily["total_cnt"], marker="o")
                plt.xticks(rotation=30, ha="right")
                plt.title("최근 30일 공고 수 추이")
                fig.tight_layout()
                img_path = report_dir / f"입찰리포트_{ts_id}_trend_total.png"
                fig.savefig(img_path)
                plt.close(fig)
                chart_files["trend_total"] = img_path.name

        except Exception as e:
            log(f"[REPORT][WARN] 차트 생성 실패: {e}")

    # ------------------------
    # 5. HTML 본문 생성
    # ------------------------
    def _dict_to_html_table(d: dict) -> str:
        if not d:
            return "<p>데이터 없음</p>"
        rows = "".join(
            f"<tr><th>{k}</th><td>{v}</td></tr>"
            for k, v in d.items()
        )
        return f"<table class='simple'><tbody>{rows}</tbody></table>"

    summary_dict = {
        "전체 공고 수": total_cnt,
        "알림대상 공고 수": target_cnt,
    }

    # 상위 50건만 미리보기 표
    preview_html = df.head(50).to_html(
        index=False, border=0, justify="left", escape=False
    )

    # 발송 내역 HTML
    if sms_df is not None and not sms_df.empty:
        sms_html = sms_df.to_html(index=False, border=0, justify="left")
    else:
        sms_html = "<p>오늘 발송된 알림톡이 없습니다.</p>"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>입찰 리포트 {ts_id}</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }}
    h1,h2,h3 {{ margin: 0.4em 0; }}
    table {{ border-collapse: collapse; }}
    th, td {{ border: 1px solid #ccc; padding: 4px 6px; }}
    th {{ background: #f5f5f5; white-space: nowrap; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 12px; }}
    .charts img {{ max-width: 100%; height: auto; margin-bottom: 8px; }}
    .small {{ color:#666; font-size:12px; }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>입찰 리포트</h1>
  <p class="small">생성시각: {date_str} / 조회기간: {bgn_dt_str} ~ {end_dt_str}</p>

  <h2>1. 요약</h2>
  {_dict_to_html_table(summary_dict)}

  <h3>1-1. 지역별 공고 수</h3>
  {_dict_to_html_table(by_region)}

  <h3>1-2. 업종별 공고 수</h3>
  {_dict_to_html_table(by_ind)}

  <div class="charts">
    <h2>2. 차트</h2>
"""

    # 차트 이미지 섹션
    if chart_files.get("region"):
        html += f"<h3>2-1. 지역별 공고 수</h3><img src=\"{chart_files['region']}\" alt=\"지역별 공고 수\" />"
    if chart_files.get("ind"):
        html += f"<h3>2-2. 업종별 공고 수</h3><img src=\"{chart_files['ind']}\" alt=\"업종별 공고 수\" />"
    if chart_files.get("trend_total"):
        html += f"<h3>2-3. 최근 30일 공고 수 추이</h3><img src=\"{chart_files['trend_total']}\" alt=\"일별 공고 수 추이\" />"

    html += f"""
  </div>

  <h2>3. 오늘 수집 공고 (상위 50건 미리보기)</h2>
  {preview_html}
  <p class="small">전체 목록은 메인 엑셀 또는 엑셀 리포트에서 확인 가능합니다.</p>

  <h2>4. 오늘 알림톡 발송 내역</h2>
  {sms_html}

</div>
</body>
</html>
"""

    with open(report_html, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"[REPORT] HTML 생성: {report_html}")

    # ------------------------
    # 6. 엑셀 리포트 (요약/데이터/발송내역 시트)
    # ------------------------
    try:
        with pd.ExcelWriter(report_xlsx, engine="openpyxl") as writer:
            # 원본 데이터
            df.to_excel(writer, sheet_name="오늘공고", index=False)

            # 요약 시트
            sum_rows = [
                ["전체 공고 수", total_cnt],
                ["알림대상 공고 수", target_cnt],
            ]
            if by_region:
                sum_rows.append(["---", "---"])
                sum_rows.append(["[지역별 공고 수]", ""])
                for k, v in by_region.items():
                    sum_rows.append([k, v])
            if by_ind:
                sum_rows.append(["---", "---"])
                sum_rows.append(["[업종별 공고 수]", ""])
                for k, v in by_ind.items():
                    sum_rows.append([k, v])

            sum_df = pd.DataFrame(sum_rows, columns=["구분", "값"])
            sum_df.to_excel(writer, sheet_name="요약", index=False)

            # 발송 내역
            if sms_df is not None and not sms_df.empty:
                sms_df.to_excel(writer, sheet_name="발송내역", index=False)

        log(f"[REPORT] EXCEL 생성: {report_xlsx}")
    except Exception as e:
        log(f"[REPORT][WARN] 엑셀 리포트 생성 실패: {e}")

    # ------------------------
    # 7. index HTML (리포트 목록)
    # ------------------------
    try:
        index_path = report_dir / "입찰리포트_index.html"
        files = sorted(
            [p for p in report_dir.glob("입찰리포트_*.html")],
            key=lambda x: x.name,
            reverse=True,
        )

        rows_html = ""
        for p in files:
            rows_html += (
                f"<tr><td>{p.name}</td>"
                f"<td><a href=\"{p.name}\">열기</a></td></tr>"
            )

        index_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>입찰 리포트 목록</title>
  <style>
    body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }}
    table {{ border-collapse:collapse; }}
    th,td {{ border:1px solid #ccc; padding:4px 6px; }}
    th {{ background:#f5f5f5; }}
    .wrap {{ max-width:800px; margin:0 auto; padding:12px; }}
    .small {{ color:#666; font-size:12px; }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>입찰 리포트 목록</h1>
  <p class="small">총 {len(files)}개 파일</p>
  <table>
    <thead><tr><th>파일명</th><th>열기</th></tr></thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>
</body>
</html>
"""
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html)
        log(f"[REPORT] index HTML 갱신: {index_path}")
    except Exception as e:
        log(f"[REPORT][WARN] index 생성 실패: {e}")

    return str(report_html), str(report_xlsx)


# -----------------------------
# main
# -----------------------------

def main():
    backup_old_excels()

    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--ind", action="append")
    p.add_argument("--no-send", action="store_true")
    a = p.parse_args()

    days = max(1, a.days)
    end = datetime.now()
    begin = end - timedelta(days=days)

    bgn_dt = begin.strftime("%Y%m%d%H%M")
    end_dt = end.strftime("%Y%m%d%H%M")

    inds = a.ind or TARGET_INDS

    all_rows = []
    for ind in inds:
        log(f"[FETCH] ind={ind} from {bgn_dt} to {end_dt}")
        part = fetch_ind(ind, bgn_dt, end_dt)
        all_rows.extend(part)

    # 1) 필터 적용
    rows = filter_rows(all_rows)

    # 2) 엑셀 저장(통합 + 지역/공종 분할)
    excel_path = save_excel(rows)

    # 3) 리포트(예전 방식) - generate_report(rows)
    #try:
     #   generate_report(rows)
    #except Exception as e:
     #   log(f"[REPORT][ERR] generate_report() 실패: {e}")

    # 4) 신규 리포트(HTML + EXCEL)
    if excel_path:
        try:
            make_report(
                excel_path=excel_path,
                bgn_dt_str=bgn_dt,
                end_dt_str=end_dt,
                report_dir=OUTDIR,
            )
        except Exception as e:
            log(f"[REPORT][ERR] make_report() 실패: {e}")
    else:
        log("[REPORT] excel_path 없음 — make_report 스킵")

    # 5) 발송 옵션: no-send면 종료
    if a.no_send:
        log("[NO-SEND] finish")
        return

    # 6) 알림톡 실제 발송
    send_all(rows)
    log("[DONE] main_send finished.")


if __name__ == "__main__":
    # 실행 중복 방지 락
    lock_fd = acquire_lock()
    if lock_fd is None:
        sys.exit(0)   # 다른 인스턴스 실행 중

    try:
        main()
    finally:
        try:
            os.close(lock_fd)
        except Exception:
            pass
