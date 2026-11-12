
import os

import time

import requests

import pandas as pd

import datetime



API_URL = "https://apis.data.go.kr/1230000/BidPublicInfoService02/getBidPblancListInfoCnstwk"



def fetch_bid_data(api_key_file, industry_codes, days_offset=1):

    """

    API 키를 파일에서 읽고, 업종 코드별로 데이터를 가져옴.

    """

    with open(api_key_file, "r", encoding="utf-8") as f:

        api_key = f.read().strip()



    if not api_key:

        raise ValueError("API 키가 비어 있습니다. /home/pi/n_data/bid_api_key.txt를 확인하세요.")



    all_rows = []

    now = datetime.datetime.now()

    start_date = (now - datetime.timedelta(days=days_offset)).strftime("%Y%m%d%H%M")

    end_date = now.strftime("%Y%m%d%H%M")



    for code in industry_codes:

        page = 1

        while True:

            params = {

                "serviceKey": api_key,

                "numOfRows": 100,

                "pageNo": page,

                "type": "json",

                "inqryDiv": "1",

                "inqryBgnDt": start_date,

                "inqryEndDt": end_date,

                "indstrytyCd": code,

            }

            res = requests.get(API_URL, params=params, timeout=10)

            data = res.json()

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

            

            if not items:

                break



            print(f"[API] 업종코드 {code}, 페이지 {page}, {len(items)}건 수집")

            all_rows.extend(items)

            page += 1

            time.sleep(0.3)



    return pd.DataFrame(all_rows)

