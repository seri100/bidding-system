
# -*- coding: utf-8 -*-

"""

outbox_shadow.py

- Shadow mode: DB에 "기록만" 남긴다.

- DB 오류/접속 실패/중복 등 어떤 문제가 있어도 발송 흐름을 절대 막지 않는다.

"""



import os

import pymysql





def normalize_bid_key(bid_key: str) -> str:

    """

    예) "R26BK01262602 - 000" -> "R26BK01262602-000"

    """

    if not isinstance(bid_key, str):

        return ""

    k = bid_key.strip()

    # 공백 제거 + 흔한 하이픈 변형 처리

    k = k.replace(" ", "").replace("–", "-").replace("—", "-")

    return k





def make_send_key(bid_key: str, template_id: str, receiver: str) -> str:

    bid_key_n = normalize_bid_key(bid_key)

    t = (template_id or "UNKNOWN").strip()

    r = (receiver or "").strip().replace(" ", "")

    return f"{bid_key_n}|{t}|{r}"





def _get_db_cfg():

    """

    기본값은 너희 운영에서 쓰던 값(seri/seri825, kakao)로 둠.

    원하면 환경변수로 바꿀 수 있음:

      DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME

    """

    return {

        "host": os.getenv("DB_HOST", "REDACTED_PRIVATE_VALUE"),

        "port": int(os.getenv("DB_PORT", "3306")),

        "user": os.getenv("DB_USER", "seri"),

        "password": os.getenv("DB_PASS", "seri825"),

        "database": os.getenv("DB_NAME", "kakao"),

        "charset": "utf8mb4",

        "autocommit": True,

        "cursorclass": pymysql.cursors.DictCursor,

    }





def db_outbox_shadow(send_key: str, bid_key: str, template_id: str, receiver: str) -> bool:

    """

    True  -> DB에 신규로 기록됨

    False -> 이미 있었음(중복) 또는 DB 오류(Shadow이므로 무시)

    """

    try:

        cfg = _get_db_cfg()

        conn = pymysql.connect(**cfg)

        try:

            with conn.cursor() as cur:

                sql = """

                INSERT IGNORE INTO send_outbox

                (send_key, bid_key, template_id, receiver, status, try_count)

                VALUES (%s, %s, %s, %s, 'NEW', 0)

                """

                cur.execute(sql, (send_key, normalize_bid_key(bid_key), template_id, receiver))

                # rowcount == 1이면 새로 들어감, 0이면 이미 존재

                return (cur.rowcount == 1)

        finally:

            conn.close()

    except Exception:

        # Shadow 모드: 어떤 오류든 발송 흐름을 막지 않음

        return False

