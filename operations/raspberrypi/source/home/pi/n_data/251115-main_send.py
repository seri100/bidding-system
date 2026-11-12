
# -*- coding: utf-8 -*-



import os, sys, json, time, math

from datetime import datetime, timedelta

from urllib.parse import quote

from pathlib import Path



import requests

import pandas as pd

import pymysql

from typing import List



# 알리고 모듈

try:

    from alligo import Alligo

except ImportError:

    Alligo = None


# 사용할 알림톡 템플릿 코드 (환경변수 없으면 TB_0485 사용)
TEMPLATE_CODE = os.getenv("ALLIGO_TPL_CODE", "TB_0485")



# ============================

# DB 설정

# ============================

DB_CONFIG = {

    "host": "REDACTED_PRIVATE_VALUE",

    "user": 'REDACTED_PRIVATE_VALUE',

    "password": 'REDACTED_PRIVATE_VALUE',   # MySQL 계정 비밀번호

    "db": "kakao",

    "charset": "utf8",

    "cursorclass": pymysql.cursors.DictCursor,

    "autocommit": True,

}





def get_db_conn():

    """kakao DB에 접속하는 공용 커넥션 함수"""

    return pymysql.connect(**DB_CONFIG)





def recv_upsert_db(

    conn,

    bidNtceCode: str,

    bidNtceOrd: str,

    receivers: List[str],

):

    """

    recvdata 업서트 함수



    - PK: (bidNtceCode, bidNtceOrd)

    - recvPhone : 대표 수신번호 1개 (receivers 리스트의 첫 번째)

    - receivers : 전체 수신번호 CSV ("010...,010...")

    - sent_at   : NOW() 로 매 호출 시점 갱신

    """

    bidNtceCode = str(bidNtceCode)

    bidNtceOrd  = str(bidNtceOrd)



    main_phone = receivers[0] if receivers else ""

    recv_str = ",".join([x for x in receivers if x])



    sql = """

    INSERT INTO recvdata

        (bidNtceCode, bidNtceOrd, recvPhone, sent_at, receivers)

    VALUES

        (%s, %s, %s, NOW(), %s)

    ON DUPLICATE KEY UPDATE

        recvPhone = VALUES(recvPhone),

        sent_at   = VALUES(sent_at),

        receivers = VALUES(receivers)

    """

    params = (bidNtceCode, bidNtceOrd, main_phone, recv_str)

    with conn.cursor() as cur:

        cur.execute(sql, params)

def _db_conn():
    """ntcedata / sendlog 용 공용 커넥션 (kakao DB 재사용)"""
    return get_db_conn()


def already_sent(bid_no, bid_ord, receiver, tpl=TEMPLATE_CODE):
    """sendlog 에 이미 발송 기록이 있는지 확인"""
    cn = _db_conn()
    try:
        with cn.cursor() as c:
            sql = """
            SELECT 1
              FROM sendlog
             WHERE bid_no=%s
               AND bid_ord=%s
               AND receiver=%s
               AND tpl=%s
             LIMIT 1
            """
            c.execute(sql, (bid_no, bid_ord, receiver, tpl))
            row = c.fetchone()
            return bool(row)
    finally:
        cn.close()


def mark_sent(bid_no, bid_ord, receiver, tpl=TEMPLATE_CODE):
    """sendlog 에 발송 기록 INSERT (중복은 무시)"""
    cn = _db_conn()
    try:
        with cn.cursor() as c:
            sql = """
            INSERT IGNORE INTO sendlog (bid_no, bid_ord, receiver, tpl)
            VALUES (%s, %s, %s, %s)
            """
            c.execute(sql, (bid_no, bid_ord, receiver, tpl))
    finally:
        cn.close()




# ============================

# 상수/환경

# ============================

API_BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"

KEY_PATH = "/home/pi/n_data/bid_api_key.txt"



# 업종코드 5종

TARGET_INDS = [

    "6202",  # 기계설비

    "0040",  # 소방

    "0037",  # 전기

    "0038",  # 소방기계

    "0039",  # 소방전

]



# 전국 시·도 키워드 (짧은 문자열로 포함 여부만 체크)

TARGET_REGION_KEYWORDS = [

    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",

    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남",

    "제주", "기타",

]



OUTDIR = Path("/mnt/vol1/n_data")

OUTDIR.mkdir(parents=True, exist_ok=True)



