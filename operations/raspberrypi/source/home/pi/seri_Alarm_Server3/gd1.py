# -*- coding: utf-8 -*-

import os
import sys
import datetime
import requests
import openpyxl
# -----------------------------------------
# 로그 설정
# -----------------------------------------
LOG_DIR = "/home/pi/seri_Alarm_Server3"
os.makedirs(LOG_DIR, exist_ok=True)
now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(LOG_DIR, f"log_{now_str}.txt")
sys.stdout = open(log_file, "w", encoding="utf-8")
sys.stderr = sys.stdout
# -----------------------------------------
# 설정 로드 함수
# -----------------------------------------

def load_api_key(filepath='bid_api_key.txt'):

    with open(filepath, 'r', encoding='utf-8') as f:

        return f.read().strip()

def load_region_keywords(filepath='settings.xlsx'):

    wb = openpyxl.load_workbook(filepath, data_only=True)

    ws = wb.active

    raw = ws["G3"].value or ""

    return [s.strip() for s in raw.split(',') if s.strip()]

# -----------------------------------------
# API 요청 함수
# -----------------------------------------

def request_api(uri, params, api_key, timeout=30):

    url = uri + "?ServiceKey=" + api_key

    try:

        for _ in range(5):

            resp = requests.get(url, params=params, timeout=timeout)

            data = resp.json()

            if data["response"]["header"]["resultCode"] == "00":

                return data

        return None

    except Exception as e:

        print("[ERR] API 요청 실패:", e)

        return None

# -----------------------------------------
# 입찰공고 수집
# -----------------------------------------

def collect_bids(api_key, codes, min_budget, region_keys):

    now = datetime.datetime.now()

    endtime = now.strftime("%Y%m%d%H%M")

    begintime = (now - datetime.timedelta(hours=24)).strftime("%Y%m%d%H%M")

    URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"

    result_map = {r: [] for r in region_keys}

    for code in codes:

        params = {

            "numOfRows": 100,

            "pageNo": 1,

            "type": "json",

            "inqryDiv": "1",

            "inqryBgnDt": begintime,

            "inqryEndDt": endtime,

            "indstrytyCd": code

        }

        data = request_api(URL, params, api_key)

        if not data:

            continue

        items = data["response"]["body"].get("items", [])

        for it in items:

            if it.get("bidNtceNo", "").startswith("T"):

                continue

            if "취소" in it.get("ntceKindNm", ""):

                continue

            if "국방" in it.get("opengPlce", ""):

                continue



            bdgt = int(it.get("bdgtAmt") or 0)

            if bdgt < min_budget:

                continue



            bid = {

                "공고명": it.get("bidNtceNm", ""),

                "입찰공고일시": it.get("bidNtceDt", ""),

                "입찰시작일시": it.get("bidBeginDt", ""),

                "입찰마감일시": it.get("bidClseDt", ""),

                "공동도급지역1": it.get("jntcontrctDutyRgnNm1", ""),

                "공동도급지역2": it.get("jntcontrctDutyRgnNm2", ""),

                "공동도급지역3": it.get("jntcontrctDutyRgnNm3", ""),

                "공동도급비율": it.get("rgnDutyJntcontrctRt", ""),

                "추정금액": bdgt,

                "공고번호": it.get("bidNtceNo", ""),

                "차수": it.get("bidNtceOrd", ""),

                "공종코드": code,

                "공고URL": it.get("bidNtceUrl", "")

            }



            for r in region_keys:
                if (
                    r in bid["공고명"]
                    or r in bid["공동도급지역1"]
                    or r in bid["공동도급지역2"]
                    or r in bid["공동도급지역3"]
                ):
                    result_map[r].append(bid)

    return result_map

# -----------------------------------------
# 엑셀 저장
# -----------------------------------------

def save_excel(region_bids):

    OUTDIR = "/mnt/vol1/gon_auto"

    os.makedirs(OUTDIR, exist_ok=True)

    filename = f"입찰공고_지역분류_{now_str}.xlsx"

    save_path = os.path.join(OUTDIR, filename)

    wb = openpyxl.Workbook()

    wb.remove(wb.active)

    headers = [

        "공고명", "입찰공고일시", "입찰시작일시", "입찰마감일시",

        "공동도급지역1", "공동도급지역2", "공동도급지역3",

        "공동도급비율", "추정금액", "공고번호", "차수", "공종코드", "공고URL"

    ]

    for region, rows in region_bids.items():

        ws = wb.create_sheet(region)

        ws.append(headers)

        for r in rows:

            ws.append([

                r["공고명"], r["입찰공고일시"], r["입찰시작일시"], r["입찰마감일시"],

                r["공동도급지역1"], r["공동도급지역2"], r["공동도급지역3"],

                r["공동도급비율"], r["추정금액"], r["공고번호"], r["차수"],

                r["공종코드"], r["공고URL"]

            ])

    wb.save(save_path)

    print("=== 저장 완료 ===")

    print(save_path)

# -----------------------------------------
# 메인 실행부
# -----------------------------------------

if __name__ == "__main__":

    api_key = load_api_key("bid_api_key.txt")

    regions = load_region_keywords("settings.xlsx")

    codes = ["0038", "0039", "0040", "6202"]

    collected = collect_bids(api_key, codes, 0, regions)

    save_excel(collected)

    print("=== 모든 작업 완료 ===")
