
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import requests
import pandas as pd
import pymysql

# -----------------------------
# Alligo 모듈 (같은 폴더의 alligo.py)
# -----------------------------
try:
    from alligo import Alligo
except ImportError:
    Alligo = None

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

# 조회 대상 업종
TARGET_INDS = ["6202", "0040", "0037", "0038", "0039"]

OUTDIR = Path("/mnt/vol1/n_data")
OUTDIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_CODE = os.getenv("ALLIGO_TPL_CODE", "TB_0485")
SENDER_NUM = os.getenv("ALLIGO_SENDER", "REDACTED_PRIVATE_VALUE")

# 추후 금액/공동도급 조건용 (지금은 0 / False 이라 실제 필터에는 영향 없음)
MIN_ESTIMATE_FOR_TARGET = 0        # 예: 10억 이상만이면 1000000000 으로 변경
REQUIRE_JOINT_RATE = False         # True 로 바꾸면 공동도급비율이 있을 때만 발송

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
    return s if len(s) <= n else s[: n - 1] + "…"

from urllib.parse import unquote

def get_service_key():
    """
    공공데이터포털 SERVICE_KEY 가져오기
    - 환경변수/파일에 URL 인코딩된 값이 들어 있어도 항상 '원래 값'으로 복원
    """
    key = None

    # 1) 환경변수 우선
    if SERVICE_KEY_ENV:
        key = SERVICE_KEY_ENV.strip()
    else:
        # 2) 없으면 키 파일에서 읽기
        try:
            key = Path(KEY_PATH).read_text(encoding="utf-8").strip()
        except Exception:
            log(f"[ERR] API key file not found: {KEY_PATH}")
            return ""

    # URL 인코딩돼 있다면 unquote
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
# API fetch
# -----------------------------
def fetch_ind(ind, bgn_dt, end_dt, retries=3, timeout=15):
    key = get_service_key()
    if not key:
        log("[ERR] SERVICE_KEY missing")
        return []

    params = {
        "serviceKey": key,
        "type": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "inqryDiv": 1,
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
        "indstrytyCd": ind,
    }

    tries = 0
    while True:
        tries += 1
        try:
            r = requests.get(API_BASE, params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()

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
                    "공고업종코드": ind,
                    "공고번호": _norm(it.get("bidNtceNo")),
                    "차수": _norm(it.get("bidNtceOrd")),
                    "공고명": _norm(it.get("bidNtceNm")),
                    "입찰마감일시": _norm(it.get("bidClseDt")),
                    "공동도급지역": _norm(it.get("prtcptLmtRgnNm")),
                    "수요지역": _norm(it.get("dmndInsttLocplcNm")),
                    "원문": it,
                }
                out.append(row)

            log(f"[HTTP] ind={ind} count={len(out)}")
            return out

        except Exception as e:
            if tries >= retries:
                log(f"[ERR] fetch_ind {ind}: {e}")
                return []
            time.sleep(1.1 * tries)

# -----------------------------
# 필터 (업종 필터)
# -----------------------------
def filter_rows(rows):
    filtered = [r for r in rows if (r.get("공고업종코드") in TARGET_INDS)]
    log(f"[FILTER] {len(filtered)} rows")
    return filtered

