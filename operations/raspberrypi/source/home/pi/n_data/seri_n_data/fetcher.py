
# -*- coding: utf-8 -*-

import time



from .config import API_BASE, TARGET_INDS

from .utils import _norm, log, get_service_key, safe_get



def fetch_ind(ind, bgn_dt, end_dt, retries=3, timeout=15):

    key = get_service_key()

    if not key:

        log("[ERR] SERVICE_KEY missing")

        return []



    num = 999

    all_rows = []

    page = 1



    while True:

        params = {

            "serviceKey": key,

            "type": "json",

            "numOfRows": num,

            "pageNo": page,

            "inqryDiv": 1,

            "inqryBgnDt": bgn_dt,

            "inqryEndDt": end_dt,

            "indstrytyCd": ind,

        }



        tries = 0

        while True:

            tries += 1

            try:

                r = safe_get(API_BASE, params=params, timeout=timeout)

                r.raise_for_status()

                data = r.json()

                break

            except Exception as e:

                if tries >= retries:

                    log(f"[ERR] fetch_ind {ind} page={page}: {e}")

                    return all_rows

                time.sleep(1.0 * tries)



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

                "공고업종코드": _norm(ind),

                "공고번호": _norm(it.get("bidNtceNo")),

                "차수": _norm(it.get("bidNtceOrd")),

                "공고명": _norm(it.get("bidNtceNm")),

                "입찰마감일시": _norm(it.get("bidClseDt")),

                "공동도급지역": _norm(it.get("prtcptLmtRgnNm")),

                "수요지역": _norm(it.get("dmndInsttLocplcNm")),

                "원문": it,

            }

            out.append(row)



        log(f"[HTTP] ind={ind} page={page} count={len(out)}")

        all_rows.extend(out)



        if len(out) < num:

            break

        page += 1



    log(f"[HTTP] ind={ind} total={len(all_rows)}")

    return all_rows



def filter_rows(rows):

    filtered = [r for r in rows if (r.get("공고업종코드") in TARGET_INDS)]

    log(f"[FILTER] {len(filtered)} rows")

    return filtered


