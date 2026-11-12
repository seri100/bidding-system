
# -*- coding: utf-8 -*-

import json



import pymysql



from .utils import log

from .utils import _norm

from .config import MIN_ESTIMATE_FOR_TARGET  # 사용 안 해도 괜찮음



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

            c.execute(sql, (bid_no, bid_ord, ind, title, region,

                            json.dumps(raw, ensure_ascii=False)))

    except Exception as e:

        log(f"[NTCEDB][ERR] {bid_no}/{bid_ord}: {e}")


