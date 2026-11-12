
# -*- coding: utf-8 -*-

"""

region_filter.py (TEST CLEAN)

- 지역 분류: classify_region

- 전국판정(10억 우선): infer_is_nationwide_by_amount_first

- 수신자 결정: companys.xlsx 기반 decide_receivers  (중요)

"""



import os

import re

from typing import Dict, Any, List



TEN_EOK = 1_000_000_000  # 10억원

VALID_INDS = {"0037", "0038", "0039", "0040", "6202"}



# -------------------------------------------------

# 지역 표준화

# -------------------------------------------------

def classify_region(text: str) -> str:

    if not isinstance(text, str):

        return ""

    t = text.strip()

    if not t:

        return ""



    tt = re.sub(r"[\(\)\[\],/·\s]+", " ", t)



    if "전국" in tt:

        return "전국"



    norm_map = {

        "서울특별시": "서울", "서울시": "서울",

        "부산광역시": "부산", "부산시": "부산",

        "대구광역시": "대구", "대구시": "대구",

        "인천광역시": "인천", "인천시": "인천",

        "광주광역시": "광주", "광주시": "광주",

        "대전광역시": "대전", "대전시": "대전",

        "울산광역시": "울산", "울산시": "울산",

        "세종특별자치시": "세종", "세종시": "세종",

        "경기도": "경기",

        "강원특별자치도": "강원", "강원도": "강원",

        "충청북도": "충북", "충북도": "충북",

        "충청남도": "충남", "충남도": "충남",

        "전북특별자치도": "전북", "전라북도": "전북", "전북도": "전북",

        "전라남도": "전남", "전남도": "전남",

        "경상북도": "경북", "경북도": "경북",

        "경상남도": "경남", "경남도": "경남",

        "제주특별자치도": "제주", "제주도": "제주",

    }

    for k, v in norm_map.items():

        if k in tt:

            return v



    patterns = [

        ("서울", ["서울"]),

        ("부산", ["부산"]),

        ("대구", ["대구"]),

        ("인천", ["인천"]),

        ("광주", ["광주"]),

        ("대전", ["대전"]),

        ("울산", ["울산"]),

        ("세종", ["세종"]),

        ("경기", ["경기", "경기도"]),

        ("강원", ["강원", "강원도", "강원특별자치도"]),

        ("충북", ["충북", "충청북도"]),

        ("충남", ["충남", "충청남도"]),

        ("전북", ["전북", "전라북도", "전북특별자치도"]),

        ("전남", ["전남", "전라남도"]),

        ("경북", ["경북", "경상북도"]),

        ("경남", ["경남", "경상남도"]),

        ("제주", ["제주", "제주도", "제주특별자치도"]),

    ]

    for rep, keys in patterns:

        for k in keys:

            if k in tt:

                return rep



    return "기타"





def _to_int_safe(x, default=0):

    try:

        if x is None:

            return default

        if isinstance(x, (int, float)):

            return int(x)

        ss = str(x).strip().replace(",", "")

        if ss == "" or ss.lower() in ("none", "n/a", "nan"):

            return default

        return int(float(ss))

    except Exception:

        return default





def infer_is_nationwide_by_amount_first(item: dict):

    """

    return: (is_nationwide: bool|None, reason: str)

    우선순위:

      1) PresmptPrce(추정가격) 10억 기준

      2) sucsfbidMthdNm 문구에서 10억 미만/이상 파싱 (보조)

    """

    pres = _to_int_safe(item.get("PresmptPrce") or item.get("presmptPrce") or item.get("추정가격") or item.get("presmptPrceAmt"))

    if pres > 0:

        if pres >= TEN_EOK:

            return True, f"PresmptPrce>=10억({pres})"

        return False, f"PresmptPrce<10억({pres})"



    txt = str(item.get("sucsfbidMthdNm") or item.get("낙찰방법세부기준") or "").strip()

    if not txt:

        return None, "no PresmptPrce and no sucsfbidMthdNm"



    ss = txt.replace("억원", "억 원")

    if re.search(r"10\s*억\s*원\s*미만", ss):

        return False, "sucsfbidMthdNm says <10억"

    if re.search(r"10\s*억\s*원\s*이상", ss):

        return True, "sucsfbidMthdNm says >=10억"

    if re.search(r"30\s*억\s*원\s*미만", ss) and re.search(r"10\s*억\s*원\s*이상", ss):

        return True, "sucsfbidMthdNm says 10억 이상(30억 미만 구간)"

    return None, "sucsfbidMthdNm not matched"





