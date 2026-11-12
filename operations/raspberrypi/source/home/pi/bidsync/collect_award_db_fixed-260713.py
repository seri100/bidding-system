"""
낙찰정보 DB 수집 스크립트 v2
- params 대신 URL 직접 조합으로 이중인코딩 방지
"""

import requests
import pymysql
import time
from datetime import datetime, timedelta

API_KEY  = "REDACTED_PRIVATE_VALUE"
BASE_URL = "http://apis.data.go.kr/1230000/as/ScsbidInfoService"
ENDPOINTS = {
    "물품": "getScsbidListSttusThng",
    "공사": "getScsbidListSttusCnstwk",
}

DB_CONFIG = dict(
    host="192.168.0.250", port=3306,
    user="seri825", password="REDACTED_PRIVATE_VALUE",
    db="seridb", charset="utf8"
)

START_DATE = datetime(2024, 5, 24)
END_DATE   = datetime.today()
CHUNK_DAYS = 7
ROWS_PER_PAGE = 100
SLEEP_SEC  = 0.8

def safe_int(v):
    try:    return int(v) if v not in (None, "", "None") else 0
    except: return 0

def safe_float(v):
    try:    return float(v) if v not in (None, "", "None") else 0.0
    except: return 0.0

def safe_str(v, maxlen=50):
    if v is None: return None
    return str(v)[:maxlen]

def parse_dt(v):
    if not v:
        return None
    s = str(v).strip()
    for fmt, n in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
        ("%Y%m%d%H%M", 12),
        ("%Y%m%d", 8),
    ):
        try:
            return datetime.strptime(s[:n], fmt)
        except:
            pass
    return None

def fetch_all(endpoint, bgn, end):
    """URL 직접 조합으로 API 호출 (이중인코딩 방지)"""
    results, page = [], 1
    while True:
        url = (
            f"{BASE_URL}/{endpoint}"
            f"?serviceKey=REDACTED_PRIVATE_VALUE"
            f"&numOfRows={ROWS_PER_PAGE}"
            f"&pageNo={page}"
            f"&inqryDiv=1"
            f"&inqryBgnDt={bgn.strftime('%Y%m%d%H%M')}"
            f"&inqryEndDt={end.strftime('%Y%m%d')}2359"
            f"&type=json"
        )
        try:
            r = requests.get(url, timeout=20)
            if not r.text.strip():
                break
            data = r.json()
            body  = data["response"]["body"]
            total = int(body.get("totalCount", 0))
            items = body.get("items", [])
            if not items:
                break
            if isinstance(items, dict):
                items = [items]
            results.extend(items)
            if page * ROWS_PER_PAGE >= total:
                break
            page += 1
            time.sleep(SLEEP_SEC)
        except Exception as e:
            print(f"    API 오류 (page {page}): {e}")
            break
    return results

def item_to_row(item, btype):
    return (
        safe_str(item.get("bidNtceNo"), 35),
        safe_str(item.get("bidNtceNm"), 100),
        parse_dt(item.get("rlOpengDt")) or parse_dt(item.get("opengDt")) or parse_dt(item.get("fnlSucsfDate")),
        safe_str(item.get("ntcelnsttCd") or item.get("dminsttCd"), 35) or "",
        safe_str(item.get("ntcelnsttNm") or item.get("dminsttNm"), 50),
        safe_str(item.get("dminsttCd"), 35) or "",
        safe_str(item.get("dminsttNm"), 50),
        safe_int(item.get("prtcptCnum")),
        safe_str(item.get("bidwinnrBizno"), 35),
        safe_str(item.get("bidwinnrNm"), 50),
        safe_str(item.get("bidwinnrCeoNm"), 50),
        safe_int(item.get("sucsfbidAmt")) or 0,
        safe_float(item.get("sucsfbidRate")) or 0.0,
        safe_int(item.get("bssamt")) or 0,
        safe_int(item.get("plnprc")) or 0,
        safe_str(item.get("bidwinrSlctnAplBssCntnts"), 50),
        safe_str(item.get("exctvNm"), 50) or "",
        safe_int(item.get("indstrytyCd")),
        safe_str(item.get("mainCnsttyNm"), 50) or btype,
        safe_str(item.get("indstrytyNm"), 50),
    )

INSERT_SQL = """
INSERT INTO final_insert
  (bidNtceNo, bidNtceNm, opengDt,
   ntcelnsttCd, ntcelnsttNm,
   dminsttCd, dminsttNm,
   prtcptCnum,
   bidwinnrBizno, bidwinnrNm, bidwinnrCeoNm,
   sucsfbidAmt, sucsfbidRate,
   bssamt, plnprc,
   bidwinrSlctnAplBssCntnts, exctvNm,
   indstrytyCd, mainCnsttyNm, indstrytyNm)
VALUES (%s,%s,%s, %s,%s, %s,%s, %s, %s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s,%s)
ON DUPLICATE KEY UPDATE
  bidNtceNm=VALUES(bidNtceNm),
  opengDt=VALUES(opengDt),
  ntcelnsttCd=VALUES(ntcelnsttCd),
  ntcelnsttNm=VALUES(ntcelnsttNm),
  dminsttCd=VALUES(dminsttCd),
  dminsttNm=VALUES(dminsttNm),
  prtcptCnum=VALUES(prtcptCnum),
  bidwinnrBizno=VALUES(bidwinnrBizno),
  bidwinnrNm=VALUES(bidwinnrNm),
  bidwinnrCeoNm=VALUES(bidwinnrCeoNm),
  sucsfbidAmt=VALUES(sucsfbidAmt),
  sucsfbidRate=VALUES(sucsfbidRate),
  bssamt=VALUES(bssamt),
  plnprc=VALUES(plnprc),
  bidwinrSlctnAplBssCntnts=VALUES(bidwinrSlctnAplBssCntnts),
  exctvNm=VALUES(exctvNm),
  indstrytyCd=VALUES(indstrytyCd),
  mainCnsttyNm=VALUES(mainCnsttyNm),
  indstrytyNm=VALUES(indstrytyNm)
"""

def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur  = conn.cursor()

    cur.execute("SELECT MAX(opengDt) FROM final_insert")
    print(f"DB 현재 최신 opengDt: {cur.fetchone()[0]}")
    print(f"수집 기간: {START_DATE.date()} ~ {END_DATE.date()}")
    print()

    total_inserted = 0
    chunk = timedelta(days=CHUNK_DAYS)
    bgn   = START_DATE

    while bgn <= END_DATE:
        end = min(bgn + chunk - timedelta(days=1), END_DATE)

        for btype, ep in ENDPOINTS.items():
            items = fetch_all(ep, bgn, end)
            if not items:
                print(f"  [{btype}] {bgn.date()}~{end.date()}: 0건")
                time.sleep(SLEEP_SEC)
                continue

            rows = []
            for it in items:
                try:    rows.append(item_to_row(it, btype))
                except: pass

            try:
                cur.executemany(INSERT_SQL, rows)
                conn.commit()
                cnt = cur.rowcount
                print(f"  [{btype}] {bgn.date()}~{end.date()}: "
                      f"API {len(items)}건 → INSERT {cnt}건")
                total_inserted += cnt
            except Exception as e:
                conn.rollback()
                print(f"  [{btype}] DB 오류: {e}")

            time.sleep(SLEEP_SEC)

        bgn += chunk

    cur.close()
    conn.close()
    print(f"\n완료! 총 {total_inserted:,}건 신규 입력")

if __name__ == "__main__":
    main()




