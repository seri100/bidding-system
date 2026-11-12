# -*- coding: utf-8 -*-

"""

main_send_clean.py

- TEST 전용 새 구조

- PPSSrch + Cnstwk 병합 수집

- 공종/지역/추정가격 정규화

- 전국/지역 판단

- 수신자 결정

- 엑셀 저장

- --no-send 안전 실행

"""



import os



def _display_blank_as_none(v):

    """알림톡 표시용: None/공란/빈 값은 '없음'으로 표시"""

    if v is None:

        return "없음"

    t = str(v).strip()

    if not t or t in ("-", "None", "nan", "NaN"):

        return "없음"

    return t



import sys

import argparse

import re
import traceback
import shutil
import time

from pathlib import Path

from datetime import datetime, timedelta



import requests

import pandas as pd

from kakao_send_tb0485 import send_for_item as kakao_send_for_item
import os

import fcntl



_SENT_FILE = "/mnt/vol1/bid/n_data/sent_keys.txt"



def _sent_key(fields, phone=None):

    bid_no = (
        fields.get("bid_no")
        or fields.get("공고번호")
        or fields.get("bidNtceNo")
        or fields.get("입찰공고번호")
        or ""
    )

    bid_ord = (
        fields.get("bid_ord")
        or fields.get("차수")
        or fields.get("bidNtceOrd")
        or "000"
    )

    bid_no = str(bid_no or "").strip()
    bid_ord = str(bid_ord or "000").strip()

    if " - " in bid_no:
        parts = bid_no.split(" - ")
        bid_no = parts[0].strip()

        if len(parts) > 1:
            bid_ord = parts[1].strip()

    bid_no = bid_no.replace(" ", "")
    bid_ord = bid_ord.replace(" ", "") or "000"

    if not bid_no:
        return ""

    key = make_bid_key(bid_no, bid_ord)

    if phone:
        key = f"{key}|{phone}"

    return key


def is_already_sent(fields, phone=None):

    key = _sent_key(fields, phone)

    if not key:
        return False

    os.makedirs(os.path.dirname(_SENT_FILE), exist_ok=True)

    with open(_SENT_FILE, "a+", encoding="utf-8") as f:

        fcntl.flock(f, fcntl.LOCK_EX)

        f.seek(0)

        lines = set(x.strip() for x in f.readlines() if x.strip())

        fcntl.flock(f, fcntl.LOCK_UN)

    return key in lines


def mark_sent(fields, phone=None):

    key = _sent_key(fields, phone)

    if not key:
        return False

    os.makedirs(os.path.dirname(_SENT_FILE), exist_ok=True)

    with open(_SENT_FILE, "a+", encoding="utf-8") as f:

        fcntl.flock(f, fcntl.LOCK_EX)

        f.seek(0)

        lines = set(x.strip() for x in f.readlines() if x.strip())

        if key not in lines:
            f.write(key + "\n")
            f.flush()
            os.fsync(f.fileno())

        fcntl.flock(f, fcntl.LOCK_UN)

    return True





# ============================================================

# 환경

# ============================================================



TARGET_INDS = ["0037", "0038", "0039", "0040", "6202"]

MIN_BUDGET = 30_000_000



BASE_DIR = Path("/home/pi/n_data_test")

NAS_BASE = Path(os.environ.get("N_DATA_BASE", "/mnt/vol1/bid/n_data_test"))



API_KEY_FILE = NAS_BASE / "bid_api_key.txt"

RAW_DIR = NAS_BASE / "raw"

REPORT_DIR = NAS_BASE / "report"

SPLIT_DIR = NAS_BASE / "split"



for d in (RAW_DIR, REPORT_DIR, SPLIT_DIR):

    d.mkdir(parents=True, exist_ok=True)





def log(msg):

    print("[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)





def env_guard():

    env = os.environ.get("N_DATA_ENV", "").strip().upper()

    cwd = Path.cwd().resolve()



    expected = {

        "TEST": (Path("/home/pi/n_data_test"), "/mnt/vol1/bid/n_data_test"),

        "PROD": (Path("/home/pi/n_data"), "/mnt/vol1/bid/n_data"),

    }



    if env not in expected:

        print("[FATAL][ENV] N_DATA_ENV must be TEST or PROD", file=sys.stderr)

        sys.exit(2)



    exp_cwd, exp_nas = expected[env]



    if cwd != exp_cwd:

        print("[FATAL][ENV] cwd mismatch: now=%s expected=%s" % (cwd, exp_cwd), file=sys.stderr)

        sys.exit(2)



    if str(NAS_BASE) != exp_nas:

        print("[FATAL][ENV] N_DATA_BASE mismatch: now=%s expected=%s" % (NAS_BASE, exp_nas), file=sys.stderr)

        sys.exit(2)



    log("[ENV] OK: %s cwd=%s nas=%s" % (env, cwd, NAS_BASE))





def load_api_key():

    return API_KEY_FILE.read_text(encoding="utf-8").strip()





def ymdhm(dt):

    return dt.strftime("%Y%m%d%H%M")





# ============================================================

# API helpers

# ============================================================



def _items_from_json(data):

    """

    공공데이터 응답이 dict/list 섞여도 안전하게 item list 반환

    """

    if isinstance(data, list):

        return _flatten_items(data)



    if not isinstance(data, dict):

        return []



    body = data.get("response", {}).get("body", {})

    items_obj = body.get("items", [])



    if isinstance(items_obj, dict):

        item = items_obj.get("item", [])

    else:

        item = items_obj



    if isinstance(item, dict):

        return [item]



    if isinstance(item, list):

        return _flatten_items(item)



    return []





def _flatten_items(items):

    out = []

    if isinstance(items, dict):

        return [items]

    if not isinstance(items, list):

        return []



    for x in items:

        if isinstance(x, dict):

            out.append(x)

        elif isinstance(x, list):

            out.extend(_flatten_items(x))

    return out





def request_items(url, params, timeout=25):

    r = requests.get(url, params=params, timeout=timeout)

    r.raise_for_status()

    return _items_from_json(r.json())





def fetch_pages(url, api_key, bgn, end, extra_params=None, max_pages=30):

    rows = []

    extra_params = extra_params or {}



    for page in range(1, max_pages + 1):

        params = {

            "serviceKey": api_key,

            "pageNo": page,

            "numOfRows": 999,

            "inqryDiv": 1,

            "inqryBgnDt": bgn,

            "inqryEndDt": end,

            "type": "json",

        }

        params.update(extra_params)



        try:

            items = request_items(url, params)

        except Exception as e:

            log("[API][ERR] page=%s url=%s err=%s" % (page, url, e))

            break



        if not items:

            break



        rows.extend(items)



        if len(items) < 999:

            break



    return rows





# ============================================================

# 수집

# ============================================================



def collect_ppssrch(api_key, bgn, end):



    url = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"







    all_rows = []



    for ind in TARGET_INDS:



        rows = fetch_pages(



            url=url,



            api_key=api_key,



            bgn=bgn,



            end=end,



            extra_params={"indstrytyCd": ind},



        )



        for r in rows:



            r["_source_api"] = "PPSSrch"

            r["_query_indstrytyCd"] = ind



            # PPSSrch는 indstrytyCd로 조회해도 응답 row의 indstrytyCd가 비어 있을 수 있음.

            # 이 경우 조회에 사용한 ind 값을 공식 API 조회 근거로 보존한다.

            if not norm(r.get("indstrytyCd")):

                r["indstrytyCd"] = ind



            if not norm(r.get("indstrytyNm")):

                if ind == "0037":

                    r["indstrytyNm"] = "전기공사업"

                elif ind == "0038":

                    r["indstrytyNm"] = "정보통신공사업"

                elif ind == "0039":

                    r["indstrytyNm"] = "전문소방시설공사업"

                elif ind == "0040":

                    r["indstrytyNm"] = "일반소방시설공사업"

                elif ind == "6202":

                    r["indstrytyNm"] = "기계설비공사업"



        all_rows.extend(rows)







    log("[COLLECT] PPSSrch rows=%d" % len(all_rows))



    return all_rows







def collect_cnstwk(api_key, bgn, end):

    url = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"



    rows = fetch_pages(

        url=url,

        api_key=api_key,

        bgn=bgn,

        end=end,

        extra_params={},

    )



    for r in rows:

        r["_source_api"] = "Cnstwk"



    log("[COLLECT] Cnstwk rows=%d" % len(rows))

    return rows

def collect_prtcpt_region(api_key, bgn, end):
    url = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"

    rows = fetch_pages(
        url=url,
        api_key=api_key,
        bgn=bgn,
        end=end,
        extra_params={},
    )

    mp = {}
    for r in rows:
        key = _n_data_call_bid_key(r)
        region = norm(r.get("prtcptPsblRgnNm"))
        if not key or not region:
            continue

        if key not in mp:
            mp[key] = []

        if region not in mp[key]:
            mp[key].append(region)

    log("[COLLECT] PrtcptPsblRgn rows=%d keys=%d" % (len(rows), len(mp)))
    return mp

# ============================================================

# 정규화

# ============================================================



def norm(v):

    return "" if v is None else str(v).strip()





def to_int(v):

    s = norm(v).replace(",", "")

    if not s:

        return 0

    try:

        return int(float(s))

    except Exception:

        return 0







def is_cancel_notice(row):
    """
    취소공고/입찰취소/공고취소 건은 발송 제외.
    API 상태값, 공고종류, 공고명, 원문 dict까지 확인한다.
    """
    keys = [
        "bidNtceSttusNm", "bidNtceSttus", "ntceKindNm",
        "bidNtceNm", "공고명", "공고상태", "notice_status"
    ]

    texts = []

    for k in keys:
        v = row.get(k, "")
        if v is not None:
            texts.append(str(v))

    raw = row.get("원문")
    if isinstance(raw, dict):
        for k in keys:
            v = raw.get(k, "")
            if v is not None:
                texts.append(str(v))

    txt = " ".join(texts)
    cancel_words = ["취소", "공고취소", "입찰취소", "취소공고"]

    return any(w in txt for w in cancel_words)


def bid_key(row):

    bid = norm(row.get("bidNtceNo") or row.get("공고번호"))

    ord_ = norm(row.get("bidNtceOrd") or row.get("차수") or "000")

    if not ord_:

        ord_ = "000"

    return "%s-%s" % (bid, ord_) if bid else ""





def detect_industry(row):

    txt = " ".join([

        norm(row.get("indstrytyCd")),

        norm(row.get("indstrytyNm")),

        norm(row.get("mainCnsttyNm")),

        norm(row.get("cnsttyAccotShreRateList")),

        norm(row.get("bidNtceNm")),

    ])



    if "0037" in txt or ("전기공사업" in txt) or ("전기공사" in txt and "소방" not in txt):

        return "0037", "전기설비"



    if "전문소방시설공사업" in txt or "0040" in txt:

        return "0040", "전문소방시설공사업"



    if "일반소방시설공사업(기계)" in txt or "0038" in txt:

        return "0038", "일반소방시설공사업(기계)"



    if "일반소방시설공사업(전기)" in txt or "0039" in txt:

        return "0039", "일반소방시설공사업(전기)"



    if "소방" in txt:

        # 일반 구분이 없으면 전문소방으로 임시 분류

        return "0040", "전문소방시설공사업"



    # [INDUSTRY_GUARD] 공고명에 "기계설비"가 있어도 실제 업종제한/면허에 6202 또는 기계설비공사업이 없으면 6202로 보지 않는다.

    # 예: 건축공사업(0002), 토목건축공사업(0003)만 있는 복합공사명 "(건축, 기계설비)" 오발송 방지

    if (
        "6202" in txt
        or "기계설비공사업" in txt
        or "기계설비ㆍ가스공사업" in txt
    ):

        return "6202", "기계설비공사업"



    return "", ""





def extract_region(row):



    # 참가가능지역/참가제한지역을 우선 사용한다.

    # 공사현장지역(cnstrtsiteRgnNm)은 참가가능지역이 없을 때만 fallback으로 사용한다.

    primary = [

        norm(row.get("prtcptPsblRgnNm")),

        norm(row.get("prtcptLmtRgnNm")),

    ]



    primary = [

        v for v in primary

        if v and v.lower() not in ("nan", "none", "null")

    ]



    if primary:

        out = []

        for v in primary:

            if v not in out:

                out.append(v)

        return " | ".join(out)



    fallback = [

        norm(row.get("jntcontrctDutyRgnNm1")),

        norm(row.get("jntcontrctDutyRgnNm2")),

        norm(row.get("jntcontrctDutyRgnNm3")),

        norm(row.get("cnstrtsiteRgnNm")),

    ]



    fallback = [

        v for v in fallback

        if v and v.lower() not in ("nan", "none", "null")

    ]



    out = []

    for v in fallback:

        if v not in out:

            out.append(v)



    return " | ".join(out)




def alimtalk_estm_amount(row):

    """

    알림톡 표시용 금액.



    원칙:

    - 알림톡에는 API 원문 추정가격(presmptPrce/추정가격)을 그대로 표시한다.

    - 추정가격 * 1.1 보정은 하지 않는다.

    """



    def _num(v):

        try:

            import pandas as pd

            if pd.isna(v):

                return 0

        except Exception:

            pass



        if v is None:

            return 0



        t = str(v).replace(",", "").replace("원", "").strip()

        if not t:

            return 0



        try:

            return int(float(t))

        except Exception:

            return 0



    for k in [

        "presmptPrce",

        "추정가격",

        "mainCnsttyPresmptPrce",

        "presmpt_price",

        "추정가격금액",

    ]:

        v = _num(row.get(k))

        if v > 0:

            return v



    return 0





def presmpt_price(row):

    return to_int(

        row.get("presmptPrce")

        or row.get("mainCnsttyPresmptPrce")

        or row.get("추정가격")

        or 0

    )

def budget_amount(row):

    # 기초금액(bssamt/bdgtAmt)만 담당한다.

    # 추정가격(presmptPrce)은 presmpt_price()에서만 사용한다.

    return to_int(row.get("bssamt") or row.get("bdgtAmt") or row.get("기초금액") or 0)





def method_text(row):

    return norm(row.get("sucsfbidMthdNm") or row.get("낙찰방법세부기준"))





def decide_scope(row):

    m = method_text(row).replace(" ", "")

    p = presmpt_price(row)



    if "소액수의" in m:

        return "지역"

    if "10억원미만" in m or "10억미만" in m:

        return "지역"

    if "10억원이상" in m or "10억이상" in m:

        return "전국"

    if p >= 1_000_000_000:

        return "전국"

    return "지역"








def is_building_only_notice(row):

    """

    건축공사업 단독 공고를 전기/소방/기계설비 대상으로 오인하지 않기 위한 방어 가드.

    예: mainCnsttyNm=건축공사업인데 indstrytyCd=0037/37 등으로 잘못 들어온 경우 제외.

    """

    main_cnst = str(row.get("mainCnsttyNm", "") or "").strip()



    if "건축공사업" not in main_cnst:

        return False



    license_text = " ".join([

        str(row.get("lcnsLmtNm", "") or ""),

        str(row.get("업종제한사항", "") or ""),

        str(row.get("licenseLimit", "") or ""),

        str(row.get("licenseLimitNm", "") or ""),

    ])



    # 업종제한사항에 우리 대상 업종이 명확히 같이 있으면 제외하지 않음

    target_words = [

        "전기공사업",

        "소방시설공사업",

        "일반소방시설공사업",

        "전문소방시설공사업",

        "기계설비공사업",

        "가스시설시공업",

    ]



    if any(w in license_text for w in target_words):

        return False



    return True


def normalize_row(raw):

    ind, ind_name = detect_industry(raw)

    region = extract_region(raw)

    scope = decide_scope(raw)



    rep = "전국" if scope == "전국" else (region or "전국")



    row = {

        "공고번호": norm(raw.get("bidNtceNo")),

        "차수": norm(raw.get("bidNtceOrd") or "000"),

        "공고명": norm(raw.get("bidNtceNm")),

        "게시일시": norm(raw.get("bidNtceDt")),

        "시작일시": norm(raw.get("bidBeginDt")),

        "입찰마감일시": norm(raw.get("bidClseDt")),

        "개찰일시": norm(raw.get("opengDt")),

        "공고업종코드": ind,

        "공고업종명": ind_name,

        "indstrytyCd": ind,

        "indstrytyNm": ind_name,

        "mainCnsttyNm": norm(raw.get("mainCnsttyNm")),

        "대표지역": rep,

        "local_region": region,

        "공동도급지역": norm(raw.get("jntcontrctDutyRgnNm1")),

        "공동도급지역_추가": " | ".join([x for x in [

            norm(raw.get("jntcontrctDutyRgnNm2")),

            norm(raw.get("jntcontrctDutyRgnNm3")),

        ] if x]),

        "공동도급비율": norm(raw.get("rgnDutyJntcontrctRt")),

        "참가제한지역": norm(raw.get("prtcptLmtRgnNm")),

        "공사현장지역": norm(raw.get("cnstrtsiteRgnNm")),

        "추정가격": presmpt_price(raw),

        "기초금액": budget_amount(raw),

        "낙찰방법세부기준": method_text(raw),

        "scope": scope,

        "detail_url": norm(raw.get("bidNtceDtlUrl")),

        "발주기관": norm(raw.get("dminsttNm") or raw.get("ntceInsttNm")),

        "_source_api": norm(raw.get("_source_api")),

        "원문": raw,

    }



    return row





def merge_raw_rows(*groups):

    """

    같은 공고번호-차수는 하나로 병합.

    Cnstwk 쪽이 상세정보가 많으므로 필드 많은 row 우선.

    """

    best = {}

    order = []



    def score(raw):

        s = 0

        for k in [

            "mainCnsttyNm", "presmptPrce", "jntcontrctDutyRgnNm1",

            "cnstrtsiteRgnNm", "sucsfbidMthdNm", "bidNtceDtlUrl",

        ]:

            if norm(raw.get(k)):

                s += 10

        if norm(raw.get("_source_api")) == "Cnstwk":

            s += 5

        return s



    for group in groups:

        for raw in group or []:

            if not isinstance(raw, dict):

                continue

            key = _n_data_call_bid_key(raw)

            if not key:

                continue



            if key not in best:

                best[key] = raw

                order.append(key)

            else:

                if score(raw) > score(best[key]):

                    best[key] = raw



    return [best[k] for k in order]





# ============================================================

# 수신자

# ============================================================



def recv_region_key(region):

    t = norm(region)



    if "충청북도" in t or "충북" in t:

        return "충북"

    if "세종" in t:

        return "세종"

    if "경상북도" in t or "경북" in t:

        return "경북"

    if "대구" in t:

        return "대구"



    return t





def decide_receivers(row):
    ind = norm(row.get("공고업종코드"))
    scope = norm(row.get("scope"))

    region_text = str(row.get("local_region") or row.get("대표지역") or "")

    if "충청북도" in region_text or "충북" in region_text or "청주시" in region_text:
        region = "충북"
    else:
        region = recv_region_key(region_text)



    nation_all = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

    nation_elec = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]



    local_fire = {



        "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],



        "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],



        "경북": ["REDACTED_PRIVATE_VALUE"],



        "대구": ["REDACTED_PRIVATE_VALUE"],



    }







    local_mech = {



        "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],



        "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],



    }







    if scope == "전국":

        if ind == "0037":

            return nation_elec

        if ind in ("0038", "0039", "0040", "6202"):

            return nation_all



    if scope == "지역":

        if ind in ("0038", "0039", "0040"):

            return local_fire.get(region, [])

        if ind == "6202":

            return local_mech.get(region, [])

        if ind == "0037":

            return []



    return []