# -------------------------------------------------

# companys.xlsx 로딩/매칭

# -------------------------------------------------

_COMPANY_CACHE = None



def _load_companys_xlsx(path: str):

    global _COMPANY_CACHE

    if _COMPANY_CACHE is not None:

        return _COMPANY_CACHE



    import openpyxl



    wb = openpyxl.load_workbook(path, data_only=True)

    ws = wb[wb.sheetnames[0]]



    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]

    idx = {str(h).strip(): i for i, h in enumerate(headers) if h is not None}



    def get(row, key, default=None):

        j = idx.get(key)

        return row[j] if j is not None and j < len(row) else default



    rows = []

    for r in ws.iter_rows(min_row=2, values_only=True):

        if not r:

            continue



        region_raw = str(get(r, "지역", "") or "").strip()

        if not region_raw:

            continue



        region_rep = classify_region(region_raw)

        inds = set()

        for k in [f"공종코드{i}" for i in range(1, 11)]:

            v = get(r, k, None)

            if v is None:

                continue

            s = str(v).strip()

            if s:

                inds.add(s)



        phones = []

        for k in [f"전화번호{i}" for i in range(1, 6)]:

            v = get(r, k, None)

            if v is None:

                continue

            p = re.sub(r"[^\d]", "", str(v))

            if p:

                phones.append(p)



        rows.append({

            "region_raw": region_raw,

            "region_rep": region_rep,

            "inds": inds,

            "phones": phones,

        })



    _COMPANY_CACHE = rows

    return rows





def _uniq_keep_order(xs: List[str]) -> List[str]:

    seen = set()

    out = []

    for x in xs:

        if x and x not in seen:

            seen.add(x)

            out.append(x)

    return out





def decide_receivers(row: Dict[str, Any]) -> List[str]:

    """

    main_send.py에서 호출하는 수신자 결정 함수.

    - FORCE_RECV 있으면 최우선

    - companys.xlsx에서 (지역 + 공종코드) 매칭하여 전화번호 반환

    """

    # 0) 강제 수신자(점검용)

    force = os.environ.get("FORCE_RECV", "").strip()

    if force:

        return [re.sub(r"[^\d]", "", force)]



    ind = str(row.get("공고업종코드", "")).strip()

    if ind not in VALID_INDS:

        return []



    # 대표지역은 main_send에서 이미 계산된 값이 있으면 그걸 우선

    rep = str(row.get("대표지역", "") or "").strip()

    rep = classify_region(rep) if rep else ""



    # 대표지역 없으면 힌트로 추정

    if not rep or rep == "기타":

        hint = " ".join([

            str(row.get("참가가능지역", "") or ""),

            str(row.get("참가제한지역", "") or ""),

            str(row.get("공동도급지역", "") or ""),

            str(row.get("공고명", "") or ""),

        ]).strip()

        rep = classify_region(hint)



    if not rep:

        return []



    # 엑셀 경로(기본: n_data_test/companys.xlsx)

    xlsx = os.environ.get("RECEIVER_XLSX", "/home/pi/n_data_test/companys.xlsx").strip()

    if not os.path.exists(xlsx):

        return []



    comp_rows = _load_companys_xlsx(xlsx)



    phones = []

    for c in comp_rows:

        # 지역 매칭: 전국은 무조건 매칭, 아니면 대표지역 동일해야 매칭

        if c["region_rep"] != "전국" and c["region_rep"] != rep:

            continue

        # 공종 매칭

        if ind not in c["inds"]:

            continue

        phones.extend(c["phones"])



    return _uniq_keep_order(phones)





def infer_region_when_etc(text: str) -> str:

    try:

        return classify_region(text or "")

    except Exception:

        return "기타"

