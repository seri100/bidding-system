
#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import os, time
print('[OUTBOX][BOOT]', time.strftime('%F %T'), 'USER='+os.getenv('USER','?'), 'DB_HOST='+str(os.getenv('DB_HOST')), 'DB_USER='+str(os.getenv('DB_USER')), 'DB_PASS_SET='+( 'Y' if os.getenv('DB_PASS') else 'N'), flush=True)




"""

outbox_sender.py

- DB(kakao.send_outbox)에서 status=NEW 레코드를 가져와 알림톡 발송

- main_send.py는 건드리지 않음 (DB-only 규칙)

- status 전이: NEW -> SENDING -> (SENT | FAILED)

- 중복방지: send_outbox.send_key UNIQUE + row-level lock/claim

"""



import os
import hashlib

import traceback
import time
import importlib

from datetime import datetime



import pymysql

import sys, traceback


# ------------------------------------------------------------

# TB_0485 safe wrapper: send_for_item(receiver, fields, dry_run)

# - payload/fields가 dict가 아니어도 .get() 크래시 방지

# - outbox_sender 어디서 호출하든 시그니처를 강제 고정

# ------------------------------------------------------------

def _tb0485_send(receiver, payload, dry_run=False):

    from kakao_send_tb0485 import send_for_item as _send_for_item



    fields = payload

    if not isinstance(fields, dict):

        if fields is None:

            fields = {}

        else:

            fields = {"_raw": str(fields)}



    # 선택: amount_str가 없으면 최소 보정(있으면 그대로 사용)

    fields.setdefault("amount_str", fields.get("amount") or fields.get("bssamt") or "")



    return _send_for_item(receiver, fields, dry_run=dry_run)





def _excepthook(exctype, value, tb):
    try:
        print('[OUTBOX][FATAL]', exctype.__name__, str(value), flush=True)
        traceback.print_tb(tb)
        traceback.print_exception(exctype, value, tb)
    except Exception:
        pass
sys.excepthook = _excepthook




DB_HOST = os.getenv("DB_HOST", "REDACTED_PRIVATE_VALUE")

DB_PORT = int(os.getenv("DB_PORT", "3306"))

DB_NAME = os.getenv("DB_NAME", "kakao")




# ------------------------------------------------------------

# send_history 기록 (outbox_sender 자동 기록 패치)

# ------------------------------------------------------------

def _safe_str(x, maxlen=255):

    try:

        if x is None:

            return ""

        x = str(x).strip()

        return x[:maxlen]

    except Exception:

        return ""



def _hash64(x: str) -> str:

    import hashlib as _hh

    return _hh.sha256((x or "").encode("utf-8", errors="ignore")).hexdigest()



def _write_send_history(cur, bid_key, receiver, status, note="", bid_row=None, src="outbox_sender"):

    """

    kakao.send_history columns (예상):

      created_at(auto), src, bid_key, ind_code, region, recv_phone, msg_hash, status, note

    """

    def _safe(x, n=255):

        try:

            if x is None:

                return ""

            return str(x).strip()[:n]

        except Exception:

            return ""



    ind_code = ""

    region = ""

    try:

        if isinstance(bid_row, dict):

            ind_code = _safe(

                bid_row.get("공고업종코드")

                or bid_row.get("indstrytyCd")

                or bid_row.get("ind_code")

                or "",

                10,

            )

            region = _safe(bid_row.get("대표지역") or bid_row.get("region") or "", 20)

    except Exception:

        pass



    msg_hash = _hash64(f"{bid_key}|{receiver}|{status}")



    cur.execute(

        """

        INSERT INTO send_history (src, bid_key, ind_code, region, recv_phone, msg_hash, status, note)

        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)

        """,

        (_safe(src, 30), _safe(bid_key, 200), ind_code, region, _safe(receiver, 20),

         msg_hash, _safe(status, 20), _safe(note, 255)),

    )



DB_USER = os.getenv("DB_USER", "seri")

DB_PASS = os.getenv("DB_PASS", "")



POLL_SEC = float(os.getenv("OUTBOX_POLL_SEC", "1.0"))

BATCH = int(os.getenv("OUTBOX_BATCH", "1"))

MAX_TRIES = int(os.getenv("OUTBOX_MAX_TRIES", "3"))


# ------------------------------------------------------------

# Receiver routing rules (forced by ind_code + region)