def apply_receivers(rows):

    for row in rows:

        receivers = decide_receivers(row)

        row["수신번호"] = ",".join(receivers)

        row["알림대상"] = "Y" if receivers else "N"

    return rows





# ============================================================

# 저장

# ============================================================




def save_excel(rows, ts):

    if not rows:

        return None



    out = RAW_DIR / ("입찰공고_clean_%s.xlsx" % ts)



    df = pd.DataFrame(rows)

    if "원문" in df.columns:

        df = df.drop(columns=["원문"])



    df.to_excel(out, index=False)

    log("[SAVE] %s" % out)

    return out





def save_split(rows, ts):

    if not rows:

        return



    df = pd.DataFrame(rows)

    if "원문" in df.columns:

        df = df.drop(columns=["원문"])



    for region in sorted(df["대표지역"].fillna("미분류").astype(str).unique()):

        safe = region if region.strip() else "미분류"

        # 파일명 길이 제한
        safe = str(safe).split("|")[0].strip()

        for ch in '\\/:*?"<>|':
            safe = safe.replace(ch, "_")

        safe = " ".join(safe.split())

        if len(safe) > 40:
            safe = safe[:40].rstrip() + "_외"

        if not safe:
            safe = "미분류"

        out = SPLIT_DIR / ("입찰공고_clean_%s_%s.xlsx" % (ts, safe))

        df[df["대표지역"].astype(str) == region].to_excel(out, index=False)

        log("[SAVE] split %s rows=%d" % (safe, len(df[df["대표지역"].astype(str) == region])))
def backup_and_rotate_excels():



    now = time.time()



    targets = [RAW_DIR, SPLIT_DIR, REPORT_DIR]



    for base in targets:



        backup_dir = base / "backup"



        backup_dir.mkdir(parents=True, exist_ok=True)



        for f in base.glob("*.xlsx"):



            try:



                age_days = (now - f.stat().st_mtime) / 86400.0



                if age_days >= 2:



                    dst = backup_dir / f.name



                    if not dst.exists():



                        shutil.move(str(f), str(dst))



                        log(f"[BACKUP] {f} -> {dst}")



            except Exception as e:



                log(f"[BACKUP][ERR] {f}: {e}")



        for f in backup_dir.glob("*"):



            try:



                age_days = (now - f.stat().st_mtime) / 86400.0



                if age_days >= 30:



                    f.unlink()



                    log(f"[DELETE] old backup removed: {f}")



            except Exception as e:



                log(f"[DELETE][ERR] {f}: {e}")




# ============================================================

# main

# ============================================================










def alimtalk_joint_region(row):

    """

    알림톡 표시용 공동도급지역.

    공동도급지역이 있으면 우선 표시하고, 없으면 참가제한/공사현장 지역을 보조로 사용한다.

    """

    def _clean(v):

        if v is None:

            return ""

        t = str(v).strip()

        if t == "" or t.lower() in ("none", "nan", "n/a", "해당없음"):

            return ""

        return t



    for k in [

        "공동도급지역",

        "jntcontrctDutyRgnNm1",

        "공동도급지역_추가",

    ]:

        v = _clean(row.get(k))

        if v:

            return v



    return ""









def alimtalk_joint_ratio(row):

    """

    알림톡 표시용 공동도급비율.

    """

    def _clean(v):

        if v is None:

            return ""

        t = str(v).strip()

        if t == "" or t.lower() in ("none", "nan", "n/a", "해당없음"):

            return ""

        return t



    for k in [

        "공동도급비율",

        "rgnDutyJntcontrctRt",

        "공동도급비율_추가",

    ]:

        v = _clean(row.get(k))

        if v:

            try:

                f = float(str(v).replace("%", "").strip())

                if f == int(f):

                    return str(int(f))

                return str(f)

            except Exception:

                return v



    return "해당없음"






def build_kakao_fields(row):

    amount = row.get("추정가격", 0) or 0

    try:

        amount_int = int(amount)

    except Exception:

        amount_int = 0



    return {

        "industry": row.get("공고업종명", ""),

        "bid_name": row.get("공고명", ""),

        "close_time": row.get("입찰마감일시", ""),

        "joint_region": alimtalk_joint_region(row),

        "joint_rate": alimtalk_joint_ratio(row),    

        "amount": budget_amount(row),
        "amount_str": f"{budget_amount(row):,}",

        "bid_no": row.get("공고번호", ""),

        "bid_ord": row.get("차수", "000"),

        "detail_url": row.get("detail_url", ""),

        "region": row.get("대표지역", "") or row.get("local_region", ""),

        "org_name": row.get("발주기관", ""),

        "낙찰방법세부기준": row.get("낙찰방법세부기준", ""),

    }







def build_gcal_message(row):

    bid_no = str(row.get("공고번호", "") or "").strip()

    bid_ord = str(row.get("차수", "") or "000").strip()

    title = str(row.get("공고명", "") or "").strip()


    # __CANCEL_NOTICE_TITLE_BEFORE_BODY_V1__

    try:

        if is_cancel_notice(row):

            _cancel_body_title = str(title or "").strip()

            if _cancel_body_title and not _cancel_body_title.startswith("[취소공고]"):

                title = "[취소공고] " + _cancel_body_title

                try:

                    row["공고명"] = title

                except Exception:

                    pass

    except Exception as e:

        try:

            log(f"[CANCEL_NOTICE][TITLE_BEFORE_BODY_ERR] {e}")

        except Exception:

            pass


    deadline = str(row.get("입찰마감일시", "") or row.get("입찰서마감일시", "") or "").strip()

    amount = row.get("추정가격", "") or row.get("추정가격", "") or row.get("amount_str", "")

    org = str(row.get("발주기관", "") or "").strip()

    ind = str(row.get("업종", "") or row.get("업종명", "") or row.get("공고업종명", "") or "").strip()

    method = str(row.get("낙찰방법", "") or row.get("낙찰방법세부기준", "") or "").strip()

    region = str(row.get("공동도급지역", "") or "").strip()



    try:

        if amount not in ("", None):

            amount = f"{int(float(str(amount).replace(',', ''))):,}원"

    except Exception:

        amount = str(amount)



    url = ""

    if bid_no:

        url = f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={bid_no}&bidPbancOrd={bid_ord}"



    return f"""[입찰마감]

공고명 : {title}

입찰마감일시 : {deadline}

공동도급지역 : {_display_blank_as_none(region)}

추정가격 : {amount}

공고번호 : {bid_no} - {bid_ord}



발주기관 : {org}

업종 : {ind}

낙찰방법 : {method}

상세URL : {url}

"""



