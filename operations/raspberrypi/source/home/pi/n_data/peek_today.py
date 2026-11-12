
# -*- coding: utf-8 -*-

import datetime as dt

import urllib.parse, os, requests



def load_key():

    key = os.environ.get("SERVICE_KEY")

    if not key:

        # .env에서 읽기

        with open("/home/pi/n_data/.env","r",encoding="utf-8") as f:

            for line in f:

                if line.strip().startswith("SERVICE_KEY="):

                    key=line.strip().split("=",1)[1]; break

    if not key:

        raise RuntimeError("SERVICE_KEY 없음")

    return urllib.parse.unquote(urllib.parse.unquote(key))



BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"



def fetch(ind, beg, end, key):

    params = {

        "serviceKey": key, "inqryDiv":"1", "inqryBgnDt":beg, "inqryEndDt":end,

        "type":"json", "indstrytyClCode": ind

    }

    r = requests.get(BASE, params=params, timeout=15)

    r.raise_for_status()

    j = r.json()

    body = j.get("response",{}).get("body",{})

    items = body.get("items",[]) or []

    # items가 dict 한 개로 나올 때 대비

    if isinstance(items, dict):

        items = [items]

    return items



if __name__ == "__main__":

    key = load_key()

    now = dt.datetime.now()

    end = now.strftime("%Y%m%d%H%M")

    beg = (now - dt.timedelta(days=1)).strftime("%Y%m%d%H%M")

    inds = ["0040","0038","0039","6202"]  # 건축/토목/전기통신/기계



    want_regions = ["충청북도","충북","전국"]

    total_hit = 0



    for ind in inds:

        items = fetch(ind, beg, end, key)

        hit = []

        for it in items:

            # 공동도급지역(지역제한) / 참가가능지역 / 공사현장 지역 필드 후보들

            fields = [

                it.get("jntcontrctDutyRgnNm1",""), it.get("jntcontrctDutyRgnNm2",""),

                it.get("jntcontrctDutyRgnNm3",""), it.get("prtcptPsblRgnNm",""),

                it.get("cnstrtsiteRgnNm",""), it.get("dminsttNm",""), it.get("ntceInsttNm","")

            ]

            text = " ".join(x for x in fields if x)

            if any(w in text for w in want_regions):

                hit.append((it.get("bidNtceNo",""), it.get("bidNtceOrd",""), it.get("bidNtceNm",""), text[:120]))



        print(f"[{ind}] fetched={len(items)}  matched(충북/전국)={len(hit)}")

        for bno, ord_, name, region_preview in hit[:5]:

            print("  -", bno, ord_, name, "|", region_preview)

        total_hit += len(hit)



    print("\nTOTAL matched:", total_hit)