# ------------------------------------------------------------



# allowed industry codes

VALID_INDS = {"0037","0038","0039","0040","6202"}



# default routing for 0038/0039/0040/6202

ROUTE_OTHERS = {

    "전국": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "세종": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "충북": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "대구": ["REDACTED_PRIVATE_VALUE"],

    "경북": ["REDACTED_PRIVATE_VALUE"],

}



# special routing for 0037 (전기공사)

ROUTE_0037 = {

    "전국": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "세종": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "충북": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "대구": ["REDACTED_PRIVATE_VALUE"],

    "경북": ["REDACTED_PRIVATE_VALUE"],

}



def _normalize_region(x: str) -> str:

    if not isinstance(x, str):

        return ""

    t = x.strip()

    # 흔한 표기 흡수 (필요하면 더 추가)

    if t in ("전국", "전체", "전국입찰", "전국가능"):

        return "전국"

    if "세종" in t:

        return "세종"

    if "충북" in t or "충청북도" in t:

        return "충북"

    if "대구" in t:

        return "대구"

    if "경북" in t or "경상북도" in t:

        return "경북"

    return t



def _pick_receivers(ind_code: str, region: str):

    ic = (ind_code or "").strip()

    rg = _normalize_region(region or "")

    if ic not in VALID_INDS:

        return []

    table = ROUTE_0037 if ic == "0037" else ROUTE_OTHERS

    return table.get(rg, [])






# -----------------------------

# sender import (여러 후보를 자동 시도)

# -----------------------------

def load_sender():

    candidates = [

        ("kakao_send_tb0485", "send_for_item"),

        ("kakao_send_tb0485", "send_kakao"),     # 혹시 다른 이름

        ("kakao_send", "send_for_item"),

        ("alligo", "send_for_item"),

    ]

    for mod, fn in candidates:

        try:

            m = importlib.import_module(mod)

            f = getattr(m, fn, None)

            if callable(f):

                return f, f"{mod}.{fn}"

        except Exception:

            pass



    # 마지막으로 main_send 안에 래핑된 sender가 있는지 시도

    try:

        m = importlib.import_module("main_send")

        # 흔한 이름들 후보

        for name in ("kakao_send_for_item", "send_for_item", "wrapped_sender"):

            f = getattr(m, name, None)

            if callable(f):

                return f, f"main_send.{name}"

    except Exception:

        pass



    raise RuntimeError("sender function import 실패: _tb0485_send 등 확인 필요")



# -----------------------------

# DB helpers

# -----------------------------


# -----------------------------
# payload normalizer (sender expects dict with .get)
# -----------------------------

    if not isinstance(d, dict):

        return d

    bk = d.get("bid_key")

    if isinstance(bk, str) and "-" in bk:

        a, b = bk.split("-", 1)

        d.setdefault("bid_no", a)

        d.setdefault("bid_ord", b)

    return d

    # sender(kakao_send_tb0485 등)는 payload.get(...)을 사용함
    # payload가 str이면 'str has no attribute get' 발생 -> dict로 포장
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    return {'bid_key': str(x)}



# -----------------------------

# payload normalizer (sender expects dict with .get)

# -----------------------------

def _normalize_payload_for_sender(x):

    if x is None:

        return {}

    if isinstance(x, dict):

        return x

    return {"bid_key": str(x)}



# -----------------------------

# enrich payload keys

# -----------------------------

def _enrich_payload_keys(d):

    if not isinstance(d, dict):

        return d

    bk = d.get("bid_key")

    if isinstance(bk, str) and "-" in bk:

        a, b = bk.split("-", 1)

        d.setdefault("bid_no", a)

        d.setdefault("bid_ord", b)

    return d



def db_connect():

    return pymysql.connect(

        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,

        db=DB_NAME, charset="utf8mb4", autocommit=False,

        cursorclass=pymysql.cursors.DictCursor

    )



def now_str():

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def log(msg):

    print(f"[{now_str()}] {msg}", flush=True)