def send_kakao_one(phone, row, no_send=False):



    from kakao_send_tb0485 import send_for_item as kakao_send_for_item



    key = f"{row.get('공고번호')}-{row.get('차수')}"

    title = row.get("공고명", "")

    fields = build_kakao_fields(row)



    if no_send or os.environ.get("HARD_NO_SEND", "") == "1":



        # __CANCEL_NOTICE_SEND_V5_1_SAFE_KEY_FIX__

        try:

            _cancel_v51_safe_title = str(

                locals().get("title")

                or locals().get("msg_title")

                or locals().get("bid_title")

                or ""

            )

            if "취소공고" in _cancel_v51_safe_title and not str(key).startswith("CANCEL:"):

                key = _cancel_v51_cancelize_key(key)

        except Exception:

            pass

        # __CANCEL_NOTICE_SEND_V5_4_APPLY_BEFORE_LOG__

        try:

            if "row" in locals() and is_cancel_notice_row(row):

                _cancel_v54_old_key = str(locals().get("key", locals().get("key", "")) or "")

                _cancel_v54_old_title = str(locals().get("title", locals().get("title", "")) or "")

                _cancel_v54_key, _cancel_v54_title = _cancel_v54_apply(row, _cancel_v54_old_key, _cancel_v54_old_title)

                if _cancel_v54_key:

                    key = _cancel_v54_key

                    key = _cancel_v54_key

                if _cancel_v54_title:

                    title = _cancel_v54_title

                    title = _cancel_v54_title

        except Exception as e:

            log(f"[CANCEL_NOTICE][V5_4_FORCE_ERR] {e}")

        log("[SAFE] DRY RUN TB0485: key=%s -> %s / %s" % (key, phone, title))



        return False



    try:



        # __CANCEL_NOTICE_SEND_V5_5_1_BEFORE_ALREADY_CHECK__

        # 취소공고는 원공고 발송 이력과 분리해야 하므로

        # SEND][SKIP_ALREADY 검사 전에 key/title을 CANCEL 전용으로 먼저 바꾼다.

        try:

            if "row" in locals() and is_cancel_notice_row(row):

                _cancel_v551_old_key = str(

                    locals().get("key", locals().get("full_key", "")) or ""

                )

                _cancel_v551_old_title = str(

                    locals().get("title", locals().get("msg_title", "")) or ""

                )

        

                if "_cancel_v54_apply" in globals():

                    _cancel_v551_key, _cancel_v551_title = _cancel_v54_apply(

                        row,

                        _cancel_v551_old_key,

                        _cancel_v551_old_title,

                    )

                else:

                    _cancel_v551_key = make_cancel_notice_key(row, _cancel_v551_old_key)

                    _cancel_v551_title = prepare_cancel_notice_row(row, _cancel_v551_old_title)

        

                if _cancel_v551_key:

                    key = _cancel_v551_key

                    full_key = _cancel_v551_key

                    send_key = _cancel_v551_key

                    dedup_key = _cancel_v551_key

        

                if _cancel_v551_title:

                    title = _cancel_v551_title

        

                try:

                    log(f"[CANCEL_NOTICE][V5_5_1_BEFORE_ALREADY] {_cancel_v551_old_key} -> {key} / {title}")

                except Exception:

                    pass

        

        except Exception as e:

            log(f"[CANCEL_NOTICE][V5_5_1_BEFORE_ALREADY_ERR] {e}")

        if is_already_sent(fields, phone):

            log(f"[SEND][SKIP_ALREADY] {key} -> {phone}")

            return False



        try:

            res = kakao_send_for_item(phone, fields, dry_run=False)

        except TypeError:

            res = kakao_send_for_item(fields, phone, dry_run=False)



        log("[SEND] RES TB0485 %s -> %s: %s" % (key, phone, res))

        if isinstance(res, dict) and res.get("ok"):
            mark_sent(fields, phone)
            log("[SEND][MARK_SENT] %s -> %s" % (key, phone))
            return True

        return False



    except Exception as e:



        log("[SEND][ERR] %s -> %s: %s" % (key, phone, e))



        return False



def parse_args():

    ap = argparse.ArgumentParser()

    ap.add_argument("--hours", type=int, default=1)

    ap.add_argument("--no-send", action="store_true")

    return ap.parse_args()







# __BID_DEDUP_KEY_PATCH_V2__

# -------------------------------------------------

# 공고번호 정규화 / 중복 알림 방지 패치

# -------------------------------------------------

_BID_NO_RE = re.compile(r"(R\d{2}BK\d+)(?:\s*-\s*(\d{1,3}))?", re.I)



def _bid_get(obj, name, default=""):

    try:

        if isinstance(obj, dict):

            return obj.get(name, default)

        if hasattr(obj, "get"):

            return obj.get(name, default)

    except Exception:

        pass

    return default



def _bid_clean(v) -> str:

    s = "" if v is None else str(v)

    if s.strip().lower() in ("nan", "none", "null"):

        return ""

    s = s.strip().upper()

    s = (

        s.replace("－", "-")

         .replace("–", "-")

         .replace("—", "-")

         .replace("−", "-")

    )

    s = re.sub(r"\s+", "", s)

    return s



def split_bid_no_ord(bid_no="", bid_ord=""):

    no = _bid_clean(bid_no)

    ord_s = _bid_clean(bid_ord)



    base = ""

    ord_from_no = ""



    m = _BID_NO_RE.search(no)

    if m:

        base = m.group(1).upper()

        ord_from_no = m.group(2) or ""

    else:

        if "-" in no:

            left, right = no.rsplit("-", 1)

            base = left.strip().upper()

            if re.fullmatch(r"\d+", right.strip()):

                ord_from_no = right.strip()

        else:

            base = no



    if ord_s and re.fullmatch(r"\d+", ord_s):

        ord_v = ord_s.zfill(3)[-3:]

    elif ord_from_no and re.fullmatch(r"\d+", ord_from_no):

        ord_v = ord_from_no.zfill(3)[-3:]

    else:

        ord_v = "000"



    return base, ord_v



def make_bid_key(bid_no="", bid_ord="", base_only=True) -> str:

    base, ord_v = split_bid_no_ord(bid_no, bid_ord)

    if not base:

        return ""

    if base_only:

        return f"BID:{base}"

    return f"BID:{base}-{ord_v}"



def get_bid_no_ord_from_row(row):

    raw = _bid_get(row, "원문", {})

    if not isinstance(raw, dict):

        raw = {}



    bid_no = (

        raw.get("bidNtceNo")

        or _bid_get(row, "공고번호")

        or _bid_get(row, "bidNtceNo")

        or _bid_get(row, "bid_no")

        or _bid_get(row, "key")

        or ""

    )

    bid_ord = (

        raw.get("bidNtceOrd")

        or _bid_get(row, "차수")

        or _bid_get(row, "공고차수")

        or _bid_get(row, "bidNtceOrd")

        or _bid_get(row, "bid_ord")

        or "000"

    )

    return bid_no, bid_ord



def make_bid_key_from_row(row, base_only=True) -> str:

    bid_no, bid_ord = get_bid_no_ord_from_row(row)

    return make_bid_key(bid_no, bid_ord, base_only=base_only)



def _bid_key_variants(bid_no="", bid_ord=""):

    base, ord_v = split_bid_no_ord(bid_no, bid_ord)

    out = set()

    if not base:

        return out

    out.add(make_bid_key(base, ord_v, base_only=True))

    out.add(make_bid_key(base, ord_v, base_only=False))

    out.add(base)

    out.add(f"{base}-{ord_v}")

    out.add(f"{base} - {ord_v}")

    out.add(f"{base}-{ord_v}-{ord_v}")

    out.add(f"{base} - {ord_v}-{ord_v}")

    return {x for x in out if x}



def load_send_history(keep_days: int = 30):

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

        dk = str(r.get("dedup_key") or "").strip()

        if dk:

            keys.add(dk)



        bid_no = (

            r.get("bid_no")

            or r.get("공고번호")

            or r.get("bidNtceNo")

            or ""

        )

        bid_ord = (

            r.get("bid_ord")

            or r.get("차수")

            or r.get("bidNtceOrd")

            or "000"

        )



        for k in _bid_key_variants(bid_no, bid_ord):

            keys.add(k)



    return keys, filtered



def save_send_history(rows: list):

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)



    tmp = HISTORY_FILE.with_suffix(".tmp")

    lock_path = HISTORY_FILE.with_suffix(HISTORY_FILE.suffix + ".lock")

    fieldnames = ["dedup_key", "bid_key_full", "bid_no", "bid_ord", "sent_date", "sent_ts"]



    lock_fd = None

    try:

        try:

            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)

            _fcntl = globals().get("fcntl")

            if _fcntl is not None:

                _fcntl.lockf(lock_fd, _fcntl.LOCK_EX)

        except Exception:

            lock_fd = None



        merged = []

        keys = set()



        def _add_row(r):

            if not isinstance(r, dict):

                return



            raw_key = str(r.get("dedup_key") or "").strip()

            bid_no = (

                r.get("bid_no")

                or r.get("공고번호")

                or r.get("bidNtceNo")

                or ""

            )

            bid_ord = (

                r.get("bid_ord")

                or r.get("차수")

                or r.get("bidNtceOrd")

                or "000"

            )



            if raw_key.startswith("BID:") and not bid_no:

                body = raw_key[4:]

                if "-" in body:

                    bid_no, bid_ord = body.rsplit("-", 1)

                else:

                    bid_no, bid_ord = body, "000"



            key = raw_key if raw_key.startswith("BID:") else make_bid_key(bid_no, bid_ord, base_only=True)

            if not key:

                return



            base_bid_no, norm_bid_ord = split_bid_no_ord(bid_no, bid_ord)

            if not base_bid_no and key.startswith("BID:"):

                base_bid_no = key[4:]

                norm_bid_ord = "000"



            if key in keys:

                return



            keys.add(key)

            merged.append({

                "dedup_key": key,

                "bid_key_full": make_bid_key(base_bid_no, norm_bid_ord, base_only=False),

                "bid_no": base_bid_no,

                "bid_ord": norm_bid_ord,

                "sent_date": str(r.get("sent_date") or r.get("sent_dt") or ""),

                "sent_ts": str(r.get("sent_ts") or ""),

            })



        if HISTORY_FILE.exists():

            try:

                with open(HISTORY_FILE, newline="", encoding="utf-8") as f:

                    reader = csv.DictReader(f)

                    for r in reader:

                        _add_row(r)

            except Exception:

                pass



        for r in (rows or []):

            _add_row(r)



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

                _fcntl = globals().get("fcntl")

                if _fcntl is not None:

                    _fcntl.lockf(lock_fd, _fcntl.LOCK_UN)

            except Exception:

                pass

            try:

                os.close(lock_fd)

            except Exception:

                pass



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

            bid_no, bid_ord = get_bid_no_ord_from_row(r)



            key = make_bid_key(bid_no, bid_ord, base_only=True)

            if key:

                keys.add(key)



            full_key = make_bid_key(bid_no, bid_ord, base_only=False)

            if full_key:

                keys.add(full_key)



            for k in _bid_key_variants(bid_no, bid_ord):

                keys.add(k)



    except Exception as e:

        log(f"[DEDUP][REPORT][ERR] {e}")



    return keys



def dedupe_by_bid(rows):

    seen = set()

    out = []



    for row in rows or []:

        key = make_bid_key_from_row(row, base_only=True)



        if not key:

            out.append(row)

            continue



        if key in seen:

            continue



        seen.add(key)

        out.append(row)



    return out



def dedup_by_bid(rows):

    def _norm(v):

        s = "" if v is None else str(v).strip()

        return "" if s.lower() in ("nan", "none", "null") else s



    def _amt_score(row):

        amt = _norm(_bid_get(row, "추정금액") or _bid_get(row, "PresmptPrce") or _bid_get(row, "bdgtAmt"))

        return 0 if amt in ("", "0", "0원", "0.0", "0.0원") else 1



    def _joint_score(row):

        score = 0

        jr = _norm(_bid_get(row, "공동도급지역"))

        rr = _norm(_bid_get(row, "공동도급비율"))



        if jr and jr not in ("해당없음",):

            score += 1



        if rr and rr not in ("해당없음", "0", "0%"):

            score += 1



        return score



    def _row_score(row):

        return (

            _amt_score(row),

            _joint_score(row),

        )



    best = {}

    order = []

    no_key_count = 0



    for row in rows or []:

        key = make_bid_key_from_row(row, base_only=True)



        if not key:

            no_key_count += 1

            key = f"NO_BID_KEY:{no_key_count}"



        if key not in best:

            best[key] = row

            order.append(key)

            continue



        prev = best[key]



        if _row_score(row) > _row_score(prev):

            best[key] = row



    return [best[k] for k in order]



# __BID_DEDUP_KEY_PATCH_V2__ END







# ============================================================

# gon_auto 보조 보강

# - Cnstwk API에서 indstrytyCd/mainCnsttyNm이 비어 있는 공고 보강

# - 예: R26BK01553436 Cnstwk 원본은 업종코드 없음, gon_auto에는 공종코드 6202 존재

# ============================================================



def _gon_norm_bid_ord(v):

    t = str(v or "").strip()

    if not t or t.lower() == "nan":

        return "000"

    try:

        if t.endswith(".0"):

            t = t[:-2]

        return str(int(t)).zfill(3)

    except Exception:

        return t.zfill(3)





def _load_gon_auto_enrich_map(days=3):

    try:

        import glob

        import os

        import pandas as pd

        from datetime import datetime, timedelta



        base = "/mnt/vol1/bid/gon_auto"

        cutoff = datetime.now() - timedelta(days=days)

        mp = {}



        files = sorted(glob.glob(base + "/입찰공고_지역분류_*.xlsx"))



        for f in files:

            try:

                if os.path.basename(f).startswith("~$"):

                    continue



                if datetime.fromtimestamp(os.path.getmtime(f)) < cutoff:

                    continue



                xl = pd.ExcelFile(f)



                for sheet in xl.sheet_names:

                    try:

                        df = pd.read_excel(f, sheet_name=sheet, dtype=str)

                    except Exception:

                        continue



                    if "공고번호" not in df.columns:

                        continue



                    for _, rr in df.iterrows():

                        bid_no = str(rr.get("공고번호") or "").strip()

                        if not bid_no or bid_no.lower() == "nan":

                            continue



                        bid_ord = _gon_norm_bid_ord(rr.get("차수"))

                        key = bid_no + "-" + bid_ord



                        code = str(rr.get("공종코드") or "").strip()

                        if code.endswith(".0"):

                            code = code[:-2]

                        if code.lower() == "nan":

                            code = ""



                        region = str(rr.get("참가가능지역") or "").strip()

                        if region.lower() == "nan":

                            region = ""



                        amt = str(rr.get("추정금액") or "").strip()

                        if amt.lower() == "nan":

                            amt = ""



                        title = str(rr.get("공고명") or "").strip()

                        if title.lower() == "nan":

                            title = ""



                        if key not in mp:

                            mp[key] = {}



                        if code:

                            mp[key]["indstrytyCd"] = code

                            mp[key]["공고업종코드"] = code



                            if code == "6202":

                                mp[key]["indstrytyNm"] = "기계설비공사업"

                                mp[key]["공고업종명"] = "기계설비공사업"



                        if region:

                            mp[key]["prtcptPsblRgnNm"] = region

                            mp[key]["prtcptLmtRgnNm"] = region



                        if amt:

                            mp[key]["bdgtAmt"] = amt



                        if title:

                            mp[key]["bidNtceNm"] = title



            except Exception:

                continue



        log("[GON_AUTO][ENRICH] loaded keys=%d" % len(mp))

        return mp



    except Exception as e:

        log("[GON_AUTO][ENRICH][ERR] load failed: %s" % e)

        return {}





