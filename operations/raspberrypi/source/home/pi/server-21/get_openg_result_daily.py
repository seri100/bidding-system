
from datetime import datetime, timedelta

from pathlib import Path

import requests, pandas as pd



BASE_URL="https://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoCnstwkPPSSrch"

KEY="REDACTED_PRIVATE_VALUE"

IND=["0037","0040","6202"]

OUT=Path("/mnt/vol1/bid/server-21"); OUT.mkdir(parents=True,exist_ok=True)

ROWS=999



def daterange():

    today=datetime.now().date()

    start=today - timedelta(days=60)

    return start.strftime("%Y%m%d")+"0000", today.strftime("%Y%m%d")+"2359"



def fetch(ind, s, e, page):

    p={

        "serviceKey":KEY,"pageNo":page,"numOfRows":ROWS,

        "inqryDiv":2, "indstrytyCd":ind, "type":"json",

        "inqryBgnDt":s,"inqryEndDt":e

    }

    r=requests.get(BASE_URL,params=p,timeout=30).json()

    body=r.get("response",{}).get("body",{})

    items=body.get("items")

    if not items: return []

    if isinstance(items,list): return items

    item=items.get("item")

    if isinstance(item,list): return item

    if isinstance(item,dict): return [item]

    return []



def main():

    s,e=daterange()

    print("[INFO] 기간",s,"~",e)

    rows=[]

    for ind in IND:

        p=1

        while True:

            print("[FETCH]",ind,"page",p)

            d=fetch(ind,s,e,p)

            if not d: break

            for it in d: it["_ind"]=ind

            rows+=d

            if len(d)<ROWS: break

            p+=1

    if not rows:

        print("[NONE] 기간 내 데이터 없음")

        return

    df=pd.json_normalize(rows)

    df.to_excel(OUT/"TEST_최근60일.xlsx",index=False)

    print("[SAVE]",OUT/"TEST_최근60일.xlsx")



if __name__=="__main__":

    main()