# 기본 수신번호(리스트)

RECEIVERS = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]



# 알리고 템플릿 / 발신번호

TEMPLATE_CODE = "TB_0485"       # 템플릿 코드

SENDER_NUM    = "REDACTED_PRIVATE_VALUE"   # 발신번호


# 유틸 함수

# ============================

def _norm(x):

    """API 응답 element를 문자열로 일관되게 정규화."""

    if isinstance(x, list):

        return " ".join(_norm(v) for v in x)

    if isinstance(x, dict):

        return " ".join(_norm(v) for v in x.values())

    if x is None:

        return ""

    return str(x).strip()





def log(msg):

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{ts}] {msg}", flush=True)





def load_key():

    raw = Path(KEY_PATH).read_text(encoding="utf-8").strip()

    return raw, quote(raw, safe="")





def clamp_len(s, n=80):

    s = _norm(s)

    return s if len(s) <= n else s[: n - 1] + "…"





# ============================

# API 호출

# ============================

def fetch_ind(ind, bgn_dt, end_dt, retries=3, timeout=15):

    """

    업종코드별 공고 목록 수집(최근 기간).

    응답 JSON을 행 리스트로 변환.

    """

    raw_key, _ = load_key()

    params = {

        "serviceKey": raw_key,

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

            resp = requests.get(API_BASE, params=params, timeout=timeout)

            resp.raise_for_status()

            data = resp.json()



            response = data.get("response") if isinstance(data, dict) else {}

            body = (response or {}).get("body") if isinstance(response, dict) else {}

            items = (body or {}).get("items")



            if items is None:

                items = []

            if isinstance(items, dict):

                src_rows = [items]

            elif isinstance(items, list):

                src_rows = items

            else:

                src_rows = []



            rows = []

            for it in src_rows:

                if not isinstance(it, dict):

                    continue



                region_join = f"{_norm(it.get('prtcptLmtRgnNm'))}{_norm(it.get('dmndInsttLocplcNm'))}"



                row = {

                    "공고업종코드": ind,

                    "공고번호": _norm(it.get("bidNtceNo")),

                    "차수": _norm(it.get("bidNtceOrd")),

                    "공고명": _norm(it.get("bidNtceNm")),

                    "입찰마감일시": _norm(it.get("bidClseDt")),

                    "공동도급지역": _norm(it.get("prtcptLmtRgnNm")),

                    "수요지역": _norm(it.get("dmndInsttLocplcNm")),

                    "원문": it,

                    "_region_concat": region_join,

                }

                rows.append(row)



            print(f"[HTTP] {API_BASE} ind={ind} count={len(rows)}")

            return rows



        except Exception as e:

            if tries >= retries:

                log(f"[ERR] fetch ind={ind} failed: {e}")

                return []

            time.sleep(1.2 * tries)





# ============================

# 필터 (현재는 업종만 사용)

# ============================

def filter_rows(rows):

    """

    - 업종: TARGET_INDS (6202, 0040, 0037, 0038, 0039)만 필터링

    - 지역은 현재 전국 허용 (추후 필요 시 조건 추가 가능)

    """

    filtered = []



    for r in rows:

        ind = _norm(r.get("공고업종코드"))

        if not ind:

            continue



        if ind in TARGET_INDS:

            filtered.append(r)



    print(

        f"[FILTER] 남은 공고(최종) {len(filtered)}건 "

        f"(전국, 업종 {','.join(TARGET_INDS)})"

    )

    return filtered





# ============================

# 엑셀 저장

# ============================

def save_excel(rows):

    if not rows:

        return None



    now = datetime.now().strftime("%Y%m%d_%H%M")

    path = OUTDIR / f"입찰공고_{now}.xlsx"



    def order(row):

        base = {

            "공고업종코드": row.get("공고업종코드", ""),

            "공고번호": row.get("공고번호", ""),

            "차수": row.get("차수", ""),

            "공고명": row.get("공고명", ""),

            "입찰마감일시": row.get("입찰마감일시", ""),

            "공동도급지역": row.get("공동도급지역", ""),

            "수요지역": row.get("수요지역", ""),

        }

        base["원문"] = json.dumps(row.get("원문", {}), ensure_ascii=False)

        return base



    df = pd.DataFrame([order(r) for r in rows])

    df.to_excel(path, index=False)

    log(f"[SAVE] {path}")

    return str(path)





# ============================

# 오래된 엑셀 자동 백업

# ============================

def backup_old_excels(base_dir: Path = OUTDIR, keep_days: int = 1):

    """

    base_dir 안의 *.xlsx 중

    '오늘 기준 keep_days일 이전' 파일을

    backup/YYYYMMDD/ 하위 폴더로 이동.

    """

    try:

        today = datetime.now().date()

        cutoff = today - timedelta(days=keep_days)



        backup_root = base_dir / "backup"

        backup_root.mkdir(parents=True, exist_ok=True)



        for f in base_dir.glob("*.xlsx"):

            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()

            if mtime <= cutoff:

                dst_dir = backup_root / mtime.strftime("%Y%m%d")

                dst_dir.mkdir(parents=True, exist_ok=True)

                dst = dst_dir / f.name

                log(f"[BACKUP] move {f} -> {dst}")

                f.replace(dst)

    except Exception as e:

        log(f"[WARN] backup_old_excels failed: {e}")





# ============================

# 알리고 관련

# ============================

def _alligo_ready():

    """

    알리고 발송 가능 여부(환경변수 + 모듈) 점검

    env: /etc/seri-main-send.env 의 ALLIGO_ID, ALLIGO_APIKEY 사용

    """

    if Alligo is None:

        log("[SEND] Alligo 모듈이 없어 발송 skip")

        return False



    need = ["ALLIGO_ID", "ALLIGO_APIKEY"]

    miss = [k for k in need if not os.getenv(k)]

    if miss:

        log(f"[SEND] 환경변수 누락으로 발송 skip: {', '.join(miss)}")

        return False



    return True





def _mk_subject(row):

    return clamp_len(row.get("공고명", ""), 40)





def _mk_message(row):

    bid_no = _norm(row.get("공고번호"))

    title = _norm(row.get("공고명"))

    close = _norm(row.get("입찰마감일시"))

    region = _norm(row.get("공동도급지역") or row.get("수요지역") or "")



    lines = [

        "[세리공영] 입찰 알림",

        f"공고번호: {bid_no}",

        f"공고명: {title}",

        f"입찰마감: {close}",

    ]

    if region:

        lines.append(f"지역: {region}")

    return "\n".join(lines)





def _mk_alt_message(row):

    # 대체문자는 동일 내용 사용

    return _mk_message(row)


def ensure_tables():
    """
    kakao.ntcedata, kakao.sendlog 테이블이 없으면 생성
    (이미 있으면 아무 일도 안 함)
    """
    sql1 = """CREATE TABLE IF NOT EXISTS ntcedata (
      bid_no      varchar(40) NOT NULL,
      bid_ord     varchar(8)  NOT NULL DEFAULT '0',
      ind         varchar(10) DEFAULT NULL,
      ind_nm      varchar(50) DEFAULT NULL,
      title       varchar(255) DEFAULT NULL,
      region_text text,
      raw_json    json DEFAULT NULL,
      created_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (bid_no, bid_ord)
    ) CHARSET=utf8mb4;"""

    sql2 = """CREATE TABLE IF NOT EXISTS sendlog (
      bid_no   varchar(40) NOT NULL,
      bid_ord  varchar(8)  NOT NULL DEFAULT '0',
      receiver varchar(20) NOT NULL,
      tpl      varchar(32) NOT NULL DEFAULT 'TB_0485',
      sent_at  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (bid_no, bid_ord, receiver, tpl)
    ) CHARSET=utf8mb4;"""

    cn = _db_conn()
    try:
        with cn.cursor() as c:
            c.execute(sql1)
            c.execute(sql2)
    finally:
        cn.close()



# ============================

# 알림톡 발송 + recvdata 업서트

# ============================

def send_alk(rows, receivers=None):
    """
    알림톡 발송 + 중복 방지 + recvdata 업서트

    - rows : 이미 filter_rows() 로 전국/업종 필터된 공고 목록
    - receivers : 기본은 상단 RECEIVERS 사용
    """

    # 수신번호 설정 (기본은 RECEIVERS, 실제 발송 대상은 대표번호 1개)
    base_receivers = receivers or RECEIVERS
    send_targets = [base_receivers[0]]  # 예: ['REDACTED_PRIVATE_VALUE']

    if not rows:
        log("[ALIMTALK] no rows to send")
        return 0

    # 알리고 환경변수 체크
    if not _alligo_ready():
        log(f"[ALIMTALK] sent=0/{len(rows)} (env missing)")
        return 0

    # DB: kakao.ntcedata / kakao.sendlog 테이블 준비
    ensure_tables()

    # Alligo 객체 생성 (ALLIGO_ID, ALLIGO_APIKEY 사용)
    a = Alligo(
        os.getenv("ALLIGO_ID"),
        os.getenv("ALLIGO_APIKEY"),
    )

    sent_cnt = 0

    # kakao.recvdata upsert 를 위해 별도 연결 사용
    conn = get_db_conn()

    try:
        for r in rows:
            # 공고번호 / 차수 추출
            bid_no = str(
                r.get("공고번호")
                or r.get("bidNtceNo")
                or ""
            ).strip()
            bid_ord = str(
                r.get("차수")
                or r.get("bidNtceOrd")
                or ""
            ).strip()

            if not bid_no:
                print(f"[SEND][SKIP] bid_no empty row: {r}")
                continue

            # recvdata : 수신번호 기록 (대표번호 + 전체 리스트 CSV)
            try:
                recv_upsert_db(conn, bid_no, bid_ord, send_targets)
            except Exception as e:
                print(f"[RECVDB][ERR] {bid_no}/{bid_ord}: {e}")

            # 템플릿 메시지 구성
            subj = _mk_subject(r)
            msg  = _mk_message(r)
            alt  = _mk_alt_message(r)

            for ph in send_targets:
                # 이미 보낸 적 있는지 sendlog 로 중복 방지
                if already_sent(bid_no, bid_ord, ph, TEMPLATE_CODE):
                    print(f"[DEDUP] skip already sent {bid_no}/{bid_ord} -> {ph}")
                    continue

                try:
                    # 알리고 응답 확인
                    resp = a.sendTalk(
                        ph,
                        TEMPLATE_CODE,
                        subj,
                        msg,
                        alt,
                    )

                    # resp 가 dict 라고 가정하고 code 체크
                    code = None
                    msg_text = None
                    if isinstance(resp, dict):
                        code = resp.get("code")
                        msg_text = resp.get("message")

                    if code != 0:
                        print(f"[SEND][FAIL-LOGIC] {bid_no}/{bid_ord} -> {ph}: code={code}, msg={msg_text}")
                        # 실패한 건 sendlog 에 기록하지 않음
                        continue

                    # 여기까지 왔으면 실제 발송 성공
                    mark_sent(bid_no, bid_ord, ph, TEMPLATE_CODE)
                    sent_cnt += 1
                    print(f"[SEND][OK] {bid_no}/{bid_ord} -> {ph}")

                except Exception as e:
                    # 예외가 난 것도 실패로 간주 (sendlog 기록 X)
                    print(f"[SEND][ERR] {bid_no}/{bid_ord} -> {ph}: {e}")

    finally:
        conn.close()

    log(f"[ALIMTALK] sent={sent_cnt}/{len(rows)}")
    return sent_cnt


   
# ============================

# main()

# ============================

def main():

    # 실행할 때마다 하루 지난 엑셀은 백업 폴더로 이동

    backup_old_excels(OUTDIR, keep_days=1)



    import argparse



    p = argparse.ArgumentParser()

    p.add_argument("--days", type=int, default=1, help="조회 기간(일)")

    p.add_argument("--ind", action="append", help="업종코드(여러 번 지정 가능)")

    p.add_argument("--no-send", action="store_true", help="알림톡 발송 생략")

    args = p.parse_args()



    days = max(1, args.days or 1)

    end = datetime.now()

    begin = end - timedelta(days=days)

    bgn_dt = begin.strftime("%Y%m%d%H%M")

    end_dt = end.strftime("%Y%m%d%H%M")



    inds = args.ind or TARGET_INDS



    all_rows = []

    for ind in inds:

        log(f"[FETCH] ind={ind} from {bgn_dt} to {end_dt}")

        part = fetch_ind(ind, bgn_dt, end_dt)

        all_rows.extend(part)



    # 엑셀 저장용 1차 필터

    rows = filter_rows(all_rows)

    save_excel(rows)



    if args.no_send:

        log("[DONE] main_send finished. (no-send)")

        return



        # 발송 + recvdata 업서트
    send_alk(rows, RECEIVERS)

    log("[DONE] main_send finished.")





if __name__ == "__main__":

    main()