def _apply_gon_auto_enrich(raw_rows, gon_map):

    if not gon_map:

        return raw_rows



    hit = 0



    for r in raw_rows:

        try:

            bid_no = str(r.get("bidNtceNo") or r.get("공고번호") or "").strip()

            bid_ord = _gon_norm_bid_ord(r.get("bidNtceOrd") or r.get("차수"))

            key = bid_no + "-" + bid_ord



            extra = gon_map.get(key)

            if not extra:

                continue



            changed = False



            # 업종코드가 비어 있을 때만 보강

            if not str(r.get("indstrytyCd") or "").strip() and extra.get("indstrytyCd"):

                r["indstrytyCd"] = extra["indstrytyCd"]

                r["공고업종코드"] = extra["indstrytyCd"]

                changed = True



            if not str(r.get("indstrytyNm") or "").strip() and extra.get("indstrytyNm"):

                r["indstrytyNm"] = extra["indstrytyNm"]

                r["공고업종명"] = extra["indstrytyNm"]

                changed = True



            if not str(r.get("prtcptPsblRgnNm") or "").strip() and extra.get("prtcptPsblRgnNm"):

                r["prtcptPsblRgnNm"] = extra["prtcptPsblRgnNm"]

                changed = True



            if not str(r.get("prtcptLmtRgnNm") or "").strip() and extra.get("prtcptLmtRgnNm"):

                r["prtcptLmtRgnNm"] = extra["prtcptLmtRgnNm"]

                changed = True



            # API presmptPrce가 있으면 유지, 없을 때만 gon_auto 추정금액 보강

            if not str(r.get("presmptPrce") or "").strip() and extra.get("bdgtAmt"):

                r["presmptPrce"] = extra["bdgtAmt"]

                changed = True



            if changed:

                hit += 1

                log("[GON_AUTO][ENRICH] %s ind=%s region=%s title=%s" % (

                    key,

                    r.get("indstrytyCd", ""),

                    r.get("prtcptPsblRgnNm", ""),

                    r.get("bidNtceNm", ""),

                ))



        except Exception as e:

            log("[GON_AUTO][ENRICH][ROW_ERR] %s" % e)



    log("[GON_AUTO][ENRICH] applied rows=%d" % hit)

    return raw_rows





# ============================================================

# PPSSrch 업종코드 보강

# - Cnstwk row가 병합 우선 선택되어 업종코드가 비는 경우

# - PPSSrch 조회에 사용한 indstrytyCd를 공식 API 조회 근거로 보강

# - gon_auto 엑셀 의존 제거용

# ============================================================



def _apply_ppssrch_industry_backfill(raw_rows, pps_rows):

    try:

        pps_map = {}



        for r in pps_rows or []:

            key = _n_data_call_bid_key(r)

            if not key:

                continue



            code = norm(r.get("indstrytyCd") or r.get("_query_indstrytyCd") or r.get("공고업종코드"))

            name = norm(r.get("indstrytyNm") or r.get("공고업종명"))

            main = norm(r.get("mainCnsttyNm"))



            if not code and not name and not main:

                continue



            if key not in pps_map:

                pps_map[key] = {}



            if code:

                pps_map[key]["indstrytyCd"] = code

                pps_map[key]["공고업종코드"] = code



            if name:

                pps_map[key]["indstrytyNm"] = name

                pps_map[key]["공고업종명"] = name



            if main:

                pps_map[key]["mainCnsttyNm"] = main



        hit = 0



        for r in raw_rows or []:

            key = _n_data_call_bid_key(r)

            extra = pps_map.get(key)

            if not extra:

                continue



            changed = False



            if not norm(r.get("indstrytyCd")) and extra.get("indstrytyCd"):

                r["indstrytyCd"] = extra["indstrytyCd"]

                r["공고업종코드"] = extra["indstrytyCd"]

                changed = True



            if not norm(r.get("indstrytyNm")) and extra.get("indstrytyNm"):

                r["indstrytyNm"] = extra["indstrytyNm"]

                r["공고업종명"] = extra["indstrytyNm"]

                changed = True



            if not norm(r.get("mainCnsttyNm")) and extra.get("mainCnsttyNm"):

                r["mainCnsttyNm"] = extra["mainCnsttyNm"]

                changed = True



            if changed:

                hit += 1

                log("[PPSSrch][BACKFILL] %s ind=%s/%s main=%s title=%s" % (

                    key,

                    r.get("indstrytyCd", ""),

                    r.get("indstrytyNm", ""),

                    r.get("mainCnsttyNm", ""),

                    r.get("bidNtceNm", ""),

                ))



        log("[PPSSrch][BACKFILL] applied rows=%d" % hit)

        return raw_rows



    except Exception as e:

        log("[PPSSrch][BACKFILL][ERR] %s" % e)

        return raw_rows


def main():
    env_guard()
    args = parse_args()

    now = datetime.now()
    start = now - timedelta(
        hours=max(1, args.hours),
        minutes=30,
    )  # overlap: API 반영 지연/경계 누락 방지

    bgn = ymdhm(start)
    end = ymdhm(now)
    ts = ymdhm(now)

    api_key = load_api_key()
    log("[MAIN] period %s ~ %s" % (bgn, end))

    pps = collect_ppssrch(api_key, bgn, end)
    cnst = collect_cnstwk(api_key, bgn, end)
    prgn_map = collect_prtcpt_region(api_key, bgn, end)

    raw_rows = merge_raw_rows(pps, cnst)
    raw_rows = _apply_ppssrch_industry_backfill(raw_rows, pps)

    for raw in raw_rows:
        raw_key = _n_data_call_bid_key(raw)
        if raw_key in prgn_map:
            raw["prtcptPsblRgnNm"] = " | ".join(prgn_map[raw_key])

    log("[MERGE] raw merged rows=%d" % len(raw_rows))

    rows = []

    for raw in raw_rows:
        row = normalize_row(raw)
        cancelled = is_cancel_notice(row)

        if cancelled:
            prepare_cancel_notice_row_final(row)
            row["_cancel_receivers"] = load_previous_notice_receivers(row)

            log(
                "[CANCEL][ACCEPT] %s receivers=%s title=%s"
                % (
                    notice_event_key(row),
                    ",".join(row["_cancel_receivers"]) or "없음",
                    row.get("공고명", ""),
                )
            )

            # 취소공고는 상태 변경 알림이므로 업종/금액/건축 단독 필터를
            # 다시 적용하지 않는다. 원공고 수신 이력은 apply_receivers에서 사용한다.
            rows.append(row)
            continue

        if is_building_only_notice(row):
            log(
                "[SKIP_BUILDING_ONLY] %s mainCnsttyNm=%s ind=%s/%s title=%s"
                % (
                    _n_data_call_bid_key(row),
                    str(row.get("mainCnsttyNm", "") or ""),
                    str(
                        row.get("공고업종코드", "")
                        or row.get("indstrytyCd", "")
                        or ""
                    ),
                    str(
                        row.get("공고업종명", "")
                        or row.get("indstrytyNm", "")
                        or ""
                    ),
                    str(row.get("공고명", "") or ""),
                )
            )
            continue

        if row["공고업종코드"] not in TARGET_INDS:
            continue

        if row["추정가격"] < MIN_BUDGET:
            continue

        rows.append(row)

    # R26BK01552481-001처럼 API 조회 시간창 밖으로 벗어난 확인된 취소공고도
    # 원공고 발송 이력/리포트를 바탕으로 한 번은 처리한다.
    rows = inject_known_cancel_notices(rows)

    log("[FILTER] target rows=%d" % len(rows))
    rows = apply_receivers(rows)

    only_bid = os.environ.get("ONLY_BID", "").strip().upper()
    only_cancel = os.environ.get("ONLY_CANCEL", "").strip().lower() in (
        "1", "y", "yes", "true"
    )

    if only_bid:
        rows = [
            r for r in rows
            if notice_identity(r)[0] == only_bid
        ]
        log("[FILTER][ONLY_BID] %s rows=%d" % (only_bid, len(rows)))

    if only_cancel:
        rows = [r for r in rows if is_cancel_notice(r)]
        log("[FILTER][ONLY_CANCEL] rows=%d" % len(rows))

    dbg = os.environ.get("DBG_BID", "").strip()
    if dbg:
        hits = [r for r in rows if r.get("공고번호") == dbg]
        log("[DBG] %s hits=%d" % (dbg, len(hits)))
        for r in hits:
            log(
                "[DBG_ROW] key=%s ind=%s scope=%s region=%s rep=%s "
                "presmpt=%s recv=%s cancel=%s title=%s"
                % (
                    notice_event_key(r),
                    r.get("공고업종코드"),
                    r.get("scope"),
                    r.get("local_region"),
                    r.get("대표지역"),
                    r.get("추정가격"),
                    r.get("수신번호"),
                    is_cancel_notice(r),
                    r.get("공고명"),
                )
            )

    send_targets = [r for r in rows if r.get("수신번호")]

    # 일반 공고는 차수를 무시한 기본키로, 취소공고는 별도 CANCEL 키로 중복 제거한다.
    before_count = len(send_targets)
    seen_event_keys = set()
    deduped_targets = []
    skipped = []

    for target in send_targets:
        event_key = notice_event_key(target)
        if not event_key:
            deduped_targets.append(target)
            continue

        if event_key in seen_event_keys:
            skipped.append(
                "%s/%s" % (event_key, target.get("공고명", ""))
            )
            continue

        seen_event_keys.add(event_key)
        deduped_targets.append(target)

    send_targets = deduped_targets

    if len(send_targets) != before_count:
        log(
            "[DEDUP][FINAL-SEND] send_targets %d -> %d; skipped=%s"
            % (
                before_count,
                len(send_targets),
                " | ".join(skipped[:10]),
            )
        )

    log(
        "[SEND] target rows=%d no_send=%s"
        % (len(send_targets), args.no_send)
    )

    sent_rows = []
    sent_count = 0
    smoke_max = int(os.environ.get("SMOKE_MAX_SEND", "0") or "0")

    for row in send_targets:
        recv_list = normalize_phone_list(
            str(row.get("수신번호", "")).split(",")
        )

        if is_cancel_notice(row):
            prepare_cancel_notice_row_final(row)
            log(
                "[SEND][CANCEL_NOTICE] %s / %s / receivers=%s"
                % (
                    notice_event_key(row),
                    row.get("공고명", ""),
                    ",".join(recv_list),
                )
            )

        gcal_done = False

        for phone in recv_list:
            ok = send_kakao_one(
                phone,
                row,
                no_send=args.no_send,
            )

            if ok:
                sent_row = dict(row)
                sent_row["발송수신번호"] = phone
                sent_row["발송일시"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                sent_rows.append(sent_row)

                if (not args.no_send) and (not gcal_done):
                    gcal_key = notice_event_key(row)
                    try:
                        from modules.calendar_sync import sync_message_to_gcal

                        gcal_msg = build_gcal_message(row)
                        gcal_res = sync_message_to_gcal(
                            gcal_msg,
                            logger=log,
                        )
                        log(
                            "[GCAL][created] %s -> %s"
                            % (gcal_key, gcal_res)
                        )
                        gcal_done = True
                    except Exception as e:
                        log("[GCAL][ERROR] %s: %s" % (gcal_key, e))

            sent_count += 1

            if smoke_max and sent_count >= smoke_max:
                log("[SMOKE] SMOKE_MAX_SEND=%s reached" % smoke_max)
                log("[MAIN] END")
                return

    if sent_rows:
        sent_out = REPORT_DIR / ("발송공고_%s.xlsx" % ts)
        sent_df = pd.DataFrame(sent_rows)
        if "원문" in sent_df.columns:
            sent_df = sent_df.drop(columns=["원문"])
        sent_df.to_excel(sent_out, index=False)
        log(
            "[SAVE] sent_report %s rows=%d"
            % (sent_out, len(sent_rows))
        )

    save_excel(rows, ts)
    save_split(rows, ts)
    backup_and_rotate_excels()
    log("[MAIN] END")








# === SEND_DEDUP_GUARD_PATCH_BEGIN ===
# -*- coding: utf-8 -*-
#
# SEND_DEDUP_GUARD_PATCH
# 목적:
#   - 같은 공고 + 같은 수신번호 알림톡 중복 발송 방지
#   - R26BK01522966 / R26BK01522966-000 / R26BK01522966 - 000 키 정규화
#   - send_history.csv / report_keys / 발송 직전 guard 일괄 보강
#
# 이 블록은 main_send.py 하단, if __name__ == "__main__": 바로 위에서
# 기존 함수를 override/wrap 한다.

import os as _dedup_os
import csv as _dedup_csv
import re as _dedup_re
import sqlite3 as _dedup_sqlite3
from pathlib import Path as _DedupPath
from datetime import datetime as _DedupDateTime

_DEDUP_BID_KEY_RE = _dedup_re.compile(
    r"(R\d{2}[A-Z]{2}\d{8})(?:\s*[-_]\s*(\d{3}))?",
    _dedup_re.I,
)

_DEDUP_TRAILING_ORD_RE = _dedup_re.compile(
    r"^([A-Z0-9]{5,})(?:[-_](\d{2,3}))$",
    _dedup_re.I,
)


def _dedup_log(msg):
    try:
        if callable(globals().get("log")):
            globals()["log"](msg)
        else:
            print(msg)
    except Exception:
        try:
            print(msg)
        except Exception:
            pass


def _dedup_norm_ord(v, default="000"):
    s = str(v or "").strip()
    s = _dedup_re.sub(r"\D", "", s)
    if not s:
        s = default
    s = _dedup_re.sub(r"\D", "", str(s or "000")) or "000"
    return s[-3:].zfill(3)


def split_bid_key(bid_no="", bid_ord="000"):
    """
    공고번호/차수를 표준형으로 분리한다.

    예:
      R26BK01522966, 000        -> R26BK01522966 / 000
      R26BK01522966-000, 000    -> R26BK01522966 / 000
      R26BK01522966 - 000, 000  -> R26BK01522966 / 000
      조달청 시설 R26BK01522966-000 호 -> R26BK01522966 / 000
    """
    s_no = str(bid_no or "").strip()
    s_ord = str(bid_ord or "").strip() or "000"

    blob = f"{s_no}-{s_ord}".replace("호", " ")
    m = _DEDUP_BID_KEY_RE.search(blob)

    if m:
        no = m.group(1).upper()
        ordv = m.group(2) or s_ord or "000"
        return no, _dedup_norm_ord(ordv)

    compact = s_no.upper().replace(" ", "").replace("호", "")
    m2 = _DEDUP_TRAILING_ORD_RE.match(compact)
    if m2 and (not s_ord or s_ord == "000"):
        no = m2.group(1).upper()
        ordv = m2.group(2)
        return no, _dedup_norm_ord(ordv)

    no = compact
    ordv = _dedup_norm_ord(s_ord)
    return no, ordv


def make_bid_key(bid_no="", bid_ord="000"):
    no, ordv = split_bid_key(bid_no, bid_ord)
    return f"{no}-{ordv}" if no else ""


def _dedup_bid_key_variants(bid_no="", bid_ord="000"):
    """
    기존 코드가 만들 수 있는 key 변형까지 같이 포함한다.
    예: R26BK01522966-000, R26BK01522966-000-000
    """
    variants = set()
    raw_no = str(bid_no or "").strip()
    raw_ord = str(bid_ord or "").strip() or "000"

    no, ordv = split_bid_key(raw_no, raw_ord)
    if not no:
        return variants

    canonical = make_bid_key(no, ordv)
    variants.add(canonical)

    if raw_no:
        variants.add(raw_no)
        variants.add(f"{raw_no}-{_dedup_norm_ord(raw_ord)}")

    variants.add(f"{canonical}-{ordv}")

    return {v for v in variants if v}


def _clean_phone(phone):
    return _dedup_re.sub(r"\D", "", str(phone or ""))


def normalize_receivers(receivers):
    out = []
    seen = set()

    for p in receivers or []:
        d = _clean_phone(p)
        if not d:
            continue
        if d in seen:
            continue
        seen.add(d)
        out.append(d)

    return out


def _dedup_row_bid_key(row):
    if not isinstance(row, dict):
        return ""

    raw = row.get("원문") or {}
    raw_dict = raw if isinstance(raw, dict) else {}

    bid_no = (
        raw_dict.get("bidNtceNo")
        or raw_dict.get("공고번호")
        or row.get("bidNtceNo")
        or row.get("공고번호")
        or row.get("bid_no")
        or ""
    )
    bid_ord = (
        raw_dict.get("bidNtceOrd")
        or raw_dict.get("차수")
        or row.get("bidNtceOrd")
        or row.get("차수")
        or row.get("bid_ord")
        or "000"
    )

    if not bid_no and raw and not isinstance(raw, dict):
        bid_no = str(raw)

    return make_bid_key(bid_no, bid_ord)


def _dedup_normalize_row_bid_fields(row):
    if not isinstance(row, dict):
        return row

    raw = row.get("원문") or {}
    raw_dict = raw if isinstance(raw, dict) else {}

    bid_no = (
        raw_dict.get("bidNtceNo")
        or row.get("bidNtceNo")
        or row.get("공고번호")
        or row.get("bid_no")
        or ""
    )
    bid_ord = (
        raw_dict.get("bidNtceOrd")
        or row.get("bidNtceOrd")
        or row.get("차수")
        or row.get("bid_ord")
        or "000"
    )

    if not bid_no and raw and not isinstance(raw, dict):
        bid_no = str(raw)

    no, ordv = split_bid_key(bid_no, bid_ord)
    if no:
        row["공고번호"] = no
        row["차수"] = ordv
        if isinstance(raw, dict):
            raw["bidNtceNo"] = no
            raw["bidNtceOrd"] = ordv

    return row


def _dedup_guard_db_path():
    # SQLite는 NAS/NFS/SMB 공유마운트에서 WAL/lock 문제가 자주 생길 수 있으므로
    # 기본 send_guard DB는 main_send.py가 있는 로컬 경로에 둔다.
    # 필요하면 환경변수로 강제 지정 가능:
    #   N_DATA_SEND_GUARD_DB=/some/path/send_guard.sqlite3
    override = _dedup_os.getenv("N_DATA_SEND_GUARD_DB", "").strip()
    if override:
        return _DedupPath(override)

    try:
        local_base = _DedupPath(__file__).resolve().parent
    except Exception:
        local_base = _DedupPath(_dedup_os.getcwd())

    return local_base / "split/history/send_guard.sqlite3"

def _send_guard_conn():
    # send_guard DB 연결.
    # - NAS WAL 전환을 하지 않는다.
    # - busy_timeout + 짧은 재시도로 일시적 lock을 흡수한다.
    import time as _dedup_time

    db = _dedup_guard_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)

    last_exc = None

    for attempt in range(1, 13):
        conn = None

        try:
            conn = _dedup_sqlite3.connect(str(db), timeout=60)
            conn.execute("PRAGMA busy_timeout=60000")

            # WAL 전환은 lock을 유발할 수 있어 기본적으로 사용하지 않는다.
            # 정말 WAL이 필요하면 명시적으로만 켠다.
            if _dedup_os.getenv("N_DATA_SEND_GUARD_WAL", "").strip().lower() in ("1", "y", "yes", "true"):
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                except Exception as e:
                    _dedup_log(f"[GUARD][WARN] journal_mode=WAL skipped: {e}")

            conn.execute(
                "CREATE TABLE IF NOT EXISTS alimtalk_send_guard ("
                "send_key TEXT PRIMARY KEY, "
                "bid_key TEXT NOT NULL, "
                "phone TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "title TEXT, "
                "created_ts TEXT NOT NULL, "
                "updated_ts TEXT NOT NULL, "
                "raw TEXT)"
            )
            conn.commit()
            return conn

        except _dedup_sqlite3.OperationalError as e:
            last_exc = e
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                if attempt in (1, 6, 12):
                    _dedup_log(f"[GUARD][WAIT] sqlite locked attempt={attempt}/12 db={db}: {e}")
                _dedup_time.sleep(min(0.5 * attempt, 3.0))
                continue

            raise

    raise last_exc

