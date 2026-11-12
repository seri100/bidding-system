
# -*- coding: utf-8 -*-

import os

import sys

import datetime

from typing import List, Dict, Any



import requests

import openpyxl





# -----------------------------

# 경로/설정

# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))



# 로그 폴더: 기존과 동일하게 서버3 밑에 생성

LOG_DIR = "/home/pi/seri_Alarm_Server3"

os.makedirs(LOG_DIR, exist_ok=True)



# 결과 엑셀 저장 위치

#   - Windows: Z:\VOL1\bid\gon_auto

#   - Raspberry Pi 마운트 경로: /mnt/vol1/gon_auto

OUTDIR = "/mnt/vol1/gon_auto"

os.makedirs(OUTDIR, exist_ok=True)



# API 키 후보 경로

API_KEY_CANDIDATES = [

    os.path.join(BASE_DIR, "bid_api_key.txt"),

    "/home/pi/n_data/bid_api_key.txt",

]



# 기본 설정

INDSTRY_CODES = ["0040", "0038", "0039", "6202"]

MIN_BUDGET = 0  # 필요하면 나중에 조정





# -----------------------------

# 로거

# -----------------------------

_now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

_LOG_FILE = os.path.join(LOG_DIR, f"log_{_now_str}.txt")

_log_fp = open(_LOG_FILE, "w", encoding="utf-8")





def log(msg: str) -> None:

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{ts}] {msg}"

    # 터미널 + 로그 파일 둘 다 남김

    print(line)

    _log_fp.write(line + "\n")

    _log_fp.flush()





# -----------------------------

# 설정 로딩

# -----------------------------

def load_api_key() -> str:

    for path in API_KEY_CANDIDATES:

        if os.path.exists(path):

            with open(path, "r", encoding="utf-8") as f:

                key = f.read().strip()

            if key:

                log(f"[CONF] API 키 로드: {path}")

                return key

    raise FileNotFoundError(

        f"bid_api_key.txt 를 찾을 수 없습니다. 검색 경로: {API_KEY_CANDIDATES}"

    )





def load_region_keywords_from_excel(filepath: str) -> List[str]:

    path = filepath

    if not os.path.isabs(path):

        path = os.path.join(BASE_DIR, filepath)

    if not os.path.exists(path):

        raise FileNotFoundError(f"지역 키워드 파일이 없습니다: {path}")



    wb = openpyxl.load_workbook(path, data_only=True)

    ws = wb.active

    raw = ws["G3"].value or ""

    regions = [s.strip() for s in str(raw).split(",") if s and s.strip()]

    log(f"[CONF] 지역 키워드 {len(regions)}개 로드: {regions}")

    return regions





# (필요시 확장용) SMS 대상 로딩 - 지금은 안 씀

def load_sms_targets(filepath: str):

    path = filepath

    if not os.path.isabs(path):

        path = os.path.join(BASE_DIR, filepath)

    if not os.path.exists(path):

        log(f"[WARN] SMS 대상 파일 없음(무시): {path}")

        return []



    wb = openpyxl.load_workbook(path, data_only=True)

    ws = wb.active

    targets = []

    for row in ws.iter_rows(min_row=2, values_only=True):

        region, company, phone = row[:3]

        if region and phone:

            targets.append(

                {

                    "지역": str(region).strip(),

                    "업체명": str(company).strip() if company else "",

                    "전화번호": str(phone).strip(),

                }

            )

    log(f"[CONF] SMS 대상 {len(targets)}건 로드")

    return targets





# -----------------------------

# API 호출

# -----------------------------

URI_BID_11 = (

    "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"

)





def req_url(uri: str, params: Dict[str, Any], api_key: str, timeout: int = 30):

    full_url = uri + "?ServiceKey=" + api_key

    for retry in range(5):

        try:

            resp = requests.get(full_url, params=params, timeout=timeout)

            resp.raise_for_status()

            result = resp.json()

            header = result.get("response", {}).get("header", {})

            code = header.get("resultCode")

            if code == "00":

                return result

            else:

                log(f"[HTTP] 결과 코드 비정상({code}), 재시도 {retry+1}/5")

        except Exception as e:

            log(f"[ERR] API 요청 실패 (시도 {retry+1}/5): {e}")

    log("[ERR] API 요청 반복 실패, None 반환")

    return None





# -----------------------------

# 입찰 수집 & 지역 분류

# -----------------------------

