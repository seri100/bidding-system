
#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

g2b_selector_probe.py - G2B 팝업 자동 닫기 + (강제우회) 입찰공고목록 진입

- Raspberry Pi용 (다운로드 폴더: /mnt/vol1/bid/n_data)

- 선택적 인자: --ind 업종코드(0040 전기, 0039 소방), --regions "경상북도,인천광역시",

               --due_from YYYY-MM-DD, --due_to YYYY-MM-DD

"""



import os, sys, time, argparse

from urllib.parse import urljoin, urlparse

from typing import Optional, Tuple, Iterable, List



from selenium import webdriver

from selenium.webdriver import ChromeOptions

from selenium.webdriver.common.by import By

from selenium.common.exceptions import TimeoutException, WebDriverException, ElementClickInterceptedException, ElementNotInteractableException

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC



DEFAULT_URL = "https://www.g2b.go.kr/"

DEFAULT_WINSIZE = "1920,1200"

DEFAULT_DOWNLOAD_DIR = "/mnt/vol1/bid/n_data"



FALLBACK_BIDLIST_URLS = [

    "https://www.g2b.go.kr:8081/ep/invitation/publish/bidInfoList.do",

    "https://www.g2b.go.kr/ep/invitation/publish/bidInfoList.do",

    "https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoList.do",

]



def parse_winsize(s: Optional[str]) -> Tuple[int, int]:

    try:

        w, h = (s or DEFAULT_WINSIZE).split(",")

        return (int(w.strip()), int(h.strip()))

    except Exception:

        return (1280, 900)



def ensure_dir(path: str) -> str:

    os.makedirs(path, exist_ok=True)

    return os.path.abspath(path)



def build_driver(headless: bool, winsize: str, download_dir: str) -> webdriver.Chrome:

    w,h = parse_winsize(winsize)

    opts = ChromeOptions()

    if headless:

        opts.add_argument("--headless=new")

    opts.add_argument(f"--window-size={w},{h}")

    opts.add_argument("--disable-gpu")

    opts.add_argument("--no-sandbox")

    opts.add_argument("REDACTED_PRIVATE_VALUE")

    opts.add_argument("--remote-allow-origins=*")

    # 다운로드 폴더

    prefs = {

        "download.default_directory": download_dir,

        "download.prompt_for_download": False,

        "download.directory_upgrade": True,

        "safebrowsing.enabled": True,

    }

    opts.add_experimental_option("prefs", prefs)

    drv = webdriver.Chrome(options=opts)

    drv.implicitly_wait(0.5)

    print(f"[DRV] Chrome 시작 (headless={headless})")

    return drv



def visible(el) -> bool:

    try:

        return el.is_displayed() and el.size.get("width",0)>0 and el.size.get("height",0)>0

    except Exception:

        return False



def safe_click(driver, el) -> bool:

    try:

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)

        el.click()

        return True

    except (ElementClickInterceptedException, ElementNotInteractableException):

        try:

            driver.execute_script("arguments[0].click();", el)

            return True

        except Exception:

            return False

    except Exception:

        return False



def find_close_candidates(driver):

    sels = [

        "button.close","a.close",".close",".popupClose",".btn-close",".btnClose",

        "[aria-label*='닫기']","[aria-label*='close' i]",

        "button[title*='닫기']","a[title*='닫기']",

        ".layer .btn_close",".layer .btn-close",

    ]

    xps = [

        "//*[self::button or self::a or self::span or self::div][contains(normalize-space(.),'닫기')]",

        "//*[self::button or self::a][contains(translate(normalize-space(.),'CLOSE','close'),'close')]",

        "//*[contains(normalize-space(.),'오늘 하루')]",

        "//*[contains(normalize-space(.),'하루동안 보지 않기')]",

        "//*[contains(normalize-space(.),'오늘하루안보기')]",

        "//*[contains(normalize-space(.),'오늘 더 이상 보지 않기')]",

    ]

    seen=set()

    for sel in sels:

        try:

            for el in driver.find_elements(By.CSS_SELECTOR, sel):

                if el.id not in seen and visible(el):

                    seen.add(el.id); yield el

        except Exception: pass

    for xp in xps:

        try:

            for el in driver.find_elements(By.XPATH, xp):

                if el.id not in seen and visible(el):

                    seen.add(el.id); yield el

        except Exception: pass



def close_all_popups(driver) -> int:

    cnt=0

    time.sleep(0.6)

    for el in find_close_candidates(driver):

        if safe_click(driver, el):

            label = (el.get_attribute("outerText") or el.get_attribute("aria-label") or el.get_attribute("title") or "").strip().replace("\n"," ")[:40]

            print(f"[POPUP] 레이어 닫힘: {label!r}")

            cnt+=1

            time.sleep(0.15)

    if cnt: print(f"[POPUP] 총 {cnt}개 팝업 정리")

    else: print("[POPUP] 닫을 팝업 없음")

    return cnt



def _wait_url_or_title(driver, url_sub=None, title_has=None, timeout=10):

    try:

        if url_sub: WebDriverWait(driver, timeout).until(EC.url_contains(url_sub))

        if title_has: WebDriverWait(driver, timeout).until(EC.title_contains(title_has))

        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        return True

    except Exception:

        return False



def _find_and_get_href(driver, locators, desc=""):

    for kind, sel in locators:

        try:

            el = WebDriverWait(driver, 6).until(

                EC.presence_of_element_located((By.CSS_SELECTOR, sel)) if kind=="css"

                else EC.presence_of_element_located((By.XPATH, sel))

            )

            href = (el.get_attribute("href") or "").strip()

            if href:

                print(f"[NAV] href 추출: {desc} -> {href}")

                return href, el

            onclick = (el.get_attribute("onclick") or "").strip()

            if onclick:

                print(f"[NAV] onclick 감지: {desc}")

                return None, el

        except Exception:

            continue

    return None, None



def _click_any(driver, sels, desc="", retries=2, timeout=8):

    last=None

    for _ in range(retries):

        for kind, sel in sels:

            try:

                el = WebDriverWait(driver, timeout).until(

                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel)) if kind=="css"

                    else EC.element_to_be_clickable((By.XPATH, sel))

                )

                if safe_click(driver, el):

                    if desc: print(f"[NAV] 클릭: {desc} ({kind}={sel})")

                    return True

            except Exception as e:

                last=e

        time.sleep(0.25)

    if desc: print(f"[WARN] 클릭 실패: {desc} ({last})")

    return False



def go_to_bid_list(driver):

    # 상단 '입찰' 클릭(메뉴 활성화)

    _click_any(driver,

        [("xpath","//a[contains(.,'입찰') and not(contains(.,'결과'))]"),

         ("xpath","//button[contains(.,'입찰')]"),

         ("css","a[href*='bid'], a[onclick*='bid']")],

        desc="상단메뉴: 입찰")



    # '입찰공고목록' 링크 확보

    href, el = _find_and_get_href(driver,

        [("xpath","//a[contains(.,'입찰공고목록')]"),

         ("xpath","//a[contains(.,'입찰공고') and contains(.,'목록')]"),

         ("css","a[href*='bidInfo'], a[href*='invitation'], a[href*='publish']")],

        desc="입찰공고목록")



    navigated=False

    if href:

        if href.lower().startswith("javascript:"):

            # JS 링크면 우선 클릭 시도

            try:

                if el: driver.execute_script("arguments[0].click();", el); time.sleep(0.6)

                navigated = _wait_url_or_title(driver, url_sub="invitation", title_has="입찰")

            except Exception:

                pass

            # 실패 시 강제 우회 진입

            if not navigated:

                for u in FALLBACK_BIDLIST_URLS:

                    try:

                        print(f"[NAV] javascript 우회 — 직접 이동: {u}")

                        driver.get(u)

                        if _wait_url_or_title(driver, url_sub="invitation", title_has="입찰"):

                            navigated=True; break

                    except Exception:

                        continue

        else:

            # 정상 href 이동

            base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(driver.current_url))

            abs_url = href if urlparse(href).netloc else urljoin(base, href)

            print(f"[NAV] 직접 이동: {abs_url}")

            driver.get(abs_url)

            navigated = _wait_url_or_title(driver, url_sub="invitation", title_has="입찰")

    else:

        # href 못 얻으면 클릭 → 실패 시 최종 우회

        _click_any(driver,

            [("xpath","//a[contains(.,'입찰공고목록')]"),

             ("xpath","//a[contains(.,'입찰공고') and contains(.,'목록')]")],

            desc="입찰공고목록")

        navigated = _wait_url_or_title(driver, url_sub="invitation", title_has="입찰")

        if not navigated:

            for u in FALLBACK_BIDLIST_URLS:

                try:

                    print(f"[NAV] 최종 우회 — 직접 이동: {u}")

                    driver.get(u)

                    if _wait_url_or_title(driver, url_sub="invitation", title_has="입찰"):

                        navigated=True; break

                except Exception:

                    continue



    if not navigated:

        print("[ERR] '입찰공고목록' 페이지로 이동 실패")

        return False



    print("[OK] 입찰공고목록 진입 완료")

    return True



def main():

    ap = argparse.ArgumentParser()

    ap.add_argument("--url", default=DEFAULT_URL)

    ap.add_argument("--ind", default=None, help="업종 코드 (예: 0040 전기, 0039 소방)")

    ap.add_argument("--regions", default=None, help='쉼표 구분 지역 (예: "경상북도,인천광역시")')

    ap.add_argument("--due_from", default=None, help="마감 시작 (YYYY-MM-DD)")

    ap.add_argument("--due_to", default=None, help="마감 끝 (YYYY-MM-DD)")

    ap.add_argument("--headless", default="1")

    ap.add_argument("--winsize", default=DEFAULT_WINSIZE)

    ap.add_argument("--download", default=DEFAULT_DOWNLOAD_DIR)

    args = ap.parse_args()



    headless = str(args.headless).strip().lower() in ("1","true","y","yes","on")

    download_dir = ensure_dir(args.download)



    driver = None

    try:

        driver = build_driver(headless=headless, winsize=args.winsize, download_dir=download_dir)

        print(f"[NAV] GET {args.url}")

        driver.get(args.url)

        try:

            WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        except TimeoutException:

            print("[WARN] 초기 로드 지연")



        # 팝업 정리

        close_all_popups(driver)



        # 입찰공고목록 강제 이동(우회 포함)

        go_to_bid_list(driver)



        print("[DONE] 작업 종료")

    except WebDriverException as e:

        print(f"[FATAL] WebDriver 오류: {e}")

        sys.exit(2)

    except Exception as e:

        print(f"[FATAL] 예기치 못한 오류: {e}")

        sys.exit(3)

    finally:

        if driver:

            try: driver.quit()

            except Exception: pass



if __name__ == "__main__":

    main()