def make_send_once_key(bid_key, phone):
    return f"{str(bid_key or '').strip()}|{_clean_phone(phone)}"


def reserve_send_once(bid_key, phone, title=""):
    """
    알림톡 API 호출 직전에 원자적으로 예약한다.
    같은 공고 + 같은 수신번호는 최초 1개 실행만 True.
    """
    bid_key = str(bid_key or "").strip()
    phone = _clean_phone(phone)
    send_key = make_send_once_key(bid_key, phone)

    if not bid_key or not phone:
        return False

    now_s = _DedupDateTime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _send_guard_conn()

    try:
        try:
            conn.execute("""
                DELETE FROM alimtalk_send_guard
                 WHERE send_key = ?
                   AND status = 'reserved'
                   AND created_ts < datetime('now', '-2 hours', 'localtime')
            """, (send_key,))
        except Exception:
            pass

        cur = conn.execute("""
            INSERT OR IGNORE INTO alimtalk_send_guard
            (send_key, bid_key, phone, status, title, created_ts, updated_ts, raw)
            VALUES (?, ?, ?, 'reserved', ?, ?, ?, '')
        """, (send_key, bid_key, phone, str(title or "")[:200], now_s, now_s))
        conn.commit()
        return cur.rowcount == 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_send_guard_sent(bid_key, phone, title="", raw=""):
    bid_key = str(bid_key or "").strip()
    phone = _clean_phone(phone)
    send_key = make_send_once_key(bid_key, phone)

    now_s = _DedupDateTime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _send_guard_conn()

    try:
        conn.execute("""
            UPDATE alimtalk_send_guard
               SET status='sent',
                   title=?,
                   updated_ts=?,
                   raw=?
             WHERE send_key=?
        """, (str(title or "")[:200], now_s, str(raw or "")[:500], send_key))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def release_send_guard_failed(bid_key, phone):
    """
    실패한 발송 예약은 지워서 다음 실행 때 재시도 가능하게 둔다.
    성공 건은 sent 상태로 남겨 영구 중복 방지.
    """
    bid_key = str(bid_key or "").strip()
    phone = _clean_phone(phone)
    send_key = make_send_once_key(bid_key, phone)

    conn = _send_guard_conn()

    try:
        conn.execute(
            "DELETE FROM alimtalk_send_guard WHERE send_key=? AND status='reserved'",
            (send_key,)
        )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _dedup_is_sent_result(res):
    if res is True:
        return True

    if isinstance(res, dict):
        if res.get("sent") is True:
            return True
        if res.get("ok") is True:
            return True
        if str(res.get("ok", "")).strip().lower() in ("true", "1", "y", "yes"):
            return True
        if str(res.get("sent_ok", "")).strip() not in ("", "0", "0.0", "None", "none"):
            return True

        code = str(res.get("code") or res.get("result_code") or "").strip()
        if code in ("0", "1"):
            return True

        raw = res.get("raw")
        if isinstance(raw, dict):
            if str(raw.get("code") or raw.get("result_code") or "").strip() in ("0", "1"):
                return True
            info = raw.get("info")
            if isinstance(info, dict):
                scnt = str(info.get("scnt") or info.get("success_cnt") or "").strip()
                if scnt and scnt not in ("0", "0.0", "None", "none"):
                    return True

    if isinstance(res, str) and res.strip().upper() in ("OK", "SUCCESS"):
        return True

    return False


# ---------------------------------------------------------------------
# history override
# ---------------------------------------------------------------------

def load_send_history(keep_days: int = 30):
    """
    send_history.csv를 정규화해서 읽는다.
    반환 keys에는 canonical key와 기존 코드가 만들 수 있는 변형 key를 모두 넣는다.
    """
    history_file = globals().get("HISTORY_FILE")
    if not history_file:
        history_file = _dedup_guard_db_path().parent / "send_history.csv"
    history_file = _DedupPath(str(history_file))
    history_file.parent.mkdir(parents=True, exist_ok=True)

    if not history_file.exists():
        return set(), []

    rows = []

    try:
        with open(str(history_file), newline="", encoding="utf-8") as f:
            reader = _dedup_csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as e:
        _dedup_log(f"[HISTORY][ERR] load_send_history 실패: {e}")
        return set(), []

    today = _DedupDateTime.now().date()
    filtered = []

    for r in rows:
        s = r.get("sent_date") or r.get("sent_dt") or ""
        keep = True

        if s:
            try:
                d = _DedupDateTime.strptime(str(s).strip(), "%Y%m%d").date()
                keep = (today - d).days <= keep_days
            except Exception:
                keep = True

        if keep:
            bid_no = str(r.get("bid_no") or "").strip()
            bid_ord = str(r.get("bid_ord") or "000").strip() or "000"
            no, ordv = split_bid_key(bid_no, bid_ord)

            if no:
                rr = dict(r)
                rr["bid_no"] = no
                rr["bid_ord"] = ordv
                filtered.append(rr)
            else:
                filtered.append(r)

    keys = set()
    for r in filtered:
        bid_no = str(r.get("bid_no") or "").strip()
        bid_ord = str(r.get("bid_ord") or "000").strip() or "000"
        keys.update(_dedup_bid_key_variants(bid_no, bid_ord))

    return keys, filtered