def recover_stuck_sending(conn, stuck_seconds: int = 180):

    """

    SENDING 상태가 오래 지속된 건을 NEW로 되돌려 재시도 가능하게 한다.

    - % 포맷 문자가 들어가는 SQL(예: DATE_FORMAT '%Y')을 사용하지 않는다.

    - note는 고정 문자열로 기록한다.

    """

    try:

        with conn.cursor() as cur:

            # 너무 오래된 SENDING을 NEW로 복구

            # (NOW() - INTERVAL N SECOND) 기준

            cur.execute(

                """

                UPDATE send_outbox

                   SET status='NEW',

                       last_error='recovered from stuck SENDING',

                       updated_at=NOW()

                 WHERE status='SENDING'

                   AND try_count < %s

                   AND updated_at < (NOW() - INTERVAL %s SECOND)

                """,

                (int(MAX_TRIES), int(stuck_seconds),)

            )

        conn.commit()

    except Exception as e:

        # recover 실패는 치명적이면 안 됨: 로그만 남기고 계속 진행

        try:

            log(f"[OUTBOX][WARN] recover_stuck_sending failed: {e}")

        except Exception:

            pass

        try:

            conn.rollback()

        except Exception:

            pass






# ============================================================

# MAIN LOOP (added)

# ============================================================

def _force_payload_dict(x):

    """

send_fn(_normalize_payload_for_sender(_tb0485_send 등))

    payload가 str이면 최대한 dict로 변환해서 반환.

    """

    if isinstance(x, dict):

        return x

    if x is None:

        return {}

    # bytes -> str

    if isinstance(x, (bytes, bytearray)):

        try:

            x = x.decode("utf-8", "ignore")

        except Exception:

            x = str(x)



    if isinstance(x, str):

        t = x.strip()

        # JSON 형태

        if (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]")):

            try:

                import json

                obj = json.loads(t)

                if isinstance(obj, dict):

                    return obj

                return {"_raw": obj}

            except Exception:

                pass

        # key=value&key2=value2 형태

        if ("=" in t) and ("&" in t):

            try:

                from urllib.parse import parse_qs

                q = parse_qs(t, keep_blank_values=True)

                return {k: (v[0] if isinstance(v, list) and v else "") for k, v in q.items()}

            except Exception:

                pass

        # fallback

        return {"_raw": t}



    # 기타 타입은 문자열로 감싸서 전달

    return {"_raw": str(x)}







def _has_new(cur):

    cur.execute("SELECT receiver, 1 AS x FROM send_outbox WHERE status='NEW' LIMIT 1")

    row = cur.fetchone()

    return bool(row)



def _claim_one(conn):

    """

    NEW 1건을 안전하게 가져와 SENDING으로 'claim'한다.

    - MySQL 8+ : SKIP LOCKED 사용 가능

    - 호환성 위해: 트랜잭션 + SELECT ... FOR UPDATE + 즉시 UPDATE 방식

    """

    with conn.cursor() as cur:

        # 1) NEW 1건 잠금

        cur.execute("""

            SELECT *

              FROM send_outbox

             WHERE status='NEW'

             ORDER BY id ASC

             LIMIT 1

             FOR UPDATE

        """)

        row = cur.fetchone()

        if not row:

            return None



        # 2) SENDING으로 전이 (claim)

        cur.execute("""

            UPDATE send_outbox

               SET status='SENDING',

                   updated_at=NOW(),

                   last_error=NULL

             WHERE id=%s AND status='NEW'
                   AND try_count < %s

        """, (row["id"], int(MAX_TRIES)))

        # update가 1이 아니면 경쟁 발생 → None 처리

        if cur.rowcount != 1:

            return None



        return row



def _set_status(conn, row_id, status, last_error=None):

    with conn.cursor() as cur:

        cur.execute("""

            UPDATE send_outbox

               SET status=%s,

                   last_error=%s,

                   updated_at=NOW()

             WHERE id=%s

        """, (status, last_error, row_id))

    conn.commit()



def _bump_try_in_error(prev_err: str, n: int, err: str) -> str:

    prev = (prev_err or "").strip()

    base = f"try={n}/{MAX_TRIES} err={_safe_str(err, 180)}"

    if not prev:

        return base

    # 너무 길어지지 않게

    combined = (prev + " | " + base).strip()

    return combined[:240]



def _extract_fields(item: dict):

    # send_outbox 스키마 기준: receiver / bid_key / template_id 우선 사용

    bid_key = item.get("bid_key") or item.get("bidId") or ""

    receiver = item.get("receiver") or ""

    template_id = item.get("template_id") or item.get("templateId") or ""

    # sender에 넘길 payload: outbox row 자체(필요하면 sender가 bid_key로 상세를 조회)

    payload = item

    return str(bid_key), str(receiver), str(template_id), payload



