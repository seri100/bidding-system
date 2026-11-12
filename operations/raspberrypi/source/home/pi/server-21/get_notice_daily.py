
# -*- coding: utf-8 -*-

"""

조달청 공사 개찰결과 일일 요약 (지역 = 참가가능지역 기반)



사용 API

- RESULT : as/ScsbidInfoService/getOpengResultListInfoCnstwk

- PRICE  : as/ScsbidInfoService/getOpengResultListInfoCnstwkPreparPcDetail

- REGION : ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn

            (serviceKey, inqryDiv=2, bidNtceNo, bidNtceOrd)



기능 요약

- 날짜 옵션:

    --days-ago N        : 오늘 기준 N일 전 하루

    --date YYYY-MM-DD   : 해당 날짜 하루

    --from-dt / --to-dt : 조회 기간 직접 지정 (YYYYMMDDHHMM)

    (옵션 없으면 어제 하루)

- RESULT + PRICE를 공고번호+차수로 병합

- 각 공고에 대해 참가가능지역 API를 개별 호출해 prtcptPsblRgnNm 사용

    → '참가가능지역원문' 컬럼 (API 값 그대로, 예: '충청남도 천안시')

    → '지역' 컬럼도 동일하게 사용

- 참가가능지역이 없으면 예전 RESULT 기반 로직으로 '지역' 추론

- 엑셀 저장 위치: /mnt/vol1/result/nara

"""



import sys

import argparse

from datetime import datetime, timedelta

from pathlib import Path

from typing import Dict, Any, List, Tuple



import requests

import pandas as pd



# --------------------------

# API URL

# --------------------------

URL_RESULT = "http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoCnstwk"

URL_PRICE  = "http://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoCnstwkPreparPcDetail"

URL_REGION = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"



# --------------------------

# 환경 설정

# --------------------------

KEY_PATH = "/home/pi/n_data/bid_api_key.txt"

OUTDIR = Path("/mnt/vol1/result/nara")



REGIONS = [

    "서울특별시","부산광역시","대구광역시","인천광역시","광주광역시",

    "대전광역시","울산광역시","세종특별자치시","경기도","강원도",

    "충청북도","충청남도","전라북도","전라남도",

    "경상북도","경상남도","제주특별자치도",

    "강원특별자치도","전북특별자치도",

]





# --------------------------

# 공통 유틸

# --------------------------

def load_service_key(path: str = KEY_PATH) -> str:

    p = Path(path)

    if not p.exists():

        print(f"[ERROR] API 키 파일이 없습니다: {path}", file=sys.stderr)

        sys.exit(1)

    key = p.read_text(encoding="utf-8").strip()

    if not key:

        print(f"[ERROR] API 키가 비어 있습니다: {path}", file=sys.stderr)

        sys.exit(1)

    return key





# --------------------------

# Scsbid 개찰결과/예정가격 수집

# --------------------------

def fetch_paged_scsbid(url: str, key: str, bgn: str, end_: str, label: str) -> List[Dict[str, Any]]:

    page = 1

    num_rows = 999

    seen = set()

    results: List[Dict[str, Any]] = []



    while True:

        print(f"[FETCH] {label} page={page}")

        params = {

            "serviceKey": key,

            "inqryDiv": 1,

            "type": "json",

            "numOfRows": num_rows,

            "pageNo": page,

            "inqryBgnDt": bgn,

            "inqryEndDt": end_,

        }



        try:

            r = requests.get(url, params=params, timeout=20)

            if not r.ok or not r.text.strip():

                print(f"[WARN] {label} 응답없음 (HTTP {r.status_code})")

                break

            j = r.json()

        except Exception as e:

            print(f"[ERROR] {label} JSON 실패: {e}")

            break



        body = j.get("response", {}).get("body", {})

        items = body.get("items", [])

        if not items:

            break

        if isinstance(items, dict):

            items = [items]



        for it in items:

            keyt = (it.get("bidNtceNo"), it.get("bidNtceOrd") or "000")

            if keyt in seen:

                continue

            seen.add(keyt)

            it["key"] = keyt

            results.append(it)



        total = body.get("totalCount", 0)

        try:

            total = int(total)

        except Exception:

            total = 0



        if total == 0 or page * num_rows >= total:

            break

        page += 1



    print(f"[INFO] {label} 수집 건수: {len(results)}")

    return results