def save_send_history(rows: list):
    """
    send_history.csv 저장 시에도 공고번호/차수 정규화.
    동시 실행 lost-update 방지용 lock + tmp replace 유지.
    """
    history_file = globals().get("HISTORY_FILE")
    if not history_file:
        history_file = _dedup_guard_db_path().parent / "send_history.csv"
    history_file = _DedupPath(str(history_file))
    history_file.parent.mkdir(parents=True, exist_ok=True)

    tmp = history_file.with_suffix(".tmp")
    lock_path = history_file.with_suffix(history_file.suffix + ".lock")
    fieldnames = ["bid_no", "bid_ord", "sent_date", "sent_ts"]

    lock_fd = None

    try:
        try:
            lock_fd = _dedup_os.open(str(lock_path), _dedup_os.O_CREAT | _dedup_os.O_RDWR, 0o644)
            fcntl_mod = globals().get("fcntl")
            if fcntl_mod is not None:
                fcntl_mod.lockf(lock_fd, fcntl_mod.LOCK_EX)
        except Exception:
            lock_fd = None

        merged = []
        keys = set()

        def _add_row(r):
            if not isinstance(r, dict):
                return

            bid_no = str(r.get("bid_no") or r.get("공고번호") or "").strip()
            bid_ord = str(r.get("bid_ord") or r.get("차수") or "000").strip() or "000"

            no, ordv = split_bid_key(bid_no, bid_ord)
            if not no:
                return

            k = make_bid_key(no, ordv)
            if k in keys:
                return

            keys.add(k)
            merged.append({
                "bid_no": no,
                "bid_ord": ordv,
                "sent_date": str(r.get("sent_date") or ""),
                "sent_ts": str(r.get("sent_ts") or ""),
            })

        if history_file.exists():
            try:
                with open(str(history_file), newline="", encoding="utf-8") as f:
                    reader = _dedup_csv.DictReader(f)
                    for r in reader:
                        _add_row(r)
            except Exception:
                pass

        for r in (rows or []):
            _add_row(r)

        with open(str(tmp), "w", newline="", encoding="utf-8") as f:
            writer = _dedup_csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in merged:
                writer.writerow(r)

        tmp.replace(history_file)
        _dedup_log(f"[HISTORY] save_send_history OK -> {history_file} (rows={len(merged)})")

    except Exception as e:
        _dedup_log(f"[HISTORY][ERR] save_send_history 실패: {e}")

    finally:
        if lock_fd is not None:
            try:
                fcntl_mod = globals().get("fcntl")
                if fcntl_mod is not None:
                    fcntl_mod.lockf(lock_fd, fcntl_mod.LOCK_UN)
            except Exception:
                pass
            try:
                _dedup_os.close(lock_fd)
            except Exception:
                pass


# ---------------------------------------------------------------------
# 기존 report key loader를 감싸서 key variant 확장
# ---------------------------------------------------------------------

try:
    _DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS
except NameError:
    _DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS = globals().get("load_existing_report_keys")


def load_existing_report_keys(*args, **kwargs):
    keys = set()

    try:
        if callable(_DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS):
            original_keys = _DEDUP_ORIG_LOAD_EXISTING_REPORT_KEYS(*args, **kwargs) or set()
            for k in original_keys:
                keys.update(_dedup_bid_key_variants(k, "000"))
    except Exception as e:
        _dedup_log(f"[REPORT][WARN] original load_existing_report_keys 실패: {e}")

    return keys


# ---------------------------------------------------------------------
# bid dedupe override
# ---------------------------------------------------------------------

def _dedup_rows_by_bid(rows):
    seen = set()
    out = []

    for row in rows or []:
        try:
            _dedup_normalize_row_bid_fields(row)
            k = _dedup_row_bid_key(row)

            if not k:
                out.append(row)
                continue

            if k in seen:
                continue

            seen.add(k)
            out.append(row)
        except Exception:
            out.append(row)

    return out


def dedup_by_bid(rows):
    return _dedup_rows_by_bid(rows)


def dedupe_by_bid(rows):
    return _dedup_rows_by_bid(rows)


# ---------------------------------------------------------------------
# TB0485 fields 정규화 wrapper
# ---------------------------------------------------------------------

try:
    _DEDUP_ORIG_BUILD_TB0485_FIELDS
except NameError:
    _DEDUP_ORIG_BUILD_TB0485_FIELDS = globals().get("build_tb0485_fields")


if callable(_DEDUP_ORIG_BUILD_TB0485_FIELDS):
    def build_tb0485_fields(row: dict) -> dict:
        fields = _DEDUP_ORIG_BUILD_TB0485_FIELDS(row)

        if not isinstance(fields, dict):
            fields = {}

        raw = row.get("원문") or {} if isinstance(row, dict) else {}
        raw_dict = raw if isinstance(raw, dict) else {}

        bid_no = (
            fields.get("bid_no")
            or raw_dict.get("bidNtceNo")
            or (row.get("공고번호") if isinstance(row, dict) else "")
            or ""
        )
        bid_ord = (
            fields.get("bid_ord")
            or raw_dict.get("bidNtceOrd")
            or (row.get("차수") if isinstance(row, dict) else "")
            or "000"
        )

        no, ordv = split_bid_key(bid_no, bid_ord)

        if no:
            fields["bid_no"] = no
            fields["bid_ord"] = ordv

            try:
                if callable(globals().get("build_detail_url")):
                    detail_url = str(fields.get("detail_url") or "")
                    if (not detail_url) or ("-000-000" in detail_url):
                        fields["detail_url"] = globals()["build_detail_url"](no, ordv)
            except Exception:
                pass

        return fields



def _dedup_is_no_send_context():
    # --no-send / dry-run 실행에서는 send_guard 예약/확정을 하지 않는다.
    # 드라이런 결과가 sent=True 형태로 반환되더라도 실제 발송 이력으로 남기지 않기 위함.
    try:
        import sys as _dedup_sys
        if "--no-send" in _dedup_sys.argv:
            return True

        for _name in ("NO_SEND", "DRY_RUN", "no_send", "dry_run"):
            _v = globals().get(_name)
            if isinstance(_v, bool) and _v:
                return True
            if str(_v).strip().lower() in ("1", "true", "y", "yes"):
                return True
    except Exception:
        pass

    return False

# ---------------------------------------------------------------------
# 발송 직전 atomic guard wrapper
# ---------------------------------------------------------------------

try:
    _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG
except NameError:
    _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG = globals().get('REDACTED_PRIVATE_VALUE')


if callable(_DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG):
    def send_tb0485_retry_and_log(phone: str, fields: dict, key: str, title: str, max_retry: int = 3) -> dict:
        """
        기존 send_tb0485_retry_and_log 호출을 감싸서
        알림톡 API 호출 전에 공고번호+수신번호 단위로 SQLite 선점한다.
        """
        if _dedup_os.getenv("N_DATA_DISABLE_SEND_GUARD", "").strip().lower() in ("1", "y", "yes", "true"):
            return _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG(
                phone=phone,
                fields=fields,
                key=key,
                title=title,
                max_retry=max_retry,
            )

        if _dedup_is_no_send_context():
            return _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG(
                phone=phone,
                fields=fields,
                key=key,
                title=title,
                max_retry=max_retry,
            )

        if not isinstance(fields, dict):
            fields = {}

        bid_no = fields.get("bid_no") or key or ""
        bid_ord = fields.get("bid_ord") or "000"

        no, ordv = split_bid_key(bid_no, bid_ord)
        bid_key = make_bid_key(no, ordv)

        if no:
            fields["bid_no"] = no
            fields["bid_ord"] = ordv

        phone_norm = _clean_phone(phone)

        if not bid_key or not phone_norm:
            _dedup_log(f"[SEND][SKIP][GUARD-EMPTY] key={bid_key!r} phone={phone!r} title={title}")
            return {
                "sent": False,
                "blocked": True,
                "guard_empty": True,
                "key": bid_key,
                "phone": phone_norm,
            }

        if not reserve_send_once(bid_key, phone_norm, title):
            _dedup_log(f"[SEND][SKIP][GUARD-DUP] {make_send_once_key(bid_key, phone_norm)} / {title}")
            return {
                "sent": False,
                "blocked": True,
                "guard_dup": True,
                "key": bid_key,
                "phone": phone_norm,
            }

        try:
            res = _DEDUP_ORIG_SEND_TB0485_RETRY_AND_LOG(
                phone=phone_norm,
                fields=fields,
                key=bid_key,
                title=title,
                max_retry=max_retry,
            )

            if isinstance(res, dict) and res.get("blocked") is True:
                # --no-send / 강제차단 / 실제 미발송 결과는 중복발송 이력으로 확정하지 않는다.
                release_send_guard_failed(bid_key, phone_norm)
            elif _dedup_is_sent_result(res):
                mark_send_guard_sent(bid_key, phone_norm, title, res)
            else:
                release_send_guard_failed(bid_key, phone_norm)

            return res

        except Exception:
            release_send_guard_failed(bid_key, phone_norm)
            raise


_dedup_log("[PATCH] SEND_DEDUP_GUARD_PATCH loaded: canonical bid key + sqlite send guard")
# === SEND_DEDUP_GUARD_PATCH_END ===




# __BID_DEDUP_FINAL_OVERRIDE_V3__

# -------------------------------------------------

# 최종 중복키 보정

# - R26BK01549829 - 000

# - R26BK01549829-000

# - R26BK01549829-001

# - R26BK01549829 / 차수 001

# 모두 중복 판단용으로 R26BK01549829-000 으로 통일

# -------------------------------------------------

import re as _bid_dedup_re



_BID_DEDUP_RE = _bid_dedup_re.compile(r"(R\d{2}BK\d+)(?:\s*-\s*(\d{1,3}))?", _bid_dedup_re.I)



def _bid_dedup_clean(v):

    s = "" if v is None else str(v)

    if s.strip().lower() in ("", "nan", "none", "null"):

        return ""



    s = s.strip().upper()



    for ch in ("－", "–", "—", "−"):

        s = s.replace(ch, "-")



    s = _bid_dedup_re.sub(r"\s+", "", s)

    return s



def split_bid_no_ord(bid_no="", bid_ord=""):

    no = _bid_dedup_clean(bid_no)

    ord_s = _bid_dedup_clean(bid_ord)



    base = ""

    ord_from_no = ""



    m = _BID_DEDUP_RE.search(no)

    if m:

        base = m.group(1).upper()

        ord_from_no = m.group(2) or ""

    else:

        if "-" in no:

            left, right = no.rsplit("-", 1)

            base = left.strip().upper()

            if _bid_dedup_re.fullmatch(r"\d+", right.strip()):

                ord_from_no = right.strip()

        else:

            base = no



    if ord_s and _bid_dedup_re.fullmatch(r"\d+", ord_s):

        ord_v = ord_s.zfill(3)[-3:]

    elif ord_from_no and _bid_dedup_re.fullmatch(r"\d+", ord_from_no):

        ord_v = ord_from_no.zfill(3)[-3:]

    else:

        ord_v = "000"



    return base, ord_v



def make_bid_key(bid_no="", bid_ord="", base_only=True):

    base, ord_v = split_bid_no_ord(bid_no, bid_ord)



    if not base:

        return ""



    # 핵심:

    # 중복 판단용 기본키는 차수를 무시하고 항상 -000으로 통일한다.

    # 그래야 정정공고 -001, -002가 같은 공고로 다시 발송되지 않는다.

    if base_only:

        return f"{base}-000"



    # 로그/상세 확인용으로만 실제 차수 보존

    return f"{base}-{ord_v}"



def _bid_row_get(row, name, default=""):

    try:

        if isinstance(row, dict):

            return row.get(name, default)

        if hasattr(row, "get"):

            return row.get(name, default)

    except Exception:

        pass

    return default



def get_bid_no_ord_from_row(row):

    raw = _bid_row_get(row, "원문", {})

    if not isinstance(raw, dict):

        raw = {}



    bid_no = (

        raw.get("bidNtceNo")

        or _bid_row_get(row, "공고번호")

        or _bid_row_get(row, "bidNtceNo")

        or _bid_row_get(row, "bid_no")

        or _bid_row_get(row, "key")

        or ""

    )



    bid_ord = (

        raw.get("bidNtceOrd")

        or _bid_row_get(row, "차수")

        or _bid_row_get(row, "공고차수")

        or _bid_row_get(row, "bidNtceOrd")

        or _bid_row_get(row, "bid_ord")

        or "000"

    )



    return bid_no, bid_ord



def make_bid_key_from_row(row, base_only=True):

    bid_no, bid_ord = get_bid_no_ord_from_row(row)

    return make_bid_key(bid_no, bid_ord, base_only=base_only)



def canonical_bid_key(*args, **kwargs):

    base_only = kwargs.pop("base_only", True)



    if len(args) == 1 and hasattr(args[0], "get"):

        return make_bid_key_from_row(args[0], base_only=base_only)



    if len(args) >= 2:

        return make_bid_key(args[0], args[1], base_only=base_only)



    if len(args) == 1:

        return make_bid_key(args[0], "", base_only=base_only)



    return ""



_canonical_bid_key = canonical_bid_key

make_canonical_bid_key = canonical_bid_key

canon_bid_key = canonical_bid_key



try:

    log("[PATCH] BID_DEDUP_FINAL_OVERRIDE_V3 active: bid order ignored for duplicate key")

except Exception:

    print("[PATCH] BID_DEDUP_FINAL_OVERRIDE_V3 active: bid order ignored for duplicate key")



# __BID_DEDUP_FINAL_OVERRIDE_V3__ END






# __CANCEL_NOTICE_SEND_V5__

# -------------------------------------------------

# 취소공고 알림 발송 보정

# - 취소공고는 일반공고와 별도 이벤트로 알림

# - 원공고가 이미 발송됐어도 취소공고는 1회 발송

# - 취소공고 자체의 반복 발송은 별도 key로 방지

# -------------------------------------------------



def _cancel_v5_get(obj, name, default=""):

    try:

        if isinstance(obj, dict):

            return obj.get(name, default)

        if hasattr(obj, "get"):

            return obj.get(name, default)

    except Exception:

        pass

    return default



def is_cancel_notice_row(row):

    raw = _cancel_v5_get(row, "원문", {})

    if not isinstance(raw, dict):

        raw = {}



    fields = [

        _cancel_v5_get(row, "공고명"),

        _cancel_v5_get(row, "공고상태"),

        _cancel_v5_get(row, "공고종류"),

        _cancel_v5_get(row, "상태"),

        raw.get("bidNtceNm"),

        raw.get("ntceKindNm"),

        raw.get("bidNtceSttusNm"),

        raw.get("bidNtceSttus"),

        raw.get("ntceDivNm"),

    ]



    text = " ".join(str(x) for x in fields if x is not None)



    return "취소" in text



