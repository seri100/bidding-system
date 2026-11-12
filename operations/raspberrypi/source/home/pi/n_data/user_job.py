
# -*- coding: utf-8 -*-

import os

import json

import sqlite3

from datetime import datetime

from kakao_send_tb0485 import send_for_item



DB_PATH = "/home/pi/n_data/state.db"



# === 신규 공고 중복 방지 ===

def _dedup_new(conn, items):

    deduped = []

    cur = conn.cursor()

    for it in items:

        bid_no = it.get("bidNtceNo")

        bid_ord = it.get("bidNtceOrd")

        cur.execute("SELECT 1 FROM sent_log WHERE bid_no=? AND bid_ord=?", (bid_no, bid_ord))

        if not cur.fetchone():

            deduped.append(it)

    return deduped





# === 필드 매핑 함수 (TB_0485 템플릿에 맞춤) ===

def map_for_tb0485(item):

    return {

        "bid_no": item.get("bidNtceNo", ""),

        "bid_name": item.get("bidNtceNm", ""),

        "license": item.get("indstrytyNm", ""),

        "amount": item.get("presmptPrce", ""),

        "limit_type": item.get("jntcontrctDutyRgnNm1", ""),

    }





# === 메인 사용자 작업 ===

def run_job(cfg):

    print(f"[USERJOB] Start, cfg={cfg}")

    ONLY_TO = cfg["ONLY_TO"]

    ALLOW_PROD_SEND = cfg["ALLOW_PROD_SEND"]



    # 1) 나라장터 API 결과 (임시 하드코딩 예시)

    items = [

        {

            "bidNtceNo":"R25BK01116963",

            "bidNtceOrd":"000",

            "bidNtceNm":"영천스타밸리 지식산업혁신센터 신축공사(소방)",

            "presmptPrce":"1382886000",

            "jntcontrctDutyRgnNm1":"경상북도",

            "rgnDutyJntcontrctRt":"49.0"

        }

    ]



    # 2) DB 연결 및 중복 제거

    conn = sqlite3.connect(DB_PATH)

    deduped = _dedup_new(conn, items)

    print(f"[USERJOB] fetched={len(items)} new_only={len(deduped)}")



    # 3) 발송 루프

    for it in deduped:

        mapped = map_for_tb0485(it)

        for phone in ONLY_TO:

            r = send_for_item(receiver=phone, fields=mapped, dry_run=not ALLOW_PROD_SEND)

            print(f"[SEND RESULT] → {phone}: {r}")

            _save_sent(conn, it, phone, r, ALLOW_PROD_SEND)



    conn.close()





# === DB 기록 ===

def _save_sent(conn, item, phone, res, prod):

    cur = conn.cursor()

    cur.execute("""

        INSERT INTO sent_log

        (bid_no, bid_ord, to_no, prod, sent_at)

        VALUES (?,?,?,?,?)

    """, (item["bidNtceNo"], item["bidNtceOrd"], phone, int(prod), datetime.now().isoformat()))

    conn.commit()