# -----------------------------
# 지역 파싱 / 대상 판정 / 수신번호 결정
# -----------------------------
def extract_region_tags(row):
    """
    지역태그 계산

    - 기본 텍스트 기준:
        · '전국', '충북/충청북도', '세종', '경북/경상북도', '대구' 를 찾음
    - 추가 전국 판정 규칙 (모든 지역 공통 규칙):
        · 원문(raw)에 다음 조건을 모두 만족하면 '전국'으로 간주
            1) presmptPrce(추정가격) >= 1,000,000,000
            2) jntcontrctDutyRgnNm1 에 지역명이 있음
            3) rgnDutyJntcontrctRt 가 0 ~ 100 사이 숫자

      예시:
        "presmptPrce": "1061161820",
        "jntcontrctDutyRgnNm1": "강원특별자치도",
        "rgnDutyJntcontrctRt": "49"
      → 전국 + 강원 태그 부여
    """
    # 기본: 공고 화면에 보이는 지역 문자열에서 태그 추출
    txt = _norm(row.get("공동도급지역")) + " " + _norm(row.get("수요지역"))
    tags = set()

    # 1) 표시 문자열에서 직접 찾는 지역들
    if "전국" in txt:
        tags.add("전국")
    if ("충북" in txt) or ("충청북도" in txt):
        tags.add("충북")
    if ("경북" in txt) or ("경상북도" in txt):
        tags.add("경북")
    if "대구" in txt:
        tags.add("대구")
    if "세종" in txt:
        tags.add("세종")
    if "강원" in txt or "강원특별자치도" in txt:
        tags.add("강원")

    # 2) 원문 JSON 기반 전국 자동 판정 로직
    raw = row.get("원문") or {}

    # presmptPrce (추정가격) 파싱
    est_str = _norm(raw.get("presmptPrce"))
    try:
        est_val = int(est_str) if est_str else 0
    except ValueError:
        est_val = 0

    # 공동도급 의무지역 / 비율 파싱
    jnt_region = _norm(raw.get("jntcontrctDutyRgnNm1"))
    jnt_rate_str = _norm(raw.get("rgnDutyJntcontrctRt"))
    try:
        jnt_rate = float(jnt_rate_str) if jnt_rate_str else None
    except ValueError:
        jnt_rate = None

    # 조건:
    #   · 추정가격 >= 1,000,000,000
    #   · jntcontrctDutyRgnNm1 에 지역명 존재
    #   · rgnDutyJntcontrctRt 가 0~100 사이 수치
    if (
        est_val >= 1_000_000_000
        and jnt_region
        and (jnt_rate is not None)
        and (0.0 <= jnt_rate <= 100.0)
    ):
        # 전국 판정
        tags.add("전국")

        # 공동도급 의무지역 이름으로부터 추가 지역 태그 추출
        if "충북" in jnt_region or "충청북도" in jnt_region:
            tags.add("충북")
        if "세종" in jnt_region:
            tags.add("세종")
        if "경북" in jnt_region or "경상북도" in jnt_region:
            tags.add("경북")
        if "대구" in jnt_region:
            tags.add("대구")
        if "강원" in jnt_region or "강원특별자치도" in jnt_region:
            tags.add("강원")

        # 디버그용 로그 (전국 자동 판정된 건만 표시)
        print(
            f"[AUTO-NATIONAL] presmptPrce={est_val:,}, "
            f"jntRegion='{jnt_region}', jntRate={jnt_rate_str} "
            f"→ 전국 처리: {row.get('공고번호')}/{row.get('차수')}"
        )

    return tags


def parse_estimate_and_joint(row):
    raw = row.get("원문") or {}
    est_str = _norm(raw.get("presmptPrce"))
    jnt_str = _norm(raw.get("rgnDutyJntcontrctRt"))
    try:
        est_val = int(est_str) if est_str else 0
    except ValueError:
        est_val = 0
    return est_str, est_val, jnt_str

def get_skip_reason(row):
    """ SKIP 사유 문자열 생성 """

    ind = str(row.get("공고업종코드") or "")
    special = {"0038", "0039", "0040", "6202"}
    if ind not in special:
        return "업종제외"

    tags = extract_region_tags(row)
    target_tags = {"전국", "충북", "세종", "경북", "대구"}

    if not (tags & target_tags):
        return "지역태그없음"

    # 금액 조건
    est_str, est_val, jnt_str = parse_estimate_and_joint(row)
    if MIN_ESTIMATE_FOR_TARGET and est_val < MIN_ESTIMATE_FOR_TARGET:
        return "금액미달"

    # 전국판단에 쓰는 공동도급 조건 확인
    raw = row.get("원문") or {}
    pres = _norm(raw.get("presmptPrce"))
    duty_region = _norm(raw.get("jntcontrctDutyRgnNm1"))
    duty_rate_str = _norm(raw.get("rgnDutyJntcontrctRt"))

    # 10억 이상 + 지역명 있음 + 비율 0~100 → 전국 판정
    try:
        pres_val = int(pres) if pres else 0
    except:
        pres_val = 0
    try:
        duty_rate = float(duty_rate_str) if duty_rate_str else None
    except:
        duty_rate = None

    if pres_val >= 1_000_000_000:
        if not duty_region:
            return "전국판정-의무지역없음"
        if duty_rate is None or duty_rate < 0 or duty_rate > 100:
            return "전국판정-의무비율없음"

    # 기본적으로 대상 조건을 만족한 경우
    return ""

