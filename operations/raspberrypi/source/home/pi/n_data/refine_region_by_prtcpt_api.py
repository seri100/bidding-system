#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import requests

import pandas as pd

from pathlib import Path

from datetime import datetime

import time



SERVICE_KEY = "REDACTED_PRIVATE_VALUE"

API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"



def call_api(bid_no, bid_ord, bgn_dt, end_dt):

    """공고번호 + 차수 기준 참가가능지역 조회"""

    params = {

        "serviceKey": SERVICE_KEY,

        "pageNo": "1",

        "numOfRows": "100",

        "type": "json",

        "inqryDiv": "1",

        "inqryBgnDt": bgn_dt,

        "inqryEndDt": end_dt,

        "bidNtceNo": bid_no,

        "bidNtceOrd": bid_ord,

    }



    try:

        r = requests.get(API_URL, params=params, timeout=5)

        r.raise_for_status()

        data = r.json()

        body = data.get("응답", {}).get("몸", {})

        items = body.get("항목", [])

        return items

    except Exception as e:

        print(f"[WARN] API error: {bid_no}-{bid_ord}: {e}")

        return []



def pick_best_region(region_list):

    """여러 지역 중 가장 상세한 지역 선택"""

    if not region_list:

        return ""

    # 글자수가 가장 긴 지역명 선택 (시/군/구 포함)

    region_list = sorted(region_list, key=lambda x: len(x), reverse=True)

    return region_list[0]



def refine_excel(input_xlsx):

    df = pd.read_excel(input_xlsx, dtype=str)

    print(f"[INFO] 엑셀 로드: {len(df)} rows")



    today = datetime.now().strftime("%Y%m%d")

    bgn_dt = today + "0000"

    end_dt = today + "2359"



    new_regions = {}



    for idx, row in df.iterrows():

        bid_no = str(row.get("공고번호") or "").strip()

        bid_ord = str(row.get("차수") or "").strip()



        if not bid_no or not bid_ord:

            continue



        items = call_api(bid_no, bid_ord, bgn_dt, end_dt)



        regions = [item.get("prtcptPsblRgnNm", "").strip()

                   for item in items if item.get("prtcptPsblRgnNm")]



        best_region = pick_best_region(regions)

        if best_region:

            new_regions[idx] = best_region



        time.sleep(0.15)   # API 과부하 방지



    # 적용

    for idx, region in new_regions.items():

        df.at[idx, "대표지역"] = region



    out_xlsx = Path(input_xlsx).stem + "_대표지역세분화.xlsx"

    df.to_excel(out_xlsx, index=False)

    print(f"[INFO] 저장 완료 → {out_xlsx}")





if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print("사용법: python3 refine_region_by_prtcpt_api.py input.xlsx")

        sys.exit(0)



    refine_excel(sys.argv[1])