def make_cancel_notice_key(row, current_key=""):

    """

    취소공고는 원공고 알림 이력과 분리해야 한다.



    기존 일반 key:

      R26BK01542443-000



    취소공고 key:

      CANCEL:C26BK01542443-001



    앞의 R을 C로 바꾸는 이유:

      기존 SEND_DEDUP_GUARD_PATCH가 R26BK... 패턴을 다시 일반 공고번호로

      정규화할 가능성이 있어, 취소공고 key가 원공고 key로 합쳐지는 것을 막기 위함.

    """

    full = ""



    try:

        full = make_bid_key_from_row(row, base_only=False)

    except Exception:

        full = ""



    if not full:

        full = str(current_key or "").strip()



    if not full:

        return ""



    safe = str(full).strip().upper()



    if safe.startswith("R"):

        safe = "C" + safe[1:]



    if safe.startswith("CANCEL:"):

        return safe



    return "CANCEL:" + safe



def prepare_cancel_notice_row(row, title=""):

    old_title = "" if title is None else str(title)



    if old_title.startswith("[취소공고]"):

        new_title = old_title

    else:

        new_title = "[취소공고] " + old_title



    try:

        if isinstance(row, dict):

            row["공고명"] = new_title



            raw = row.get("원문")

            if isinstance(raw, dict):

                raw["bidNtceNm"] = new_title

    except Exception:

        pass



    return new_title



try:

    log("[PATCH] CANCEL_NOTICE_SEND_V5 active: cancel notices will be sent")

except Exception:

    print("[PATCH] CANCEL_NOTICE_SEND_V5 active: cancel notices will be sent")



# __CANCEL_NOTICE_SEND_V5__ END






# __CANCEL_NOTICE_SEND_V5_1__

# -------------------------------------------------

# 취소공고 v5.1 보정

# - title 변수가 아직 생성되기 전이어도 [취소공고] 제목 생성

# - 취소공고 key를 일반공고와 분리: CANCEL:C26BK...-001

# - make_bid_key_from_row(row) 호출 시 취소공고는 자동으로 CANCEL key 반환

# -------------------------------------------------

import re as _cancel_v51_re



def _cancel_v51_get(obj, name, default=""):

    try:

        if isinstance(obj, dict):

            return obj.get(name, default)

        if hasattr(obj, "get"):

            return obj.get(name, default)

    except Exception:

        pass

    return default



def _cancel_v51_row_title(row):

    raw = _cancel_v51_get(row, "원문", {})

    if not isinstance(raw, dict):

        raw = {}



    return str(

        raw.get("bidNtceNm")

        or _cancel_v51_get(row, "공고명")

        or _cancel_v51_get(row, "title")

        or ""

    ).strip()



def _cancel_v51_cancelize_key(k):

    s = "" if k is None else str(k).strip().upper()



    if not s:

        return ""



    if s.startswith("CANCEL:"):

        return s



    # R26BK01542443-001 / C26BK01542443-001 모두 처리

    m = _cancel_v51_re.search(r"([RC]\d{2}BK\d+)(?:\s*-\s*(\d{1,3}))?", s)



    if m:

        base = m.group(1)

        ord_v = (m.group(2) or "001").zfill(3)[-3:]



        if base.startswith("R"):

            base = "C" + base[1:]



        return f"CANCEL:{base}-{ord_v}"



    # 그래도 못 읽으면 일반 key와 충돌하지 않도록 prefix만 붙임

    return "CANCEL:" + s



def make_cancel_notice_key(row=None, current_key=""):

    """

    취소공고 전용 key.

    일반공고 R26BK01542443-000 과 충돌하지 않도록

    CANCEL:C26BK01542443-001 형태로 저장/비교한다.

    """

    full = ""



    try:

        if row is not None:

            bid_no, bid_ord = get_bid_no_ord_from_row(row)

            full = make_bid_key(bid_no, bid_ord, base_only=False)

    except Exception:

        full = ""



    if not full:

        full = current_key



    return _cancel_v51_cancelize_key(full)



def prepare_cancel_notice_row(row, title=""):

    old_title = str(title or "").strip()



    if not old_title:

        old_title = _cancel_v51_row_title(row)



    if old_title.startswith("[취소공고]"):

        new_title = old_title

    else:

        new_title = "[취소공고] " + old_title



    try:

        if isinstance(row, dict):

            row["공고명"] = new_title

            row["title"] = new_title



            raw = row.get("원문")

            if isinstance(raw, dict):

                raw["bidNtceNm"] = new_title

    except Exception:

        pass



    return new_title



# 취소공고 row 자체가 key를 만들 때도 항상 CANCEL key로 떨어지게 보정

try:

    _CANCEL_V51_ORIG_MAKE_BID_KEY_FROM_ROW = make_bid_key_from_row



    def make_bid_key_from_row(row, base_only=True):

        try:

            if is_cancel_notice_row(row):

                ck = make_cancel_notice_key(row)

                if ck:

                    return ck

        except Exception:

            pass



        return _CANCEL_V51_ORIG_MAKE_BID_KEY_FROM_ROW(row, base_only=base_only)



except Exception:

    pass



try:

    log("[PATCH] CANCEL_NOTICE_SEND_V5_1 active: title/key fixed for cancel notices")

except Exception:

    print("[PATCH] CANCEL_NOTICE_SEND_V5_1 active: title/key fixed for cancel notices")



# __CANCEL_NOTICE_SEND_V5_1__ END





# __CANCEL_NOTICE_SEND_V5_2_UNSHADOW_BID_KEY__


# __CANCEL_NOTICE_SEND_V5_3_BID_KEY_GLOBAL_CALL__

# -------------------------------------------------

# bid_key 이름 충돌 방지

# -------------------------------------------------

# main() 내부에 bid_key = ... 대입이 있으면 파이썬은 bid_key(raw)를

# 지역변수 호출로 해석한다. 그래서 전역 함수 bid_key 호출은 이 wrapper를 통해 수행한다.

def _n_data_call_bid_key(*args, **kwargs):

    return globals()["bid_key"](*args, **kwargs)



# __CANCEL_NOTICE_SEND_V5_3_BID_KEY_GLOBAL_CALL__ END






# __CANCEL_NOTICE_SEND_V5_4_FORCE_KEY_TITLE__

# -------------------------------------------------

# 취소공고 key/title 최종 보정

# - 취소공고는 로그/발송 직전 key를 CANCEL:C26BK... 로 강제

# - 제목 앞에 [취소공고] 강제

# -------------------------------------------------

import re as _cancel_v54_re



def _cancel_v54_get(obj, name, default=""):

    try:

        if isinstance(obj, dict):

            return obj.get(name, default)

        if hasattr(obj, "get"):

            return obj.get(name, default)

    except Exception:

        pass

    return default



def _cancel_v54_base_title(row, old_title=""):

    s = str(old_title or "").strip()



    if not s:

        raw = _cancel_v54_get(row, "원문", {})

        if not isinstance(raw, dict):

            raw = {}



        s = str(

            raw.get("bidNtceNm")

            or _cancel_v54_get(row, "공고명")

            or _cancel_v54_get(row, "title")

            or ""

        ).strip()



    # "취소공고 A동..."이면 "[취소공고] A동..."으로 보기 좋게 정리

    if s.startswith("[취소공고]"):

        return s



    if s.startswith("취소공고"):

        s = s.replace("취소공고", "", 1).strip()



    return "[취소공고] " + s



def _cancel_v54_cancel_key(row=None, old_key=""):

    old_key = str(old_key or "").strip().upper()



    # 우선 기존 helper가 있으면 사용

    try:

        if row is not None:

            k = make_cancel_notice_key(row, old_key)

            if k:

                return str(k).strip().upper()

    except Exception:

        pass



    # row에서 직접 공고번호/차수 추출

    full = ""

    try:

        if row is not None:

            bid_no, bid_ord = get_bid_no_ord_from_row(row)

            full = make_bid_key(bid_no, bid_ord, base_only=False)

    except Exception:

        full = ""



    if not full:

        full = old_key



    s = str(full or "").strip().upper()



    if s.startswith("CANCEL:"):

        return s



    m = _cancel_v54_re.search(r"([RC]\d{2}BK\d+)(?:\s*-\s*(\d{1,3}))?", s)

    if m:

        base = m.group(1)

        ord_v = (m.group(2) or "001").zfill(3)[-3:]



        if base.startswith("R"):

            base = "C" + base[1:]



        return f"CANCEL:{base}-{ord_v}"



    return "CANCEL:" + s if s else ""



def _cancel_v54_apply(row, old_key="", old_title=""):

    new_key = _cancel_v54_cancel_key(row, old_key)

    new_title = _cancel_v54_base_title(row, old_title)



    # 이후 코드가 row에서 제목을 다시 읽더라도 [취소공고]가 유지되도록 row 자체도 수정

    try:

        if isinstance(row, dict):

            row["공고명"] = new_title

            row["title"] = new_title



            raw = row.get("원문")

            if isinstance(raw, dict):

                raw["bidNtceNm"] = new_title

    except Exception:

        pass



    return new_key, new_title



try:

    log("[PATCH] CANCEL_NOTICE_SEND_V5_4 active: force CANCEL key/title before send log")

except Exception:

    print("[PATCH] CANCEL_NOTICE_SEND_V5_4 active: force CANCEL key/title before send log")



# __CANCEL_NOTICE_SEND_V5_4_FORCE_KEY_TITLE__ END




# === CANCEL_NOTICE_FINAL_FIX_BEGIN ===
# 취소공고 최종 처리. 이전의 실험성 V5 패치보다 아래 정의가 최종 우선된다.
import sqlite3 as _cancel_sqlite3

KNOWN_CANCELLED_NOTICES = {
    ("R26BK01552481", "001"),
}

# TEST/PROD 환경의 NAS_BASE에 맞춰 발송 이력 파일을 분리한다.
try:
    _SENT_FILE = str(Path(NAS_BASE) / "sent_keys.txt")
except Exception:
    pass

_CANCEL_STATUS_FIELDS = (
    "bidNtceSttusNm",
    "bidNtceSttus",
    "ntceKindNm",
    "ntceDivNm",
    "bidNtceKindNm",
    "bidNtceDtlSttusNm",
    "notice_status",
    "공고상태",
    "공고종류",
    "상태",
)

_CANCEL_TITLE_FIELDS = (
    "bidNtceNm",
    "공고명",
    "title",
    "bid_name",
)

_CANCEL_FLAG_FIELDS = (
    "cancelYn",
    "cnclYn",
    "ntceCnclYn",
    "bidNtceCnclYn",
    "canceledYn",
    "cancelledYn",
    "cancel_notice",
    "_cancel_notice",
)


def _cancel_get(obj, name, default=""):
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)
        if hasattr(obj, "get"):
            return obj.get(name, default)
    except Exception:
        pass
    return default


def _cancel_raw(row):
    raw = _cancel_get(row, "원문", {})
    return raw if isinstance(raw, dict) else {}


def _clean_notice_ord(value, default="000"):
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        digits = default
    return digits[-3:].zfill(3)


def notice_identity(row):
    raw = _cancel_raw(row)

    bid_no = (
        _cancel_get(row, "공고번호")
        or _cancel_get(row, "bidNtceNo")
        or _cancel_get(row, "bid_no")
        or raw.get("bidNtceNo")
        or raw.get("공고번호")
        or ""
    )

    bid_ord = (
        _cancel_get(row, "차수")
        or _cancel_get(row, "bidNtceOrd")
        or _cancel_get(row, "bid_ord")
        or raw.get("bidNtceOrd")
        or raw.get("차수")
        or ""
    )

    bid_no_text = str(bid_no or "").strip().upper()
    match = re.search(
        r"(R\d{2}BK\d+)(?:\s*[-_]\s*(\d{1,3}))?",
        bid_no_text,
        re.I,
    )

    if match:
        base = match.group(1).upper()
        ord_from_no = match.group(2) or ""
    else:
        base = re.sub(r"\s+", "", bid_no_text)
        ord_from_no = ""

    order = _clean_notice_ord(bid_ord or ord_from_no or "000")
    return base, order


def is_cancel_notice(row):
    base, order = notice_identity(row)
    if (base, order) in KNOWN_CANCELLED_NOTICES:
        return True

    raw = _cancel_raw(row)

    for source in (row, raw):
        for field in _CANCEL_FLAG_FIELDS:
            value = str(_cancel_get(source, field, "") or "").strip().lower()
            if value in ("y", "yes", "true", "1"):
                return True

    texts = []
    for source in (row, raw):
        for field in _CANCEL_STATUS_FIELDS + _CANCEL_TITLE_FIELDS:
            value = _cancel_get(source, field, "")
            if value not in (None, ""):
                texts.append(str(value))

    status_text = " ".join(texts).lower()
    return "취소" in status_text or "cancel" in status_text


def is_cancel_notice_row(row):
    return is_cancel_notice(row)


def prepare_cancel_notice_row_final(row):
    if not isinstance(row, dict):
        return row

    base, order = notice_identity(row)
    raw = _cancel_raw(row)

    title = str(
        row.get("공고명")
        or row.get("title")
        or raw.get("bidNtceNm")
        or (base + " 취소공고" if base else "취소공고")
    ).strip()

    if title.startswith("[취소공고]"):
        fixed_title = title
    else:
        if title.startswith("취소공고"):
            title = title[len("취소공고"):].strip(" :-")
        fixed_title = "[취소공고] " + (title or base or "공고")

    row["공고번호"] = base or str(row.get("공고번호", "") or "").strip()
    row["차수"] = order
    row["공고명"] = fixed_title
    row["title"] = fixed_title
    row["_cancel_notice"] = True
    row["cancel_notice"] = True
    row["event_type"] = "cancel"

    if not isinstance(row.get("원문"), dict):
        row["원문"] = {}

    row["원문"].update({
        "bidNtceNo": row["공고번호"],
        "bidNtceOrd": order,
        "bidNtceNm": fixed_title,
        "ntceKindNm": row["원문"].get("ntceKindNm") or "취소공고",
        "bidNtceSttusNm": row["원문"].get("bidNtceSttusNm") or "취소",
    })

    return row


