
# -*- coding: utf-8 -*-

"""

나라장터 API 누락 공고 자동 추적 시스템



역할:

1. 이미 수집된 공고번호 주변 범위 생성

2. 빠진 번호를 단건 API로 재조회

3. 조회 성공한 공고를 api_rows에 추가

4. 중복은 bidNtceNo-bidNtceOrd 기준 제거

"""



import re

import time

import requests



DETAIL_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"



TIMEOUT = 15

SLEEP_SEC = 0.12



PREFIX_RE = re.compile(r"^(R\d+BK)(\d+)$")





def _log(msg):

    print(msg, flush=True)





def _items(data):

    body = (data or {}).get("response", {}).get("body", {})

    items = body.get("items", {})

    if isinstance(items, dict):

        item = items.get("item", [])

    else:

        item = items



    if item is None:

        return []

    if isinstance(item, dict):

        return [item]

    if isinstance(item, list):

        return item

    return []





def _key(row):

    no = str(row.get("bidNtceNo") or row.get("공고번호") or "").strip()

    od = str(row.get("bidNtceOrd") or row.get("차수") or "000").strip()

    return f"{no}-{od}"





def _bid_no(row):

    return str(row.get("bidNtceNo") or row.get("공고번호") or "").strip()





def _parse_bid_no(bid_no):

    """

    R26BK01486034 -> ("R26BK", 1486034)

    """

    s = str(bid_no or "").strip()

    m = PREFIX_RE.match(s)

    if not m:

        return None, None

    return m.group(1), int(m.group(2))





def _make_candidate_bid_numbers(rows, window=3, max_candidates=300):

    """

    수집된 번호 주변 +/- window 범위 후보 생성.

    예:

      01486036이 있으면 01486033~01486039 확인

    """

    parsed = []

    for r in rows:

        p, n = _parse_bid_no(_bid_no(r))

        if p and n:

            parsed.append((p, n))



    if not parsed:

        return []



    existing = {f"{p}{n:08d}" for p, n in parsed}

    candidates = []



    for p, n in parsed:

        for x in range(n - window, n + window + 1):

            if x <= 0:

                continue

            bid = f"{p}{x:08d}"

            if bid not in existing:

                candidates.append(bid)



    # 중복 제거 + 과도한 호출 방지

    dedup = []

    seen = set()

    for bid in candidates:

        if bid not in seen:

            seen.add(bid)

            dedup.append(bid)



    return dedup[:max_candidates]





def fetch_by_bid_no(api_key, bid_no):

    """

    공고번호 단건 조회.

    API가 bidNtceNo 조건을 지원하지 않거나 응답이 없으면 [] 반환.

    """

    params = {

        "serviceKey": api_key,

        "type": "json",

        "pageNo": 1,

        "numOfRows": 10,

        "bidNtceNo": bid_no,

    }



    try:

        r = requests.get(DETAIL_URL, params=params, timeout=TIMEOUT)

        r.raise_for_status()

        data = r.json()

        rows = _items(data)

    except Exception as e:

        _log(f"[MISSING][ERR] bid={bid_no} {type(e).__name__}: {e}")

        return []



    result = []

    for row in rows:

        if str(row.get("bidNtceNo") or "").strip() == bid_no:

            result.append(row)



    return result





def enrich_missing_bids(api_key, rows, window=3, max_candidates=300, must_check=None):

    """

    main_send.py에서 api_rows 수집 직후 호출.

    """

    if not isinstance(rows, list):

        return rows, 0



    before = len(rows)



    existing_keys = {_key(r) for r in rows}

    existing_bidnos = {_bid_no(r) for r in rows}



    candidates = _make_candidate_bid_numbers(

        rows,

        window=window,

        max_candidates=max_candidates,

    )



    if must_check:

        for bid in must_check:

            bid = str(bid).strip()

            if bid and bid not in existing_bidnos and bid not in candidates:

                candidates.insert(0, bid)



    _log(f"[MISSING] candidates={len(candidates)} window={window}")



    added = 0



    for i, bid in enumerate(candidates, 1):

        extra_rows = fetch_by_bid_no(api_key, bid)



        if not extra_rows:

            continue



        for r in extra_rows:

            k = _key(r)

            if k not in existing_keys:

                rows.append(r)

                existing_keys.add(k)

                existing_bidnos.add(_bid_no(r))

                added += 1

                _log(f"[MISSING][ADD] {k} / {r.get('bidNtceNm', '')}")



        time.sleep(SLEEP_SEC)



    _log(f"[MISSING] before={before} after={len(rows)} added={added}")

    return rows, added

