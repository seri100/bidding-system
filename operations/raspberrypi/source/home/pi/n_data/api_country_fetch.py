
import os

import time

import requests

import pandas as pd

import datetime





API_URL = "https://apis.data.go.kr/1230000/BidPublicInfoService02/getBidPblancListInfoCnstwk"



def fetch_construction_bids(api_key_file, industry_codes, hours_back=1):

    with open(api_key_file, "r", encoding="utf-8") as f:

        api_key = f.read().strip()

    if not api_key:

        raise ValueError("API 키가 비어 있습니다: /home/pi/n_data/bid_api_key.txt")



    all_items = []

    now = datetime.datetime.now()

    start_dt = (now - datetime.timedelta(hours=hours_back)).strftime("%Y%m%d%H%M")

    end_dt = now.strftime("%Y%m%d%H%M")



    for code in industry_codes:

        page = 1

        while True:

            params = {

                "serviceKey": api_key,

                "numOfRows": 100,

                "pageNo": page,

                "type": "json",

                "inqryDiv": "1",

                "inqryBgnDt": start_dt,

                "inqryEndDt": end_dt,

                "indstrytyCd": code,

            }

            res = requests.get(API_URL, params=params, timeout=10)

            try:

                items = res.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])

            except:

                break

            if not items:

                break



            print(f"[API] code={code}, page={page}, got={len(items)}")

            all_items.extend(items)

            page += 1

            time.sleep(0.2)



    return pd.DataFrame(all_items)