def collect_bids(

    api_key: str,

    indstry_codes: List[str],

    min_budget: int,

    search_hours: int = 24,

) -> List[Dict[str, Any]]:

    now = datetime.datetime.now()

    endtime = now.strftime("%Y%m%d%H%M")

    begintime = (now - datetime.timedelta(hours=search_hours)).strftime("%Y%m%d%H%M")

    log(f"[FETCH] 기간: {begintime} ~ {endtime}")



    all_bids: List[Dict[str, Any]] = []



    for code in indstry_codes:

        params = {

            "numOfRows": 100,

            "pageNo": 1,

            "type": "json",

            "inqryDiv": "1",

            "inqryBgnDt": begintime,

            "inqryEndDt": endtime,

            "indstrytyCd": code,

        }

        log(f"[HTTP] 요청 ind={code}")

        result = req_url(URI_BID_11, params, api_key)

        if not result:

            log(f"[WARN] ind={code} 응답 없음, skip")

            continue



        body = result.get("response", {}).get("body", {})

        items = body.get("items", [])

        log(f"[HTTP] ind={code} 건수={len(items)}")



        for item in items:

            # 필터: 테스트/취소/국방

            if str(item.get("bidNtceNo", "")).startswith("T"):

                continue

            if "취소" in str(item.get("ntceKindNm", "")):

                continue

            if "국방" in str(item.get("opengPlce", "")):

                continue



            bdgt_amt = 0

            try:

                bdgt_amt = int(item.get("bdgtAmt") or 0)

            except Exception:

                bdgt_amt = 0



            if bdgt_amt < min_budget:

                continue



            bid = {

                "공고명": item.get("bidNtceNm", ""),

                "입찰공고일시": item.get("bidNtceDt", ""),

                "입찰시작일시": item.get("bidBeginDt", ""),

                "입찰마감일시": item.get("bidClseDt", ""),

                "공동도급지역1": item.get("jntcontrctDutyRgnNm1", ""),

                "공동도급지역2": item.get("jntcontrctDutyRgnNm2", ""),

                "공동도급지역3": item.get("jntcontrctDutyRgnNm3", ""),

                "공동도급비율": item.get("rgnDutyJntcontrctRt", ""),

                "추정금액": bdgt_amt,

                "공고번호": item.get("bidNtceNo", ""),

                "차수": item.get("bidNtceOrd", ""),

                "공종코드": code,

                "공고URL": item.get("bidNtceUrl", ""),

            }

            all_bids.append(bid)



    log(f"[FETCH] 전체 수집 건수: {len(all_bids)}")

    return all_bids





def split_bids_by_region(

    bids: List[Dict[str, Any]], region_keys: List[str]

) -> Dict[str, List[Dict[str, Any]]]:

    result_map: Dict[str, List[Dict[str, Any]]] = {r: [] for r in region_keys}



    for bid in bids:

        concat = " ".join(

            [

                str(bid.get("공고명", "")),

                str(bid.get("공동도급지역1", "")),

                str(bid.get("공동도급지역2", "")),

                str(bid.get("공동도급지역3", "")),

            ]

        )



        for r in region_keys:

            if r and r in concat:

                result_map[r].append(bid)



    return result_map





# -----------------------------

# 엑셀 저장

# -----------------------------

def save_to_excel_by_region(

    region_map: Dict[str, List[Dict[str, Any]]], outdir: str

) -> str:

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"입찰공고_지역분류_{now_str}.xlsx"

    out_path = os.path.join(outdir, filename)



    wb = openpyxl.Workbook()

    # 기본 시트는 'ALL' 로 사용

    ws_all = wb.active

    ws_all.title = "ALL"



    headers = [

        "지역키워드",

        "공고번호",

        "차수",

        "공종코드",

        "공고명",

        "입찰공고일시",

        "입찰시작일시",

        "입찰마감일시",

        "공동도급지역1",

        "공동도급지역2",

        "공동도급지역3",

        "공동도급비율",

        "추정금액",

        "공고URL",

    ]

    ws_all.append(headers)



    # ALL 시트 + 지역별 시트 생성

    for region, bids in region_map.items():

        if not bids:

            continue

        ws_region = wb.create_sheet(title=region[:31])  # 엑셀 시트 이름 31자 제한

        ws_region.append(headers)



        for bid in bids:

            row = [

                region,

                bid.get("공고번호", ""),

                bid.get("차수", ""),

                bid.get("공종코드", ""),

                bid.get("공고명", ""),

                bid.get("입찰공고일시", ""),

                bid.get("입찰시작일시", ""),

                bid.get("입찰마감일시", ""),

                bid.get("공동도급지역1", ""),

                bid.get("공동도급지역2", ""),

                bid.get("공동도급지역3", ""),

                bid.get("공동도급비율", ""),

                bid.get("추정금액", ""),

                bid.get("공고URL", ""),

            ]

            ws_all.append(row)

            ws_region.append(row)



    wb.save(out_path)

    log(f"[SAVE] 엑셀 저장: {out_path}")

    return out_path





# -----------------------------

# main

# -----------------------------

def main():

    log("[BOOT] gd-1 (2).py 시작")



    try:

        api_key = load_api_key()

        region_keys = load_region_keywords_from_excel("settings.xlsx")

        _ = load_sms_targets("companys.xlsx")  # 나중 확장용, 현재는 사용 안 함



        bids = collect_bids(api_key, INDSTRY_CODES, MIN_BUDGET, search_hours=24)



        if not bids:

            log("[INFO] 수집된 공고가 없습니다. 종료.")

            return 0



        region_map = split_bids_by_region(bids, region_keys)

        save_to_excel_by_region(region_map, OUTDIR)



        log("[DONE] gd-1 (2).py 정상 종료")

        return 0

    except Exception as e:

        log(f"[FATAL] 오류 발생: {e}")

        return 1

    finally:

        try:

            _log_fp.close()

        except Exception:

            pass





if __name__ == "__main__":

    sys.exit(main())

