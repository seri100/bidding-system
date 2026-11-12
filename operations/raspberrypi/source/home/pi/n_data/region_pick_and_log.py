
# -*- coding: utf-8 -*-

import os, json, datetime as dt, urllib.parse

import requests

from openpyxl import Workbook



WANT_REGIONS = ["충청북도","충북","전국"]

INDS = ["0040","0038","0039","6202"]  # 건축/토목/전기·정보통신/기계

BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"



def load_key():

    key = os.environ.get("SERVICE_KEY")

    if not key:

        with open("/home/pi/n_data/.env","r",encoding="utf-8") as f:

            for line in f:

                if line.strip().startswith("SERVICE_KEY="):

                    key = line.strip().split("=",1)[1]

                    break

    if not key:

        raise RuntimeError("SERVICE_KEY 없음")

    # 공공데이터포털 특성: 이중 URL 인코딩돼 올 때가 많음 → 두 번 디코딩

    return urllib.parse.unquote(urllib.parse.unquote(key))



def fetch(ind, beg, end, key):

    params = {"serviceKey":key,"inqryDiv":"1","inqryBgnDt":beg,"inqryEndDt":end,"type":"json","indstrytyClCode":ind}

    r = requests.get(BASE, params=params, timeout=20)

    r.raise_for_status()

    j = r.json()

    body = j.get("response",{}).get("body",{})

    items = body.get("items",[]) or []

    if isinstance(items, dict):

        items = [items]

    return items



def region_like(item):

    cand = [

        item.get("jntcontrctDutyRgnNm1",""), item.get("jntcontrctDutyRgnNm2",""),

        item.get("jntcontrctDutyRgnNm3",""),

        item.get("prtcptPsblRgnNm",""),      # 참가가능지역

        item.get("cnstrtsiteRgnNm",""),      # 공사현장

        item.get("dminsttNm",""), item.get("ntceInsttNm","")

    ]

    s = " ".join([c for c in cand if c])

    return any(w in s for w in WANT_REGIONS)



def main(days=1):

    key = load_key()

    now = dt.datetime.now()

    end = now.strftime("%Y%m%d%H%M")

    beg = (now - dt.timedelta(days=days)).strftime("%Y%m%d%H%M")



    all_hits = []

    for ind in INDS:

        items = fetch(ind, beg, end, key)

        hits = [it for it in items if region_like(it)]

        print(f"[{ind}] fetched={len(items)}  matched(충북/전국)={len(hits)}")

        for it in hits[:5]:

            print("  -", it.get("bidNtceNo",""), it.get("bidNtceOrd",""), it.get("bidNtceNm",""))

        # 업종코드 추가해 두면 이후 분석/전송에 편함

        for it in hits:

            it["_ind"] = ind

        all_hits.extend(hits)



    print("\nTOTAL matched:", len(all_hits))

    # 엑셀 저장

    if all_hits:

        wb = Workbook()

        ws = wb.active

        cols = ["_ind","bidNtceNo","bidNtceOrd","bidNtceNm","bidNtceDt","bidClseDt",

                "jntcontrctDutyRgnNm1","jntcontrctDutyRgnNm2","jntcontrctDutyRgnNm3",

                "prtcptPsblRgnNm","cnstrtsiteRgnNm","dminsttNm","ntceInsttNm",

                "bdgtAmt","bidNtceUrl","bidNtceDtlUrl"]

        ws.append(cols)

        for it in all_hits:

            ws.append([it.get(c,"") for c in cols])



        outdir = "REDACTED_PRIVATE_VALUE"

        os.makedirs(outdir, exist_ok=True)

        out = os.path.join(outdir, f"region_probe_{now.strftime('%Y%m%d_%H%M')}.xlsx")

        wb.save(out)

        print("Saved:", out)



if __name__ == "__main__":

    main(days=3)