def is_target_row(row) -> bool:
    """
    알림톡 발송 대상 여부:
      - 업종: 0038, 0039, 0040, 6202
      - 지역태그: 전국, 충북, 세종, 경북, 대구 중 하나 이상
      - presmptPrce >= 1,000,000,000 이고
        jntcontrctDutyRgnNm1 있고 rgnDutyJntcontrctRt 0~100 사이면 → 전국 자동판정
      - SKIP 사유를 상세 로그로 출력
    """

    # -------------------------
    # 1) 업종 체크
    # -------------------------
    ind = str(row.get("공고업종코드") or "")
    special = {"0038", "0039", "0040", "6202"}
    if ind not in special:
        print(f"[SKIP][IND] 업종 미대상({ind}) → {row.get('공고번호')}/{row.get('차수')}")
        return False

    # -------------------------
    # 2) 지역태그 추출
    # -------------------------
    tags = extract_region_tags(row)
    target_tags = {"전국", "충북", "세종", "경북", "대구"}

    # 지역태그 없음
    if not tags:
        print(f"[SKIP][REGION] 지역태그 없음 → {row.get('공고번호')}/{row.get('차수')}")
        return False

    # target_tags 교집합이 없으면 SKIP
    if not (tags & target_tags):
        print(f"[SKIP][PRICE] 지역/전국 기준 미충족(tags={tags}) → {row.get('공고번호')}/{row.get('차수')}")
        return False

    # -------------------------
    # 3) 금액/공동도급 조건 (옵션)
    # -------------------------
    est_str, est_val, jnt_str = parse_estimate_and_joint(row)

    # MIN_ESTIMATE_FOR_TARGET 옵션
    if MIN_ESTIMATE_FOR_TARGET and est_val < MIN_ESTIMATE_FOR_TARGET:
        print(f"[SKIP][PRICE] 추정가격 {est_val:,} < 기준금액 {MIN_ESTIMATE_FOR_TARGET:,} → {row.get('공고번호')}/{row.get('차수')}")
        return False

    # REQUIRE_JOINT_RATE 옵션
    if REQUIRE_JOINT_RATE and not jnt_str:
        print(f"[SKIP][JOINT] 공동도급비율 없음 → {row.get('공고번호')}/{row.get('차수')}")
        return False

    # -------------------------
    # 4) 최종 통과
    # -------------------------
    return True


def decide_receivers(row) -> List[str]:
    """
    최종 규칙(업종은 0038,0039,0040,6202만 의미 있음):

      - 전국일 때: 2060, 2051, 3560, 0340 (4명 모두)
      - 충북: 2060, 2051
      - 세종: 3560, 2051
      - 경북: 0340
      - 대구: 0340

      - 전국 + 다른 지역(충북/세종/경북/대구)이 섞여 있어도
        '전국'이 포함되면 4명 모두에게 발송.
    """
    ind = str(row.get("공고업종코드") or "")
    special = {"0038", "0039", "0040", "6202"}
    if ind not in special:
        return []

    tags = extract_region_tags(row)
    phones = set()

    # 전국이면 4명 모두
    if "전국" in tags:
        phones.update([
            "REDACTED_PRIVATE_VALUE",  # 2060
            "REDACTED_PRIVATE_VALUE",  # 2051
            "REDACTED_PRIVATE_VALUE",  # 3560
            "REDACTED_PRIVATE_VALUE",  # 0340
        ])
    else:
        # 전국이 아닌 경우, 각각의 지역별 규칙 적용
        if "충북" in tags:
            phones.update(["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"])
        if "세종" in tags:
            phones.update(["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"])
        if "경북" in tags or "대구" in tags:
            phones.add("REDACTED_PRIVATE_VALUE")

    return sorted(phones)

