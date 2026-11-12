
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

TARGET_INDS = ["6202", "0040", "0037", "0038", "0039"]

OUTDIR = Path("/mnt/vol1/n_data")
OUTDIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_CODE = os.getenv("ALLIGO_TPL_CODE", "TB_0485")
SENDER_NUM = os.getenv("ALLIGO_SENDER", "REDACTED_PRIVATE_VALUE")

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
    return s if len(s) <= n else s[: n - 1] + "…"

from urllib.parse import unquote

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
# 1차 필터 (업종 필터)
# -----------------------------
def filter_rows(rows):
    filtered = [r for r in rows if (r.get("공고업종코드") in TARGET_INDS)]
    log(f"[FILTER] {len(filtered)} rows")
    return filtered

# -----------------------------
# 지역 태그 / 대상 판정 / 수신번호 로직 (Python 3.7~3.9 호환)
# -----------------------------

def normalize_region(name):
    """API 지역 문자열 → 내부 지역 태그 변환"""
    if not name:
        return None
    s = str(name)

    if "전국" in s:
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
    tags = set()

    t1 = normalize_region(_norm(row.get("공동도급지역")))
    t2 = normalize_region(_norm(row.get("수요지역")))
    if t1: tags.add(t1)
    if t2: tags.add(t2)

    raw = row.get("원문") or {}

    t3 = normalize_region(_norm(raw.get("cnstrtsiteRgnNm")))
    t4 = normalize_region(_norm(raw.get("jntcontrctDutyRgnNm1")))
    if t3: tags.add(t3)
    if t4: tags.add(t4)

    # 추정가 기반 전국 판정
    est_str = _norm(raw.get("presmptPrce"))
    try:
        est_val = int(est_str) if est_str else 0
    except:
        est_val = 0

    jnt_region = _norm(raw.get("jntcontrctDutyRgnNm1"))
    jnt_rate_str = _norm(raw.get("rgnDutyJntcontrctRt"))
    try:
        jnt_rate = float(jnt_rate_str) if jnt_rate_str else None
    except:
        jnt_rate = None

    if est_val >= 1_000_000_000 and jnt_region and jnt_rate is not None:
        tags.add("전국")
        jr = normalize_region(jnt_region)
        if jr:
            tags.add(jr)

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
    ind = str(row.get("공고업종코드") or "")
    if ind not in {"0038", "0039", "0040", "6202"}:
        return []

    tags = extract_region_tags(row)
    phones = set()

    # 전국이면 4명
    if "전국" in tags:
        phones.update([
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
            "REDACTED_PRIVATE_VALUE",
        ])
        return sorted(phones)

    # 강원 단독 제외
    if tags == {"강원"}:
        return []

    # 지역별 규칙
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
    path = OUTDIR / ("입찰공고_%s.xlsx" % now)

    def conv(r):
        raw = r.get("원문") or {}

        # ----- 공동도급지역 표시값 -----
        region_display = _norm(r.get("공동도급지역"))
        if not region_display:
            region_display = _norm(raw.get("jntcontrctDutyRgnNm1"))
            if not region_display:
                region_display = _norm(raw.get("cnstrtsiteRgnNm"))

        # ----- 추정금액 / 공동도급비율 -----
        est_str, est_val, jnt_str = parse_estimate_and_joint(r)

        # ----- 게시일시(bidNtceDt) 추가 -----
        bid_notice_dt = _norm(raw.get("bidNtceDt"))

        # ----- 기본 컬럼 생성 -----
        base = {
            "공고업종코드": r.get("공고업종코드", ""),
            "공고번호": r.get("공고번호", ""),
            "차수": r.get("차수", ""),
            "공고명": r.get("공고명", ""),
            "입찰마감일시": r.get("입찰마감일시", ""),
            "공동도급지역": region_display,
            "수요지역": r.get("수요지역", ""),
            "게시일시": bid_notice_dt,   # ⭐ 신규 추가
        }

        # ----- 지역 태그 -----
        tags = extract_region_tags(r)
        tags_str = ",".join(sorted(tags)) if tags else ""

        # ----- SKIP 이유 -----
        skip_reason = get_skip_reason(r)

        # ----- 알림 대상 여부 -----
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

        # ----- 추가 정보 -----
        base["추정금액"] = est_str
        base["추정금액_원"] = est_val
        base["공동도급비율"] = jnt_str

        base["원문"] = json.dumps(raw, ensure_ascii=False)
        return base


    df = pd.DataFrame([conv(r) for r in rows])
    df.to_excel(path, index=False)
    log("[SAVE] %s" % path)

    return str(path)
# -----------------------------
# 메시지 생성
# -----------------------------
def _mk_message(row):
    bid_no = _norm(row.get("공고번호"))
    bid_ord = _norm(row.get("차수") or "000")
    title = _norm(row.get("공고명"))
    close = _norm(row.get("입찰마감일시"))

    # 1차: 엑셀 컬럼 "공동도급지역"
    region = _norm(row.get("공동도급지역"))

    # 2차: 비어 있으면 원문 JSON의 jntcontrctDutyRgnNm1 사용
    if not region:
        raw = row.get("원문") or {}
        region = _norm(raw.get("jntcontrctDutyRgnNm1"))
        # 그래도 없으면 최종으로 cnstrtsiteRgnNm 사용
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
# 알림톡 발송
# -----------------------------
def send_alk(rows):
    if not rows:
        return 0
    if Alligo is None:
        log("[ALIMTALK] alligo module not found")
        return 0

    ensure_tables()

    dry = os.getenv("KAKAO_DRY_RUN", "0") == "1" or os.getenv("KAKAO_TEST", "0") == "1"

    cn = get_db_conn()
    a = Alligo()
    sent = 0

    try:
        for r in rows:
            bid_no = str(r.get("공고번호") or "")
            bid_ord = str(r.get("차수") or "000")

            # DB 기록
            upsert_ntcedata(cn, r)

            # 발송 대상 여부 판정
            if not is_target_row(r):
                log(f"[SKIP][RULE] {bid_no}/{bid_ord}")
                continue

            receivers = decide_receivers(r)
            if not receivers:
                log(f"[SKIP][NO-RECV] {bid_no}/{bid_ord}")
                continue

            # recvdata DB 기록
            recv_upsert_db(cn, bid_no, bid_ord, receivers)

            # 중복 제거
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
