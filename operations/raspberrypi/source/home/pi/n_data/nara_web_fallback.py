
# -*- coding: utf-8 -*-

"""

나라장터 WEB fallback 보강 모듈



목적:

- Open API / 단건 API에서 누락되는 공고를 보강

- 우선 특정 공고번호를 직접 상세 URL로 접근

- 실패 시 수동 안전 보강값 사용

"""



import time

import re

from selenium import webdriver

from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By





def _log(msg):

    print(msg, flush=True)





def _clean(s):

    return re.sub(r"\s+", " ", str(s or "")).strip()





def make_driver():

    opt = Options()

    opt.add_argument("--headless=new")

    opt.add_argument("--no-sandbox")

    opt.add_argument("REDACTED_PRIVATE_VALUE")

    opt.add_argument("--disable-gpu")

    opt.add_argument("--window-size=1600,1200")



    try:

        return webdriver.Chrome(options=opt)

    except Exception:

        opt.binary_location = "REDACTED_PRIVATE_VALUE"

        return webdriver.Chrome(options=opt)





def manual_known_gh_dongtan2():

    return {

        "bidNtceNo": "R26BK01486034",

        "bidNtceOrd": "000",

        "bidNtceNm": "동탄2 주차상업복합건물 소방설비공사",

        "indstrytyCd": "0038",

        "indstrytyNm": "전문소방시설공사업",

        "prtcptLmtRgnNm": "경기도",

        "prtcptPsblRgnNm": "전국",

        "jntcontrctDutyRgnNm1": "경기도",

        "jntcontrctDutyRgnNm2": "",

        "jntcontrctDutyRgnNm3": "",

        "jntcontrctDutyRgnRt": "49",

        "sucsfbidMthdNm": "적격심사제-지방자치단체 입찰시 낙찰자 결정기준 - 추정가격이 30억원 미만 10억원 이상인 입찰공사(실적제한 아님)",

        "presmptPrce": 1168564817,

        "bdgtAmt": 1289856000,

        "bidBeginDt": "2026-05-07 09:00:00",

        "bidClseDt": "2026-05-11 10:00:00",

        "opengDt": "2026-05-11 11:00:00",

        "ntceInsttNm": "경기주택도시공사",

        "dminsttNm": "경기주택도시공사",

        "bidNtceDt": "2026-04-23 17:25:30",

        "_source": "MANUAL_WEB_FALLBACK",

    }





def crawl_g2b_by_bid_no(bid_no):

    bid_no = str(bid_no).strip()

    driver = make_driver()



    try:

        url = f"https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoDtl.do?bidno={bid_no}&bidseq=00"

        _log(f"[WEB] open {url}")



        driver.get(url)

        time.sleep(4)



        text = _clean(driver.find_element(By.TAG_NAME, "body").text)



        if bid_no in text or "동탄2" in text or "주차상업복합건물" in text:

            _log(f"[WEB][FOUND] {bid_no}")



            # 현재는 상세 화면 파싱보다 안정적인 수동 보강값을 우선 사용

            if bid_no == "R26BK01486034":

                return manual_known_gh_dongtan2()



            return {

                "bidNtceNo": bid_no,

                "bidNtceOrd": "000",

                "bidNtceNm": "",

                "indstrytyCd": "",

                "indstrytyNm": "",

                "presmptPrce": 0,

                "bdgtAmt": 0,

                "_source": "WEB_FALLBACK",

                "_web_text": text[:5000],

            }



        _log(f"[WEB][MISS] {bid_no}")

        return None



    except Exception as e:

        _log(f"[WEB][ERR] {bid_no} {type(e).__name__}: {e}")

        return None



    finally:

        try:

            driver.quit()

        except Exception:

            pass





def enrich_web_fallback(api_rows, target_bid_nos=None):

    if not isinstance(api_rows, list):

        return api_rows, 0



    target_bid_nos = target_bid_nos or []



    existing = {

        str(r.get("bidNtceNo") or r.get("공고번호") or "").strip()

        for r in api_rows

    }



    added = 0



    for bid_no in target_bid_nos:

        bid_no = str(bid_no).strip()



        if not bid_no:

            continue



        if bid_no in existing:

            _log(f"[WEB][SKIP] already exists {bid_no}")

            continue



        _log(f"[WEB] fallback check {bid_no}")



        if bid_no == "R26BK01486034":

            _log(f"[WEB][FORCE] manual fallback {bid_no}")

            row = manual_known_gh_dongtan2()

        else:

            row = crawl_g2b_by_bid_no(bid_no)



        if row:

            api_rows.append(row)

            existing.add(bid_no)

            added += 1

            _log(f"[WEB][ADD] {bid_no} / {row.get('bidNtceNm', '')}")



    _log(f"[WEB] added={added}")

    return api_rows, added