def main():

    log("[OUTBOX][MAIN] start")

    conn = db_connect()



    try:

        # 0) stuck sending 복구

        recover_stuck_sending(conn, stuck_seconds=180)



        with conn.cursor() as cur:

            if not _has_new(cur):

                log("[OUTBOX][EMPTY] no NEW -> exit")

                conn.commit()

                return 0



        # sender 로드

        send_fn, send_name = load_sender()

        log(f"[OUTBOX][SENDER] {send_name}")



        processed = 0

        while processed < BATCH:

            try:

                conn.begin()

                item = _claim_one(conn)

                if not item:

                    conn.rollback()

                    break



                row_id = item["id"]

                prev_err = item.get("last_error") or ""

                tries = int(item.get('try_count') or 0) + 1



                bid_key, ind_code, region, payload = _extract_fields(item)
                # payload normalize: ensure dict for send_fn
                try:
                    # payload가 str이면 send_fn 내부 .get()에서 터질 수 있으니 dict로 보정
                    if isinstance(payload, str):
                        _ps = payload.strip()
                        if _ps.startswith('{') and _ps.endswith('}'):
                            import json
                            try:
                                payload = json.loads(_ps)
                            except Exception:
                                payload = {'_raw': payload}
                        else:
                            payload = {'_raw': payload}
                    # payload가 None이면 item을 쓰도록
                except Exception:
                    pass



                # 1) 최우선: DB(send_outbox.receiver) / payload 에 receiver가 있으면 그걸 사용
                receivers = []
                try:
                    _recv = None
                    # fallback: item/payload에 receiver가 없으면 DB에서 직접 조회
                    if not _recv:
                        try:
                            with conn.cursor() as _c:
                                _c.execute('SELECT receiver FROM send_outbox WHERE id=%s', (row_id,))
                                _r = _c.fetchone()
                            if isinstance(_r, dict):
                                _recv = _r.get('receiver')
                            elif _r:
                                _recv = _r[0]
                        except Exception:
                            pass
                    if isinstance(item, dict):
                        _recv = item.get('receiver') or item.get('recv') or item.get('hp')
                    if (not _recv) and isinstance(payload, dict):
                        _recv = payload.get('receiver') or payload.get('recv') or payload.get('hp')
                    if _recv:
                        receivers = [str(_recv)]
                except Exception:
                    pass

                # 2) 없으면 기존 규칙(업종/지역)으로 수신자 결정
                if not receivers:
                    receivers = _pick_receivers(ind_code, region)

                # 3) 그래도 없으면 SKIPPED
                if not receivers:
                    err = "no receiver in send_outbox row"
                    _set_status(conn, row_id, "SKIPPED", err)
                    try:
                        with db_connect() as c2:
                            with c2.cursor() as cur2:
                                _write_send_history(cur2, bid_key, "", "FAILED", note=err, bid_row={"ind_code": ind_code, "region": region})
                            c2.commit()
                    except Exception:
                        pass
                    processed += 1
                    continue
                # 실제 발송: receiver 별로 발송 시도 (1건이라도 성공하면 SENT로 처리)

                any_ok = False

                last_exc = None



                for r in receivers:

                    try:

                        # send_fn이 기대하는 인자 형태가 프로젝트마다 달라서 유연하게 시도

                        ok = None

                        # --- payload normalize: send_fn expects dict ---
                        try:
                            # payload가 dict가 아니면 item(dict)로 강제
                            if not isinstance(payload, dict):
                                if isinstance(item, dict):
                                    payload = item
                                else:
                                    payload = {}
                            # receiver를 payload에도 주입 (kakao_send_tb0485가 payload['receiver']를 볼 수 있게)
                            if isinstance(payload, dict) and r and not payload.get('receiver'):
                                payload['receiver'] = str(r)
                        except Exception:
                            pass
                        # --- end normalize ---

                        try:

                            payload_to_send = payload if payload is not None else item
                            payload_to_send = _force_payload_dict(payload_to_send)
                            if isinstance(payload_to_send, dict) and r and not payload_to_send.get('receiver'):
                                payload_to_send['receiver'] = str(r)
                            try:
                                _keys = list(payload_to_send.keys()) if isinstance(payload_to_send, dict) else []
                                _nested_key = ''
                                _nested_val = None
                                if isinstance(payload_to_send, dict):
                                    for _k in ('variables','vars','params','data','payload','template_args','tmpl','tpl','msg'):
                                        if _k in payload_to_send:
                                            _nested_key = _k
                                            _nested_val = payload_to_send.get(_k)
                                            break
                                log('[OUTBOX][DEBUG] row_id=%s p2s_type=%s keys=%s nested(%s)_type=%s nested_preview=%s p2s_preview=%s' % (
                                    row_id,
                                    type(payload_to_send).__name__,
                                    _keys[:30],
                                    _nested_key,
                                    (type(_nested_val).__name__ if _nested_val is not None else 'None'),
                                    (str(_nested_val)[:160] if _nested_val is not None else ''),
                                    (str(payload_to_send)[:220] if payload_to_send is not None else '')
                                ))
                            except Exception:
                                pass
                            ok = send_fn(_normalize_payload_for_sender(payload_to_send), r)

                        except TypeError:

                            ok = send_fn(_normalize_payload_for_sender(payload_to_send), receiver=r)

                        except Exception as e:

                            raise



                        if ok is None:

                            # send_fn이 성공/실패 반환 안 하는 구현 대비: 예외 없으면 성공으로 간주

                            ok = True



                        if ok:

                            any_ok = True

                            # 히스토리 기록

                            try:

                                with db_connect() as c2:

                                    with c2.cursor() as cur2:

                                        _write_send_history(cur2, bid_key, r, "SENT", note="ok", bid_row=payload if isinstance(payload, dict) else (item if isinstance(item, dict) else None))

                                    c2.commit()

                            except Exception:

                                pass

                        else:

                            # 실패도 히스토리

                            try:

                                with db_connect() as c2:

                                    with c2.cursor() as cur2:

                                        _write_send_history(cur2, bid_key, r, "FAILED", note="send_fn returned False", bid_row=payload if isinstance(payload, dict) else (item if isinstance(item, dict) else None))

                                    c2.commit()

                            except Exception:

                                pass



                    except Exception as e:

                        last_exc = e

                        # receiver 실패 히스토리

                        try:

                            with db_connect() as c2:

                                with c2.cursor() as cur2:

                                    _write_send_history(cur2, bid_key, r, "FAILED", note=_safe_str(e, 200), bid_row=payload if isinstance(payload, dict) else (item if isinstance(item, dict) else None))

                                c2.commit()

                        except Exception:

                            pass



                # 상태 결정

                if any_ok:

                    with conn.cursor() as cur:
                        cur.execute("UPDATE send_outbox SET status=%s, last_error=%s, sent_at=NOW(), updated_at=NOW() WHERE id=%s", ("SENT", None, row_id))
                    conn.commit()

                    log(f"[OUTBOX][SENT] id={row_id} bid_key={bid_key} receivers={len(receivers)}")

                else:

                    err = last_exc or "send failed"

                    # tries 기반 재시도 정책: MAX_TRIES 이하면 NEW로 되돌림, 초과면 FAILED

                    new_err = _bump_try_in_error(prev_err, tries, str(err))

                    with conn.cursor() as cur:
                        cur.execute("UPDATE send_outbox SET try_count=%s WHERE id=%s", (tries, row_id))
                    conn.commit()



                    if tries < MAX_TRIES:

                        _set_status(conn, row_id, "NEW", new_err)

                        log(f"[OUTBOX][RETRY] id={row_id} tries={tries}/{MAX_TRIES}")
                        log('[OUTBOX][EXC] ' + traceback.format_exc())

                    else:

                        _set_status(conn, row_id, "FAILED", new_err)

                        log(f"[OUTBOX][FAILED] id={row_id} tries={tries}/{MAX_TRIES}")
                        log('[OUTBOX][EXC] ' + traceback.format_exc())



                processed += 1



            except Exception as e:

                try:

                    conn.rollback()

                except Exception:

                    pass

                log(f"[OUTBOX][ERROR] loop error: {e}")
                traceback.print_exc()
            time.sleep(0.2)



        log(f"[OUTBOX][MAIN] done processed={processed}")

        return 0



    finally:

        try:

            conn.close()

        except Exception:

            pass





if __name__ == "__main__":

    raise SystemExit(main())