# --------------------------

# 참가가능지역 API (공고별 호출)

# --------------------------

def fetch_region_for_notice(api_key: str, bid_no: str, bid_ord: str) -> str:

    """

    getBidPblancListInfoPrtcptPsblRgn

    - serviceKey

    - inqryDiv=2

    - bidNtceNo, bidNtceOrd 로 개별 조회

    - prtcptPsblRgnNm 반환 (없으면 빈 문자열)

    """

    if not bid_no:

        return ""



    params = {

        "serviceKey": api_key,

        "numOfRows": 10,

        "pageNo": 1,

        "type": "json",

        "inqryDiv": "2",

        "bidNtceNo": bid_no,

        "bidNtceOrd": bid_ord or "000",

    }



    try:

        for _ in range(2):  # 최대 2번 시도

            r = requests.get(URL_REGION, params=params, timeout=20)

            if not r.ok or not r.text.strip():

                continue

            try:

                j = r.json()

            except Exception:

                continue



            header = j.get("response", {}).get("header", {})

            if header.get("resultCode") != "00":

                continue



            body = j.get("response", {}).get("body", {})

            items = body.get("items", [])

            if not items:

                return ""



            if isinstance(items, dict):

                items = [items]

            first = items[0]

            return first.get("prtcptPsblRgnNm", "") or ""

    except Exception:

        return ""



    return ""





def build_region_map(api_key: str, result_items: List[Dict[str, Any]]) -> Dict[Tuple[str, str], str]:

    """

    RESULT 목록을 돌면서

    - 각 (bidNtceNo, bidNtceOrd)에 대해 참가가능지역 API 호출

    - key: (bidNtceNo, bidNtceOrd) → value: prtcptPsblRgnNm

    """

    region_map: Dict[Tuple[str, str], str] = {}

    for idx, r in enumerate(result_items, start=1):

        bid_no = r.get("bidNtceNo")

        bid_ord = r.get("bidNtceOrd") or "000"

        key = (bid_no, bid_ord)



        print(f"[REGION] {idx}/{len(result_items)} {bid_no}/{bid_ord} 참가가능지역 조회")

        prtcpt = fetch_region_for_notice(api_key, bid_no, bid_ord)

        region_map[key] = prtcpt

    return region_map





# --------------------------

# 참가가능지역 문자열 그대로 사용

# --------------------------

def normalize_region_from_prtcpt(psbl_raw: str) -> str:

    """

    참가가능지역 문자열(prtcptPsblRgnNm)을 가공 없이 그대로 반환.



    예)

      - '대전광역시 전지역'        -> '대전광역시 전지역'

      - '충청남도 천안시'         -> '충청남도 천안시'

    """

    if not psbl_raw:

        return ""

    return str(psbl_raw).strip()





# --------------------------

# (fallback) RESULT 기반 지역 추론

# --------------------------

def extract_region_from_result_row(r: Dict[str, Any]) -> str:

    candidates = [

        r.get("prtcptLmtRgnNm"),

        r.get("prtcptRgnNm"),

        r.get("bidNtceNm"),

        r.get("ntceInsttNm"),

        r.get("dminsttNm"),

    ]



    for text in candidates:

        if not text:

            continue

        for rg in REGIONS:

            if rg in text:

                return rg



    # 축약형

    short_map = [

        ("서울", "서울특별시"),

        ("부산", "부산광역시"),

        ("대구", "대구광역시"),

        ("인천", "인천광역시"),

        ("광주", "광주광역시"),

        ("대전", "대전광역시"),

        ("울산", "울산광역시"),

        ("세종", "세종특별자치시"),

        ("경기", "경기도"),

        ("충북", "충청북도"),

        ("충남", "충청남도"),

        ("전북", "전북특별자치도"),

        ("전남", "전라남도"),

        ("경북", "경상북도"),

        ("경남", "경상남도"),

        ("제주", "제주특별자치도"),

        ("강원", "강원특별자치도"),

    ]

    for text in candidates:

        if not text:

            continue

        for key, rg in short_map:

            if key in text:

                return rg



    return "기타"





# --------------------------

# 병합 (RESULT + PRICE + 참가가능지역)

# --------------------------