def notice_event_key(row):
    base, order = notice_identity(row)
    if not base:
        return ""

    if is_cancel_notice(row):
        cancel_base = "C" + base[1:] if base.startswith("R") else base
        return "CANCEL:%s-%s" % (cancel_base, order)

    # 기존 정책 유지: 일반 정정 차수는 같은 기본 공고로 중복 처리한다.
    return "%s-000" % base


def make_cancel_notice_key(row=None, current_key=""):
    if row is not None:
        key = notice_event_key(row)
        if key.startswith("CANCEL:"):
            return key

    text = str(current_key or "").strip().upper()
    match = re.search(
        r"([RC]\d{2}BK\d+)(?:\s*[-_]\s*(\d{1,3}))?",
        text,
        re.I,
    )
    if not match:
        return ("CANCEL:" + text) if text else ""

    base = match.group(1).upper()
    order = _clean_notice_ord(match.group(2) or "001", "001")
    if base.startswith("R"):
        base = "C" + base[1:]
    return "CANCEL:%s-%s" % (base, order)


def make_bid_key_from_row(row, base_only=True):
    if is_cancel_notice(row):
        return notice_event_key(row)

    bid_no, bid_ord = get_bid_no_ord_from_row(row)
    return make_bid_key(bid_no, bid_ord, base_only=base_only)


def normalize_phone_list(values):
    out = []
    seen = set()

    for value in values or []:
        phone = re.sub(r"\D", "", str(value or ""))
        if not phone or phone in seen:
            continue
        seen.add(phone)
        out.append(phone)

    return out


def _sent_key(fields, phone=None):
    key = notice_event_key(fields)
    if not key:
        return ""

    if phone:
        phone_norm = re.sub(r"\D", "", str(phone or ""))
        if phone_norm:
            key = "%s|%s" % (key, phone_norm)

    return key


def _sent_file_candidates():
    paths = []

    for candidate in (
        globals().get("_SENT_FILE"),
        str(globals().get("NAS_BASE", "") / "sent_keys.txt")
        if globals().get("NAS_BASE")
        else "",
    ):
        if candidate and candidate not in paths:
            paths.append(candidate)

    return paths


def _load_receivers_from_sent_files(base):
    phones = set()

    for sent_path in _sent_file_candidates():
        try:
            path = Path(sent_path)
            if not path.exists():
                continue

            with open(path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if "|" not in line:
                        continue

                    key_part, phone = line.rsplit("|", 1)
                    key_upper = key_part.upper()

                    if key_upper.startswith("CANCEL:"):
                        continue
                    if base not in key_upper:
                        continue

                    phones.update(normalize_phone_list([phone]))
        except Exception as exc:
            log("[CANCEL][HISTORY][SENT_FILE_ERR] %s: %s" % (sent_path, exc))

    return phones


def _load_receivers_from_send_guard(base):
    phones = set()
    db_candidates = []

    try:
        db_candidates.append(
            Path(__file__).resolve().parent
            / "split"
            / "history"
            / "send_guard.sqlite3"
        )
    except Exception:
        pass

    try:
        db_candidates.append(
            Path(BASE_DIR) / "split" / "history" / "send_guard.sqlite3"
        )
    except Exception:
        pass

    seen_paths = set()

    for db_path in db_candidates:
        db_path = Path(db_path)
        if db_path in seen_paths or not db_path.exists():
            continue
        seen_paths.add(db_path)

        conn = None
        try:
            conn = _cancel_sqlite3.connect(str(db_path), timeout=10)
            rows = conn.execute(
                "SELECT bid_key, phone FROM alimtalk_send_guard "
                "WHERE status='sent' AND UPPER(bid_key) LIKE ?",
                ("%%%s%%" % base,),
            ).fetchall()

            for bid_key_value, phone in rows:
                if str(bid_key_value or "").upper().startswith("CANCEL:"):
                    continue
                phones.update(normalize_phone_list([phone]))
        except Exception as exc:
            log("[CANCEL][HISTORY][SQLITE_ERR] %s: %s" % (db_path, exc))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    return phones


def _clean_excel_value(value):
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return value


def load_previous_notice_snapshot(base):
    phones = set()
    snapshot = None

    file_groups = []
    try:
        file_groups.extend(sorted(REPORT_DIR.glob("발송공고_*.xlsx"), reverse=True)[:80])
    except Exception:
        pass
    try:
        file_groups.extend(sorted(RAW_DIR.glob("입찰공고_clean_*.xlsx"), reverse=True)[:80])
    except Exception:
        pass

    seen_files = set()

    for excel_path in file_groups:
        if excel_path in seen_files:
            continue
        seen_files.add(excel_path)

        try:
            df = pd.read_excel(excel_path, dtype=object)
            if "공고번호" not in df.columns:
                continue

            for _, excel_row in df.iterrows():
                row_dict = {
                    str(k): _clean_excel_value(v)
                    for k, v in excel_row.to_dict().items()
                }
                row_base, _ = notice_identity(row_dict)
                if row_base != base:
                    continue

                if snapshot is None:
                    snapshot = row_dict

                phones.update(
                    normalize_phone_list([
                        row_dict.get("발송수신번호", ""),
                        *str(row_dict.get("수신번호", "") or "").split(","),
                    ])
                )

            if snapshot is not None and phones:
                break
        except Exception:
            continue

    return snapshot, sorted(phones)


def load_previous_notice_receivers(row):
    base, _ = notice_identity(row)
    if not base:
        return []

    phones = set()
    phones.update(_load_receivers_from_sent_files(base))
    phones.update(_load_receivers_from_send_guard(base))

    if not phones:
        _, report_phones = load_previous_notice_snapshot(base)
        phones.update(report_phones)

    return sorted(phones)


def _to_int_safe(value):
    try:
        if pd.isna(value):
            return 0
    except Exception:
        pass

    text = str(value or "").replace(",", "").replace("원", "").strip()
    if not text:
        return 0

    try:
        return int(float(text))
    except Exception:
        return 0


def _known_cancel_row(base, order):
    snapshot, report_phones = load_previous_notice_snapshot(base)
    row = dict(snapshot or {})

    row.setdefault("공고업종코드", row.get("indstrytyCd", ""))
    row.setdefault("공고업종명", row.get("indstrytyNm", ""))
    row.setdefault("indstrytyCd", row.get("공고업종코드", ""))
    row.setdefault("indstrytyNm", row.get("공고업종명", ""))
    row.setdefault("대표지역", row.get("local_region", ""))
    row.setdefault("local_region", row.get("대표지역", ""))
    row.setdefault("공동도급지역", "")
    row.setdefault("공동도급지역_추가", "")
    row.setdefault("공동도급비율", "")
    row.setdefault("입찰마감일시", "")
    row.setdefault("detail_url", "")
    row.setdefault("발주기관", "")
    row.setdefault("낙찰방법세부기준", "")
    row.setdefault("scope", "전국" if row.get("대표지역") == "전국" else "지역")
    row.setdefault("mainCnsttyNm", "")

    row["추정가격"] = _to_int_safe(row.get("추정가격", 0))
    row["기초금액"] = _to_int_safe(row.get("기초금액", 0))
    row["공고번호"] = base
    row["차수"] = order
    row["원문"] = {
        "bidNtceNo": base,
        "bidNtceOrd": order,
        "bidNtceNm": str(row.get("공고명", "") or ""),
        "ntceKindNm": "취소공고",
        "bidNtceSttusNm": "취소",
    }

    prepare_cancel_notice_row_final(row)

    history_phones = load_previous_notice_receivers(row)
    row["_cancel_receivers"] = normalize_phone_list(
        list(report_phones) + list(history_phones)
    )

    return row


def inject_known_cancel_notices(rows):
    out = list(rows or [])
    present = {notice_identity(row) for row in out}

    for base, order in sorted(KNOWN_CANCELLED_NOTICES):
        if (base, order) in present:
            continue

        row = _known_cancel_row(base, order)

        if not row.get("_cancel_receivers") and not row.get("공고업종코드"):
            log(
                "[CANCEL][KNOWN][WAIT] %s-%s: "
                "원공고 수신 이력과 업종 정보를 찾지 못했습니다."
                % (base, order)
            )
            continue

        known_receivers = normalize_phone_list(row.get("_cancel_receivers", []))
        if known_receivers:
            known_fields = build_kakao_fields(row)
            if all(is_already_sent(known_fields, phone) for phone in known_receivers):
                log(
                    "[CANCEL][KNOWN][DONE] %s: 모든 수신자 발송 완료"
                    % notice_event_key(row)
                )
                continue

        out.append(row)
        present.add((base, order))
        log(
            "[CANCEL][KNOWN][INJECT] %s receivers=%s title=%s"
            % (
                notice_event_key(row),
                ",".join(row.get("_cancel_receivers", [])) or "없음",
                row.get("공고명", ""),
            )
        )

    return out


def apply_receivers(rows):
    for row in rows:
        if is_cancel_notice(row):
            prepare_cancel_notice_row_final(row)

            receivers = normalize_phone_list(
                row.get("_cancel_receivers", [])
            )
            if not receivers:
                receivers = load_previous_notice_receivers(row)
            if not receivers:
                receivers = normalize_phone_list(decide_receivers(row))

            row["_cancel_receivers"] = receivers
        else:
            receivers = normalize_phone_list(decide_receivers(row))

        row["수신번호"] = ",".join(receivers)
        row["알림대상"] = "Y" if receivers else "N"

        if is_cancel_notice(row) and not receivers:
            log(
                "[CANCEL][SKIP_NO_RECEIVER] %s / %s"
                % (notice_event_key(row), row.get("공고명", ""))
            )

    return rows


def build_kakao_fields(row):
    if is_cancel_notice(row):
        prepare_cancel_notice_row_final(row)

    amount = budget_amount(row)
    if amount <= 0:
        amount = _to_int_safe(row.get("추정가격", 0))

    return {
        "industry": row.get("공고업종명", ""),
        "bid_name": row.get("공고명", ""),
        "close_time": row.get("입찰마감일시", ""),
        "joint_region": alimtalk_joint_region(row),
        "joint_rate": alimtalk_joint_ratio(row),
        "amount": amount,
        "amount_str": "%s" % format(amount, ","),
        "bid_no": row.get("공고번호", ""),
        "bid_ord": row.get("차수", "000"),
        "detail_url": row.get("detail_url", ""),
        "region": row.get("대표지역", "") or row.get("local_region", ""),
        "org_name": row.get("발주기관", ""),
        "낙찰방법세부기준": row.get("낙찰방법세부기준", ""),
        "cancel_notice": is_cancel_notice(row),
        "_cancel_notice": is_cancel_notice(row),
        "event_type": "cancel" if is_cancel_notice(row) else "notice",
    }


def _send_result_ok(result):
    checker = globals().get("_dedup_is_sent_result")
    if callable(checker):
        try:
            return bool(checker(result))
        except Exception:
            pass

    if result is True:
        return True
    if isinstance(result, dict):
        if result.get("ok") is True or result.get("sent") is True:
            return True
        return str(result.get("code", "")).strip() == "0"
    return False


def send_kakao_one(phone, row, no_send=False):
    from kakao_send_tb0485 import send_for_item as _send_for_item

    phone = re.sub(r"\D", "", str(phone or ""))
    if not phone:
        return False

    if is_cancel_notice(row):
        prepare_cancel_notice_row_final(row)

    fields = build_kakao_fields(row)
    key = _sent_key(fields)
    title = fields.get("bid_name", "")

    if no_send or os.environ.get("HARD_NO_SEND", "") == "1":
        log("[SAFE] DRY RUN TB0485: key=%s -> %s / %s" % (key, phone, title))
        return False

    if is_already_sent(fields, phone):
        log("[SEND][SKIP_ALREADY] %s -> %s" % (key, phone))
        return False

    guard_reserved = False
    reserve = globals().get("reserve_send_once")
    release = globals().get("release_send_guard_failed")
    mark_guard = globals().get("mark_send_guard_sent")

    try:
        if callable(reserve):
            guard_reserved = bool(reserve(key, phone, title))
            if not guard_reserved:
                log("[SEND][SKIP_GUARD] %s -> %s" % (key, phone))
                return False

        try:
            result = _send_for_item(phone, fields, dry_run=False)
        except TypeError:
            result = _send_for_item(fields, phone, dry_run=False)

        log("[SEND] RES TB0485 %s -> %s: %s" % (key, phone, result))

        if _send_result_ok(result):
            mark_sent(fields, phone)
            if guard_reserved and callable(mark_guard):
                mark_guard(key, phone, title, repr(result))
            log("[SEND][MARK_SENT] %s -> %s" % (key, phone))
            return True

        if guard_reserved and callable(release):
            release(key, phone)
        return False

    except Exception as exc:
        if guard_reserved and callable(release):
            try:
                release(key, phone)
            except Exception:
                pass
        log("[SEND][ERR] %s -> %s: %s" % (key, phone, exc))
        return False


log(
    "[PATCH] CANCEL_NOTICE_FINAL_FIX active: "
    "R26BK01552481-001 + generic cancel status + separate sent key"
)
# === CANCEL_NOTICE_FINAL_FIX_END ===


if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        log("[FATAL] %s: %s" % (type(e).__name__, e))

        traceback.print_exc()

        sys.exit(1)