# -----------------------------
# 엑셀 저장
# -----------------------------
def save_excel(rows):
    if not rows:
        return None
    now = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUTDIR / f"입찰공고_{now}.xlsx"

    def conv(r):
        base = {
            "공고업종코드": r.get("공고업종코드", ""),
            "공고번호": r.get("공고번호", ""),
            "차수": r.get("차수", ""),
            "공고명": r.get("공고명", ""),
            "입찰마감일시": r.get("입찰마감일시", ""),
            "공동도급지역": r.get("공동도급지역", ""),
            "수요지역": r.get("수요지역", ""),
        }

        # 지역 태그
        tags = extract_region_tags(r)
        tags_str = ",".join(sorted(tags)) if tags else ""

        # 추정금액 / 공동도급비율
        est_str, est_val, jnt_str = parse_estimate_and_joint(r)
        
         # SKIP 이유 추가
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

        base["추정금액"] = est_str
        base["추정금액_원"] = est_val
        base["공동도급비율"] = jnt_str

        base["원문"] = json.dumps(r.get("원문", {}), ensure_ascii=False)
        return base

    pd.DataFrame([conv(r) for r in rows]).to_excel(path, index=False)
    log(f"[SAVE] {path}")
    return str(path)

# -----------------------------
# 메시지 생성
# -----------------------------
def _mk_subject(row):
    return clamp_len(row.get("공고명", ""), 40)

def _mk_message(row):
    bid_no = _norm(row.get("공고번호"))
    bid_ord = _norm(row.get("차수") or "000")
    title = _norm(row.get("공고명"))
    close = _norm(row.get("입찰마감일시"))
    region = _norm(row.get("공동도급지역"))
    raw = row.get("원문") or {}
    est_str, est_val, jnt_str = parse_estimate_and_joint(row)

    lines = [
        "[세리공영]",
        "",
        f"공고명 : {title}",
        f"입찰마감일시 :  {close}",
        f"공동도급지역 : {region}",
        f"공동도급비율 : {jnt_str}",
        f"추정금액 : {est_str}",
        f"공고번호 : {bid_no} - {bid_ord}",
    ]
    return "\n".join(lines)

# -----------------------------
# 알림톡 발송
# -----------------------------
def send_alk(rows):
    if not rows:
        return 0
    if Alligo is None:
        log("[ALIMTALK] alligo module not found")
        return 0

    ensure_tables()

    # 환경변수로 드라이런 제어 (기본: 실제 발송)
    dry = os.getenv("KAKAO_DRY_RUN", "0") == "1" or os.getenv("KAKAO_TEST", "0") == "1"

    cn = get_db_conn()
    a = Alligo()
    sent = 0

    try:
        for r in rows:
            bid_no = str(r.get("공고번호") or "")
            bid_ord = str(r.get("차수") or "000")

            # DB에는 모든 공고를 적재
            upsert_ntcedata(cn, r)

            # 발송 대상이 아니면 규칙 스킵
            if not is_target_row(r):
                log(f"[SKIP][RULE] {bid_no}/{bid_ord}")
                continue

            receivers = decide_receivers(r)
            if not receivers:
                log(f"[SKIP][NO-RECV] {bid_no}/{bid_ord}")
                continue

            recv_upsert_db(cn, bid_no, bid_ord, receivers)

            targets = []
            for ph in receivers:
                if already_sent(bid_no, bid_ord, ph, TEMPLATE_CODE):
                    log(f"[DEDUP] skip {bid_no}/{bid_ord} -> {ph}")
                else:
                    targets.append(ph)

            if not targets:
                continue

            subj = _mk_subject(r)
            msg = _mk_message(r)

            if dry:
                log(f"[DRY] {bid_no}/{bid_ord} -> {targets}")
                continue

            try:
                ok = a.sendTalk(TEMPLATE_CODE, SENDER_NUM, subj, msg, targets)
                if not ok:
                    log(f"[SEND][FAIL] {bid_no}/{bid_ord}")
                    continue

                for ph in targets:
                    mark_sent(bid_no, bid_ord, ph, TEMPLATE_CODE)
                    log(f"[SEND][OK] {bid_no}/{bid_ord} -> {ph}")
                    sent += 1

            except Exception as e:
                log(f"[SEND][ERR] {bid_no}/{bid_ord}: {e}")

    finally:
        cn.close()

    log(f"[ALIMTALK] sent={sent}/{len(rows)}")
    return sent

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
        log(f"[FETCH] ind={ind}")
        part = fetch_ind(ind, bgn_dt, end_dt)
        all_rows.extend(part)

    rows = filter_rows(all_rows)
    save_excel(rows)

    if a.no_send:
        log("[NO-SEND] finish")
        return

    send_alk(rows)
    log("[DONE]")

if __name__ == "__main__":
    main()