def merge_data(

    result_items: List[Dict[str, Any]],

    price_items: List[Dict[str, Any]],

    region_map: Dict[Tuple[str, str], str],

) -> List[Dict[str, Any]]:

    price_map = {p["key"]: p for p in price_items if "key" in p}

    merged: List[Dict[str, Any]] = []



    for r in result_items:

        k = r.get("key")

        p = price_map.get(k, {})



        # 예정/기초금액 없으면 스킵

        try:

            pln = float(p.get("plnprc", 0) or 0)

            bss = float(p.get("bssamt", 0) or 0)

            if pln == 0 or bss == 0:

                continue

            rate = round(pln / bss * 100, 3)

        except Exception:

            continue



        op = r.get("opengCorpInfo") or ""

        parts = op.split("^") if op else []

        bidder = parts[0] if parts else None

        bid_rate = parts[-1] if parts else None



        bid_no = r.get("bidNtceNo")

        bid_ord = r.get("bidNtceOrd") or "000"

        key_tuple = (bid_no, bid_ord)



        prtcpt_raw = region_map.get(key_tuple, "") or ""

        if prtcpt_raw:

            # 참가가능지역이 있으면 그대로 사용

            region = normalize_region_from_prtcpt(prtcpt_raw)

        else:

            # 없을 때만 RESULT 기반 추론

            region = extract_region_from_result_row(r)



        merged.append({

            "공고번호": bid_no,

            "공고차수": bid_ord,

            "공고명": r.get("bidNtceNm"),

            "실개찰일시": r.get("inptDt"),

            "참여업체수": r.get("prtcptCnum"),

            "낙찰자명": bidder,

            "투찰률(raw)": bid_rate,

            "예정가격": pln,

            "기초금액": bss,

            "결정율(%)": rate,

            "참가가능지역원문": prtcpt_raw,

            "지역": region,

        })



    return merged





# --------------------------

# 저장

# --------------------------

def save_report(data: List[Dict[str, Any]], from_dt: str) -> Path:

    OUTDIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")

    ymd = from_dt[:8]

    fp = OUTDIR / f"co_일일_입찰요약_{ymd}_{now}.xlsx"



    df = pd.DataFrame(data)

    if not df.empty:

        if "실개찰일시" in df.columns:

            df["실개찰일시"] = pd.to_datetime(df["실개찰일시"], errors="coerce")

            df = df.sort_values("실개찰일시")

        df.to_excel(fp, index=False)



    print(f"[INFO] ✅ 엑셀 저장 완료: {fp}")

    return fp





# --------------------------

# 기간 계산

# --------------------------

def calc_period(args) -> Tuple[str, str]:

    if args.from_dt and args.to_dt:

        return args.from_dt, args.to_dt



    if args.date:

        base = datetime.strptime(args.date, "%Y-%m-%d")

    elif args.days_ago is not None:

        base = datetime.now() - timedelta(days=args.days_ago)

    else:

        base = datetime.now() - timedelta(days=1)



    ymd = base.strftime("%Y%m%d")

    return ymd + "0000", ymd + "2359"





# --------------------------

# MAIN

# --------------------------

def main():

    parser = argparse.ArgumentParser(description="조달청 개찰결과 일일 요약 (참가가능지역 기반 지역 구분)")

    parser.add_argument("--date", help="YYYY-MM-DD")

    parser.add_argument("--days-ago", type=int, dest="days_ago")

    parser.add_argument("--from-dt", dest="from_dt")

    parser.add_argument("--to-dt", dest="to_dt")

    args = parser.parse_args()



    from_dt, to_dt = calc_period(args)

    print(f"[INFO] 조회기간: {from_dt} ~ {to_dt}")



    key = load_service_key()



    # 1) RESULT / PRICE

    result_items = fetch_paged_scsbid(URL_RESULT, key, from_dt, to_dt, "RESULT")

    price_items  = fetch_paged_scsbid(URL_PRICE , key, from_dt, to_dt, "PRICE")



    if not result_items:

        print("[INFO] 개찰결과가 비어 있어 종료합니다.")

        return



    # 2) 참가가능지역 정보 (공고별 조회)

    region_map = build_region_map(key, result_items)



    # 3) 병합

    merged = merge_data(result_items, price_items, region_map)

    print(f"[INFO] 병합 후 건수: {len(merged)}")



    if not merged:

        print("[INFO] 병합 결과 데이터가 없습니다.")

        return



    save_report(merged, from_dt)





if __name__ == "__main__":

    main()

