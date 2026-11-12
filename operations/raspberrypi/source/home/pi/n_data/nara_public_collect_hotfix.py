
# -*- coding: utf-8 -*-



import math

import time

import requests



URI_BID_11 = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"



PAGE_SIZE = 999

TIMEOUT = 25





def _to_dt(v):

    s = str(v or "")

    if "-" in s or ":" in s:

        from datetime import datetime

        try:

            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d%H%M")

        except Exception:

            pass

    return "".join(ch for ch in s if ch.isdigit())[:12]





def _items(data):

    body = (data or {}).get("response", {}).get("body", {})

    items = body.get("items", {})

    item = items.get("item", []) if isinstance(items, dict) else items

    if item is None:

        return []

    if isinstance(item, dict):

        return [item]

    if isinstance(item, list):

        return item

    return []





def _total(data):

    body = (data or {}).get("response", {}).get("body", {})

    try:

        return int(body.get("totalCount") or 0)

    except Exception:

        return 0





def _call(api_key, params):

    p = dict(params)

    p["serviceKey"] = api_key

    p["type"] = "json"



    r = requests.get(URI_BID_11, params=p, timeout=TIMEOUT)

    r.raise_for_status()

    return r.json()





def _fetch_pages(api_key, bgn, end, ind_code=None):

    rows = []

    page = 1



    while True:

        params = {

            "pageNo": page,

            "numOfRows": PAGE_SIZE,

            "inqryDiv": "1",

            "inqryBgnDt": bgn,

            "inqryEndDt": end,

            "bidClseExcpYn": "N",

            "intrntnlDivCd": "1",

        }



        if ind_code:

            params["indstrytyCd"] = str(ind_code).zfill(4)



        data = _call(api_key, params)

        items = _items(data)

        total = _total(data)



        for r in items:

            if ind_code and not str(r.get("indstrytyCd") or "").strip():

                r["indstrytyCd"] = str(ind_code).zfill(4)

            rows.append(r)



        if total <= 0:

            break



        max_page = int(math.ceil(total / float(PAGE_SIZE)))

        if page >= max_page:

            break



        page += 1

        time.sleep(0.1)



    return rows





def _key(row):

    no = str(row.get("bidNtceNo") or row.get("입찰번호") or "").strip()

    od = str(row.get("bidNtceOrd") or "000").strip() or "000"

    return f"{no}-{od}"





def collect_bids_range(api_key, start_dt=None, end_dt=None, indstry_codes=None, target_inds=None, min_budget=0, **kwargs):

    bgn = _to_dt(start_dt or kwargs.get("bgn_dt") or kwargs.get("inqryBgnDt"))

    end = _to_dt(end_dt or kwargs.get("end_dt") or kwargs.get("inqryEndDt"))



    codes = indstry_codes or target_inds or kwargs.get("inds") or []

    codes = [str(c).zfill(4) for c in codes]



    all_rows = []



    # 1) 기존 방식: 업종코드별 조회

    for code in codes:

        all_rows.extend(_fetch_pages(api_key, bgn, end, code))



    # 2) 보강 방식: 업종코드 없이 전체 조회 1회

    #    R26BK01486034처럼 업종코드 조건에서 빠지는 공고 보완

    all_rows.extend(_fetch_pages(api_key, bgn, end, None))



    # 3) 공고번호+차수 기준 중복 제거

    dedup = {}

    for r in all_rows:

        k = _key(r)

        if k.strip("-"):

            dedup[k] = r



    return list(dedup.values())





try:

    from nara_public_collect import enrich_cnstwk_sucs_method

except Exception:

    def enrich_cnstwk_sucs_method(*args, **kwargs):

        return 0

