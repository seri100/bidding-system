#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
한국도로공사 전자조달시스템 입찰공사 수집 스크립트 - DB 미사용 버전

- 사이트: https://ebid.ex.co.kr/default.do
- 템플릿코드: UC_8365
- DB 사용 안 함
- 결과 저장 위치:
  /mnt/vol1/bid/exroad

생성 파일:
1) raw/exroad_raw_날짜.xlsx
2) target/exroad_target_날짜.xlsx
3) send_ready/exroad_send_ready_날짜.xlsx
4) sent_keys.txt
"""

import os
import re
import time
import json
import argparse
import hashlib
import subprocess
import datetime as dt
from pathlib import Path

import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait


# ============================================================
# 기본 설정
# ============================================================





# ============================================================

# 한국도로공사 입찰면허 코드 매핑 / 대상 필터

# ============================================================



TARGET_LICENSE_CODES = [

    "6202",  # 기계가스설비공사업

    "0038",  # 소방 관련

    "0039",  # 소방 관련

    "0040",  # 전문소방시설공사업 계열

]



LICENSE_CODE_MAP = {

    "0001": "토목공사업",

    "0002": "건축공사업",

    "0005": "조경공사업",

    "0036": "정보통신공사업",

    "0038": "소방시설공사업",

    "0039": "소방시설공사업",

    "0040": "전문소방시설공사업",

    "6202": "기계가스설비공사업",

    "1449": "상하수도설비공사업",

    "4992": "도장/습식/방수/석공사업",

    "4993": "조경식재/시설물공사업",

}




EXROAD_URL = "https://ebid.ex.co.kr/default.do"

TEMPLATE_ID = "UC_8365"

# Windows: Z:\VOL1\bid\bid\exroad
# Raspberry Pi: /mnt/vol1/bid/exroad
BASE_DIR = Path(os.environ.get("EXROAD_BASE_DIR", "/mnt/vol1/bid/exroad"))

RAW_DIR = BASE_DIR / "raw"
TARGET_DIR = BASE_DIR / "target"
SEND_READY_DIR = BASE_DIR / "send_ready"
LOG_DIR = BASE_DIR / "logs"
DEBUG_DIR = BASE_DIR / "debug"
SENT_KEYS_FILE = BASE_DIR / "sent_keys.txt"

for p in [RAW_DIR, TARGET_DIR, SEND_READY_DIR, LOG_DIR, DEBUG_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# 테스트 수신자
DEFAULT_RECEIVERS = ["REDACTED_PRIVATE_VALUE"]

# 조회 기간 기본값
DEFAULT_HOURS = int(os.environ.get("EXROAD_HOURS", "24"))

# 도로공사 템플릿 변수
# #{bid_no}
# #{bid_name}
# #{license}
# #{amount}
# #{limit_type}

TARGET_LICENSE_KEYWORDS = [
    "기계가스설비",
    "기계설비",
    "가스시설시공업",
    "가스시설",
    "전문소방",
    "일반소방",
    "소방시설",
    "소방공사",
]

EXCLUDE_NAME_KEYWORDS = [
    "용역",
    "감리",
    "설계",
    "폐기물",
    "건설사업관리",
]

MIN_AMOUNT = int(os.environ.get("EXROAD_MIN_AMOUNT", "0"))
MAX_AMOUNT = int(os.environ.get("EXROAD_MAX_AMOUNT", "999999999999"))

LOCAL_KEYWORDS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산",
    "세종", "경기", "강원", "충북", "충남", "전북", "전남",
    "경북", "경남", "제주",
    "강원특별자치도", "전북특별자치도",
]


# ============================================================
# 공통 함수
# ============================================================

def now_str():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp():
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def log(msg):
    line = f"[{now_str()}] {msg}"
    print(line, flush=True)

    log_file = LOG_DIR / f"exroad_{dt.datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def norm_text(v):
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def only_digits(v):
    return re.sub(r"[^0-9]", "", str(v or ""))


def parse_amount(v):
    s = only_digits(v)
    if not s:
        return 0
    try:
        return int(s)
    except Exception:
        return 0


def fmt_money(v):
    try:
        return f"{int(v):,}원"
    except Exception:
        return str(v or "")


def load_sent_keys():
    if not SENT_KEYS_FILE.exists():
        return set()

    with open(SENT_KEYS_FILE, "r", encoding="utf-8") as f:
        return set(x.strip() for x in f if x.strip())


def append_sent_key(key):
    with open(SENT_KEYS_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def make_notice_key(row, receiver):
    bid_no = norm_text(row.get("bid_no"))
    bid_name = norm_text(row.get("bid_name"))
    base = f"EXROAD|{TEMPLATE_ID}|{bid_no}|{bid_name}|{receiver}"
    h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"EXROAD:{bid_no}:{receiver}:{h}"


def format_exroad_datetime(v):
    """EXROAD YYYYMMDDHHMM[SS] 값을 알림톡 표시 형식으로 변환한다."""
    s = only_digits(v)
    if len(s) < 12:
        return ""

    try:
        parsed = dt.datetime.strptime(s[:12], "%Y%m%d%H%M")
        return parsed.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def raw_row_data(row):
    raw = row.get("raw_text")
    if isinstance(raw, dict):
        return raw

    try:
        value = json.loads(str(raw or ""))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

# ============================================================
# Selenium 함수
# ============================================================

def make_driver(headless=True):
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("REDACTED_PRIVATE_VALUE")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--lang=ko-KR")

    chromedriver = os.environ.get("CHROMEDRIVER", "REDACTED_PRIVATE_VALUE")

    if Path(chromedriver).exists():
        service = Service(chromedriver)
        return webdriver.Chrome(service=service, options=options)

    return webdriver.Chrome(options=options)


def save_debug(driver, name):
    ts = stamp()

    html_path = DEBUG_DIR / f"{name}_{ts}.html"
    png_path = DEBUG_DIR / f"{name}_{ts}.png"

    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
        log(f"[DEBUG] HTML 저장: {html_path}")
    except Exception as e:
        log(f"[DEBUG][HTML][ERR] {e}")

    try:
        driver.save_screenshot(str(png_path))
        log(f"[DEBUG] 화면 저장: {png_path}")
    except Exception as e:
        log(f"[DEBUG][PNG][ERR] {e}")


def click_by_text(driver, texts):
    for text in texts:
        xpaths = [
            f"//*[contains(normalize-space(.), '{text}')]",
            f"//a[contains(normalize-space(.), '{text}')]",
            f"//button[contains(normalize-space(.), '{text}')]",
            f"//span[contains(normalize-space(.), '{text}')]",
        ]

        for xp in xpaths:
            try:
                elems = driver.find_elements(By.XPATH, xp)
                elems = [e for e in elems if e.is_displayed()]

                if not elems:
                    continue

                elem = elems[0]
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    elem
                )
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", elem)
                time.sleep(1)

                log(f"[CLICK] {text}")
                return True

            except Exception:
                continue

    return False

def click_menu_by_id(driver, menu_id, wait_sec=2):
    """
    한국도로공사 전자조달시스템 메뉴를 ID로 직접 클릭
    예:
      NPRO11000 = 공사
      NPRO11001 = 입찰공고(공사)
    """
    try:
        elem = driver.find_element(By.ID, menu_id)

        driver.execute_script(
            """
            arguments[0].scrollIntoView({block:'center'});
            """,
            elem
        )
        time.sleep(0.5)

        driver.execute_script(
            """
            var el = arguments[0];
            var btn = el.querySelector('button') || el.querySelector('a') || el;
            btn.click();
            """,
            elem
        )

        log(f"[MENU_ID][CLICK] {menu_id}")
        time.sleep(wait_sec)
        return True

    except Exception as e:
        log(f"[MENU_ID][ERR] {menu_id}: {e}")
        return False
def set_date_inputs(driver, start_dt, end_dt):
    start_s = start_dt.strftime("%Y-%m-%d")
    end_s = end_dt.strftime("%Y-%m-%d")

    inputs = driver.find_elements(By.XPATH, "//input")
    visible = []

    for inp in inputs:
        try:
            if inp.is_displayed():
                visible.append(inp)
        except Exception:
            pass

    candidates = []

    for inp in visible:
        name = (inp.get_attribute("name") or "").lower()
        iid = (inp.get_attribute("id") or "").lower()
        typ = (inp.get_attribute("type") or "").lower()
        ph = (inp.get_attribute("placeholder") or "").lower()
        meta = " ".join([name, iid, typ, ph])

        if (
            "date" in meta
            or "일자" in meta
            or "기간" in meta
            or "from" in meta
            or "to" in meta
            or "start" in meta
            or "end" in meta
            or "bgn" in meta
        ):
            candidates.append(inp)

    if len(candidates) >= 2:
        vals = [start_s, end_s]

        for inp, val in zip(candidates[:2], vals):
            try:
                driver.execute_script(
                    """
                    arguments[0].removeAttribute('readonly');
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input'));
                    arguments[0].dispatchEvent(new Event('change'));
                    """,
                    inp,
                    val
                )
            except Exception:
                try:
                    inp.clear()
                    inp.send_keys(val)
                except Exception:
                    pass

        log(f"[DATE] {start_s} ~ {end_s}")
        return True

    log("[DATE][WARN] 날짜 입력칸 자동 설정 실패")
    return False




def go_bid_list(driver, start_dt, end_dt):

    log(f"[OPEN] {EXROAD_URL}")



    driver.get(EXROAD_URL)



    WebDriverWait(driver, 20).until(

        lambda d: d.execute_script("return document.readyState") == "complete"

    )



    time.sleep(5)



    # 팝업/확인창 닫기 후보

    for txt in ["확인", "닫기", "오늘 하루", "Close"]:

        click_by_text(driver, [txt])



    time.sleep(2)



    # 한국도로공사 메뉴 ID 기준 직접 이동

    # NPRO00000 = 입찰

    # NPRO11000 = 공사

    # NPRO11001 = 입찰공고(공사)

    log("[MENU] ID 방식으로 입찰공고(공사) 이동 시작")



    click_menu_by_id(driver, "NPRO00000", wait_sec=2)

    click_menu_by_id(driver, "NPRO11000", wait_sec=2)

    click_menu_by_id(driver, "NPRO11001", wait_sec=8)



    time.sleep(8)



    save_debug(driver, "after_menu_click")



    # 날짜 설정 시도

    set_date_inputs(driver, start_dt, end_dt)



    # 조회 버튼 클릭

    click_by_text(driver, ["조회", "검색"])



    time.sleep(5)



    save_debug(driver, "after_search")





def extract_rows_from_tables(driver):

    """

    한국도로공사 입찰공고(공사) 목록 추출



    이 화면은 일반 HTML table이 아니라 sc-grid/canvas 그리드이므로

    DOM의 tr/td가 아닌 grid dataProvider에서 직접 데이터를 읽는다.

    """



    js = r"""

    function safeCall(obj, name, args) {

        try {

            if (obj && typeof obj[name] === 'function') {

                return obj[name].apply(obj, args || []);

            }

        } catch(e) {}

        return null;

    }



    function isArrayRows(v) {

        return Array.isArray(v) && v.length > 0 && typeof v[0] === 'object';

    }



    var grid = document.querySelector('sc-grid#gridPanel');

    var result = {

        ok: false,

        rows: [],

        debug: {}

    };



    if (!grid) {

        result.debug.error = 'gridPanel not found';

        return result;

    }



    result.debug.gridKeys = Object.keys(grid).slice(0, 80);



    var candidates = [];



    try { candidates.push(grid.getDataProvider && grid.getDataProvider()); } catch(e) {}

    try { candidates.push(grid.dataProvider); } catch(e) {}

    try { candidates.push(grid._dataProvider); } catch(e) {}

    try { candidates.push(grid.provider); } catch(e) {}

    try { candidates.push(grid._provider); } catch(e) {}

    try { candidates.push(grid.getGridView && grid.getGridView()); } catch(e) {}

    try { candidates.push(grid.gridView); } catch(e) {}

    try { candidates.push(grid._gridView); } catch(e) {}

    try { candidates.push(grid.$ && grid.$.gridView); } catch(e) {}

    try { candidates.push(grid.$ && grid.$.dataProvider); } catch(e) {}



    for (var ci = 0; ci < candidates.length; ci++) {

        var obj = candidates[ci];

        if (!obj) continue;



        var name = 'candidate_' + ci;

        try { result.debug[name + '_keys'] = Object.keys(obj).slice(0, 80); } catch(e) {}



        var rows = null;



        rows = safeCall(obj, 'getItems', []);

        if (isArrayRows(rows)) {

            result.ok = true;

            result.rows = rows;

            result.debug.method = name + '.getItems';

            return result;

        }



        rows = safeCall(obj, 'getRows', []);

        if (isArrayRows(rows)) {

            result.ok = true;

            result.rows = rows;

            result.debug.method = name + '.getRows';

            return result;

        }



        rows = safeCall(obj, 'getJsonRows', []);

        if (isArrayRows(rows)) {

            result.ok = true;

            result.rows = rows;

            result.debug.method = name + '.getJsonRows()';

            return result;

        }



        var cnt = safeCall(obj, 'getRowCount', []);

        if (cnt === null || cnt === undefined) {

            cnt = safeCall(obj, 'getItemCount', []);

        }



        if (typeof cnt === 'number' && cnt > 0) {

            var arr = [];



            var all1 = safeCall(obj, 'getJsonRows', [0, cnt - 1]);

            if (isArrayRows(all1)) {

                result.ok = true;

                result.rows = all1;

                result.debug.method = name + '.getJsonRows(0,cnt-1)';

                return result;

            }



            var all2 = safeCall(obj, 'getRows', [0, cnt - 1]);

            if (isArrayRows(all2)) {

                result.ok = true;

                result.rows = all2;

                result.debug.method = name + '.getRows(0,cnt-1)';

                return result;

            }



            for (var i = 0; i < cnt; i++) {

                var r = null;

                r = safeCall(obj, 'getJsonRow', [i]);

                if (!r) r = safeCall(obj, 'getDataRow', [i]);

                if (!r) r = safeCall(obj, 'getRow', [i]);

                if (r && typeof r === 'object') arr.push(r);

            }



            if (arr.length > 0) {

                result.ok = true;

                result.rows = arr;

                result.debug.method = name + '.rowLoop';

                return result;

            }

        }



        var ds = safeCall(obj, 'getDataSource', []);

        if (ds) {

            try { result.debug[name + '_ds_keys'] = Object.keys(ds).slice(0, 80); } catch(e) {}



            var dcnt = safeCall(ds, 'getRowCount', []);

            if (typeof dcnt === 'number' && dcnt > 0) {

                var arr2 = [];



                var dsAll = safeCall(ds, 'getJsonRows', [0, dcnt - 1]);

                if (isArrayRows(dsAll)) {

                    result.ok = true;

                    result.rows = dsAll;

                    result.debug.method = name + '.getDataSource.getJsonRows';

                    return result;

                }



                for (var j = 0; j < dcnt; j++) {

                    var rr = null;

                    rr = safeCall(ds, 'getJsonRow', [j]);

                    if (!rr) rr = safeCall(ds, 'getRow', [j]);

                    if (rr && typeof rr === 'object') arr2.push(rr);

                }



                if (arr2.length > 0) {

                    result.ok = true;

                    result.rows = arr2;

                    result.debug.method = name + '.getDataSource.rowLoop';

                    return result;

                }

            }

        }

    }



    return result;

    """



    data = driver.execute_script(js)



    try:

        log("[GRID_DEBUG] " + json.dumps(data.get("debug", {}), ensure_ascii=False)[:2000])

    except Exception:

        pass



    grid_rows = []

    if isinstance(data, dict) and data.get("ok") and isinstance(data.get("rows"), list):

        grid_rows = data.get("rows") or []



    rows = []



    for item in grid_rows:

        if not isinstance(item, dict):

            continue



        bid_no = norm_text(

            item.get("noti_no")

            or item.get("bid_no")

            or item.get("공고번호")

        )



        bid_name = norm_text(

            item.get("noti_nm")

            or item.get("bid_name")

            or item.get("공고명")

        )



        area = norm_text(item.get("area") or item.get("지역"))



        license_text = norm_text(

            item.get("bid_shpr")

            or item.get("bid_shpr1_ct")

            or item.get("bid_shpr2")

            or item.get("입찰면허")

        )



        # 면허가 1/2로 나뉘어 있으면 합침

        license_parts = []

        for k in ["bid_shpr1_ct", "bid_shpr2", "bid_shpr1_sv"]:

            v = norm_text(item.get(k))

            if v and v not in license_parts:

                license_parts.append(v)

        if license_parts:

            license_text = " ".join(license_parts)



        amount = parse_amount(

            item.get("dsgng_amt")

            or item.get("amount")

            or item.get("설계금액")

        )



        limit_type = norm_text(

            item.get("lmtcpt_apply_bas_cd")

            or item.get("limit_type")

            or item.get("제한유형")

        )



        noti_date = norm_text(

            item.get("noti_date")

            or item.get("공고일자")

        )



        prog_sts = norm_text(

            item.get("prog_sts")

            or item.get("상태")

        )



        # 코드값이면 한글 표시명 보강

        # 예: "3000 0036" -> "3000 0036 정보통신공사업"

        try:

            mapped_names = []

            for code, name in LICENSE_CODE_MAP.items():

                if code in license_text and name not in mapped_names:

                    mapped_names.append(name)

            if mapped_names:

                license_text = (license_text + " " + " ".join(mapped_names)).strip()

        except Exception:

            pass



        raw_text = json.dumps(item, ensure_ascii=False)



        if not bid_no and not bid_name:

            continue



        # 공고번호가 없으면 공고명 기준 임시 키 생성

        if not bid_no:

            bid_no = "EXROAD_" + hashlib.sha1(bid_name.encode("utf-8")).hexdigest()[:12]



        rows.append({

            "source": "한국도로공사",

            "template_id": TEMPLATE_ID,

            "bid_no": bid_no,

            "bid_name": bid_name,

            "area": area,

            "license": license_text,

            "amount": amount,

            "amount_text": fmt_money(amount),

            "limit_type": limit_type or "미확인",

            "noti_date": noti_date,

            "prog_sts": prog_sts,

            "raw_text": raw_text,

        })



    log(f"[GRID_EXTRACT] rows={len(rows)}")



    if rows:

        return rows



    # fallback: 기존 table 방식

    fallback = []

    trs = driver.find_elements(By.XPATH, "//table//tr")

    log(f"[TABLE] tr count={len(trs)}")



    for tr in trs:

        try:

            if not tr.is_displayed():

                continue



            cells = tr.find_elements(By.XPATH, "./th|./td")

            texts = [norm_text(c.text) for c in cells]

            texts = [x for x in texts if x]



            if len(texts) < 3:

                continue



            full = " ".join(texts)

            log("[ROW_DEBUG] " + " | ".join(texts[:30]))



        except Exception:

            continue



    return fallback



# ============================================================
# 필터
# ============================================================

def is_target_row(row):

    """

    한국도로공사 발송 대상 판단



    기본 normal 모드:

    - n_data 대상과 유사하게 기계설비/소방 관련만 통과

    - 한글명과 코드값 둘 다 확인



    테스트 all 모드:

    - EXROAD_FILTER_MODE=all 이면 전체 통과

    """

    if os.environ.get("EXROAD_FILTER_MODE", "normal").lower() == "all":

        return True, "OK_ALL_TEST"



    bid_name = norm_text(row.get("bid_name"))

    license_text = norm_text(row.get("license"))

    raw = norm_text(row.get("raw_text"))

    amount = int(row.get("amount") or 0)



    combined = " ".join([bid_name, license_text, raw])



    if any(k in bid_name for k in EXCLUDE_NAME_KEYWORDS):

        return False, "EXCLUDE_NAME"



    keyword_ok = any(k in combined for k in TARGET_LICENSE_KEYWORDS)

    code_ok = any(c in combined for c in TARGET_LICENSE_CODES)



    if not keyword_ok and not code_ok:

        return False, "NO_TARGET_LICENSE"



    if amount and amount < MIN_AMOUNT:

        return False, "UNDER_MIN_AMOUNT"



    if amount and amount > MAX_AMOUNT:

        return False, "OVER_MAX_AMOUNT"



    return True, "OK"



def filter_rows(rows):
    targets = []

    for r in rows:
        ok, reason = is_target_row(r)
        r["filter_result"] = reason

        if ok:
            targets.append(r)

    log(f"[FILTER] target={len(targets)} / total={len(rows)}")

    return targets


# ============================================================
# 상세 공고문(HWP) 자동 보완
# ============================================================

def parse_exroad_notice_text(text):
    """입찰공고문에서 공동도급 관련 필드를 보수적으로 추출한다."""
    clean_text = str(text or "").replace("\u00a0", " ")
    result = {
        "joint_region": "",
        "joint_rate": "",
        "joint_method": "",
        "joint_member_min_rate": "",
    }

    patterns = [
        r"공사현장\s*관할지역(?:은|\s*[:：])?\s*([^\n.]+)",
        r"공사현장\s*소재지(?:는|\s*[:：])?\s*([^\n.]+)",
        r"공사현장(?:은|\s*[:：])?\s*([^\n.]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, clean_text)
        if m:
            value = norm_text(m.group(1)).rstrip("입니다").strip(" .,:：")
            if value:
                result["joint_region"] = value
                break

    rate_patterns = [
        r"지역업체의\s*최소지분율은\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*이상",
        r"지역업체[^\n]{0,80}?([0-9]+(?:\.[0-9]+)?)\s*%\s*이상",
        r"지역업체[^\n]{0,80}?([0-9]+(?:\.[0-9]+)?)\s*%",
    ]
    for pattern in rate_patterns:
        m = re.search(pattern, clean_text)
        if m:
            result["joint_rate"] = m.group(1) + "% 이상"
            break

    method_match = re.search(r"이행방식\s*[:：]\s*([^\n]+)", clean_text)
    if method_match:
        result["joint_method"] = norm_text(method_match.group(1)).strip(" .")

    member_match = re.search(
        r"대표자를\s*제외한\s*구성원[^\n]{0,100}?최소지분율이\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*%\s*이상",
        clean_text,
    )
    if member_match:
        result["joint_member_min_rate"] = member_match.group(1) + "% 이상"

    return result


def wait_for_exroad_detail_files(driver, timeout=20):
    end_time = time.time() + timeout
    script = r"""
        var shared = document.querySelector('es-sp-bid-shared');
        if (!shared || !shared.$ || !shared.$.findInfoBidShared) return null;
        var response = shared.$.findInfoBidShared.lastResponse;
        if (!response || !Array.isArray(response.fileAttList)) return null;
        return response.fileAttList;
    """

    while time.time() < end_time:
        try:
            files = driver.execute_script(script)
            if isinstance(files, list):
                return files
        except Exception:
            pass
        time.sleep(0.5)

    return []


def open_exroad_detail(driver, raw_data):
    return driver.execute_script(
        r"""
        var target = arguments[0];
        var parent = document.querySelector('em-sp-bid-noti-ct');
        if (!parent || !parent.$ || !parent.$.detail) {
            return {ok:false, error:'detail component not found'};
        }
        parent.$.pages.selectItem(parent.$.detail);
        parent.$.detail.load(
            parent.titleText ? parent.titleText.detail : '입찰공고 상세',
            parent.pageType,
            target
        );
        return {ok:true};
        """,
        raw_data,
    )


def download_exroad_notice_hwp(driver, row, file_data):
    bid_no = norm_text(row.get("bid_no")) or "unknown"
    document_dir = BASE_DIR / "documents" / bid_no
    document_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(document_dir.glob("*.hwp"))
    if existing:
        return existing[-1]

    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(document_dir)},
    )

    popup_result = driver.execute_script(
        r"""
        var data = arguments[0];
        var shared = document.querySelector('es-sp-bid-shared');
        if (!shared || typeof shared.callAttachPopup !== 'function') {
            return {ok:false, error:'callAttachPopup not found'};
        }
        shared.callAttachPopup(
            data,
            {rowIndex:0, dataField:'file_att_cnt'},
            null
        );
        return {ok:true};
        """,
        file_data,
    )
    if not popup_result or not popup_result.get("ok"):
        raise RuntimeError("첨부 팝업 열기 실패: %s" % popup_result)

    end_time = time.time() + 20
    download_called = False
    while time.time() < end_time:
        result = driver.execute_script(
            r"""
            var wanted = String(arguments[0] || '');
            var popups = document.querySelectorAll('ep-raonk-attach-sub');
            for (var i = popups.length - 1; i >= 0; i--) {
                var popup = popups[i];
                var uploader = popup.$ && popup.$.raonKUpload
                    ? popup.$.raonKUpload : popup.querySelector('cc-upload');
                if (!uploader || typeof uploader.onFileDownload !== 'function') {
                    continue;
                }
                if (!uploader.value || !uploader.dtlValue) {
                    continue;
                }
                if (wanted && String(uploader.dtlValue) !== wanted) {
                    continue;
                }
                uploader.onFileDownload();
                return {
                    ready:true,
                    value:uploader.value,
                    dtlValue:uploader.dtlValue
                };
            }
            return {ready:false};
            """,
            norm_text(file_data.get("file_att_id")),
        )
        if result and result.get("ready"):
            download_called = True
            break
        time.sleep(0.5)

    if not download_called:
        raise RuntimeError("첨부파일 다운로드 함수 준비 시간 초과")

    end_time = time.time() + 60
    while time.time() < end_time:
        downloading = list(document_dir.glob("*.crdownload"))
        hwp_files = sorted(document_dir.glob("*.hwp"))
        if hwp_files and not downloading:
            return hwp_files[-1]
        time.sleep(1)

    raise RuntimeError("HWP 다운로드 완료 시간 초과")


def convert_exroad_hwp_to_text(hwp_path):
    txt_path = hwp_path.with_suffix(".txt")
    if txt_path.exists() and txt_path.stat().st_size > 0:
        return txt_path

    hwp5txt = Path("/home/pi/exroad/.venv_hwp/bin/hwp5txt")
    if not hwp5txt.exists():
        raise RuntimeError("hwp5txt 없음: %s" % hwp5txt)

    proc = subprocess.run(
        [str(hwp5txt), "--output", str(txt_path), str(hwp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("hwp5txt 실패 rc=%s output=%s" % (proc.returncode, proc.stdout))

    return txt_path


def enrich_exroad_target_row(driver, row):
    raw_data = raw_row_data(row)
    close_time = format_exroad_datetime(
        raw_data.get("bid_end_dt") or row.get("bid_end_dt")
    )
    if close_time:
        row["close_time"] = close_time

    row["bid_end_dt"] = norm_text(raw_data.get("bid_end_dt"))
    row["open_time"] = format_exroad_datetime(raw_data.get("open_dt"))
    row["noti_id"] = norm_text(raw_data.get("noti_id"))
    row["noti_cont_id"] = norm_text(raw_data.get("noti_cont_id"))
    row["bid_ord"] = "000"

    bid_no = norm_text(row.get("bid_no"))
    document_dir = BASE_DIR / "documents" / bid_no
    txt_files = sorted(document_dir.glob("*.txt")) if document_dir.exists() else []

    if txt_files:
        txt_path = txt_files[-1]
    else:
        detail_result = open_exroad_detail(driver, raw_data)
        if not detail_result or not detail_result.get("ok"):
            raise RuntimeError("상세화면 열기 실패: %s" % detail_result)

        file_list = wait_for_exroad_detail_files(driver)
        notice_file = None
        for item in file_list:
            filename = norm_text(item.get("orgn_file_nm"))
            if "입찰공고문" in filename and filename.lower().endswith(".hwp"):
                notice_file = item
                break

        if notice_file is None:
            raise RuntimeError("입찰공고문 HWP를 찾지 못함")

        hwp_path = download_exroad_notice_hwp(driver, row, notice_file)
        txt_path = convert_exroad_hwp_to_text(hwp_path)
        row["document_path"] = str(hwp_path)

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_exroad_notice_text(text)
    row.update({k: v for k, v in parsed.items() if v})
    row["document_text_path"] = str(txt_path)

    log(
        "[DETAIL_ENRICH][OK] bid_no=%s close=%s region=%s rate=%s method=%s"
        % (
            bid_no,
            row.get("close_time", ""),
            row.get("joint_region", ""),
            row.get("joint_rate", ""),
            row.get("joint_method", ""),
        )
    )


def enrich_new_exroad_targets(driver, rows):
    sent_keys = load_sent_keys()
    count = 0

    for row in rows:
        ok, _ = is_target_row(row)
        if not ok:
            continue

        is_new = any(
            make_notice_key(row, receiver) not in sent_keys
            for receiver in DEFAULT_RECEIVERS
        )
        if not is_new:
            continue

        try:
            enrich_exroad_target_row(driver, row)
            count += 1
        except Exception as exc:
            raw_data = raw_row_data(row)
            close_time = format_exroad_datetime(raw_data.get("bid_end_dt"))
            if close_time:
                row["close_time"] = close_time
            log(
                "[DETAIL_ENRICH][WARN] bid_no=%s error=%s"
                % (norm_text(row.get("bid_no")), exc)
            )

    log("[DETAIL_ENRICH] enriched=%d" % count)


# ============================================================
# 발송 준비 파일 생성
# ============================================================

def make_send_ready_rows(target_rows, receivers, no_mark=False):
    sent_keys = load_sent_keys()
    send_rows = []
    skip_count = 0

    for row in target_rows:
        for receiver in receivers:
            notice_key = make_notice_key(row, receiver)

            if notice_key in sent_keys:
                log(f"[SKIP_ALREADY] {notice_key}")
                skip_count += 1
                continue

            payload = {
                "bid_no": norm_text(row.get("bid_no")),
                "bid_ord": norm_text(row.get("bid_ord") or "000"),
                "bid_name": norm_text(row.get("bid_name")),
                "license": norm_text(row.get("license") or "미확인"),
                "amount": fmt_money(row.get("amount") or 0),
                "limit_type": norm_text(row.get("limit_type") or "미확인"),
                "close_time": norm_text(row.get("close_time") or "미기재"),
                "joint_region": norm_text(row.get("joint_region")),
                "joint_rate": norm_text(row.get("joint_rate")),
                "joint_method": norm_text(row.get("joint_method")),
                "joint_member_min_rate": norm_text(row.get("joint_member_min_rate")),
                "document_path": norm_text(row.get("document_path")),
                "document_text_path": norm_text(row.get("document_text_path")),
            }

            kakao_message = (
                "[세리공영] 한국도로공사 입찰 알림\n"
                f"공고번호 : {payload['bid_no']}\n"
                f"공고명 : {payload['bid_name']}\n"
                f"입찰면허 : {payload['license']}\n"
                f"설계금액 : {payload['amount']}\n"
                f"제한유형 : {payload['limit_type']}\n"
                f"입찰마감일시 : {payload['close_time']}\n"
                f"공동도급지역 : {payload['joint_region']}\n"
                f"공동도급비율 : {payload['joint_rate']}"
            )

            send_rows.append({
                "notice_key": notice_key,
                "template_id": TEMPLATE_ID,
                "receiver": receiver,

                "bid_no": payload["bid_no"],
                "bid_ord": payload["bid_ord"],
                "bid_name": payload["bid_name"],
                "license": payload["license"],
                "amount": payload["amount"],
                "limit_type": payload["limit_type"],
                "close_time": payload["close_time"],
                "joint_region": payload["joint_region"],
                "joint_rate": payload["joint_rate"],
                "joint_method": payload["joint_method"],
                "joint_member_min_rate": payload["joint_member_min_rate"],
                "document_path": payload["document_path"],
                "document_text_path": payload["document_text_path"],

                "message": kakao_message,
                "payload_json": json.dumps(payload, ensure_ascii=False),

                "created_at": now_str(),
                "send_status": "READY",
                "source": "한국도로공사",
            })

            if not no_mark:
                append_sent_key(notice_key)

    log(f"[SEND_READY] rows={len(send_rows)} skip={skip_count}")

    return send_rows

# ============================================================
# 메인
# ============================================================

def run(hours=DEFAULT_HOURS, no_mark=False, headless=True):
    start_time = dt.datetime.now()
    end_dt = start_time
    start_dt = end_dt - dt.timedelta(hours=hours)

    log("=" * 70)
    log("[START] 한국도로공사 입찰공사 수집")
    log(f"[BASE_DIR] {BASE_DIR}")
    log(f"[TEMPLATE] {TEMPLATE_ID}")
    log(f"[PERIOD] {start_dt} ~ {end_dt}")

    driver = None
    rows = []

    try:
        driver = make_driver(headless=headless)
        go_bid_list(driver, start_dt, end_dt)
        rows = extract_rows_from_tables(driver)
        enrich_new_exroad_targets(driver, rows)

    except Exception as e:
        log(f"[SCRAPE][ERR] {e}")
        if driver:
            save_debug(driver, "error")

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    ts = stamp()

    if not rows:
        log("[DONE] 수집 데이터 없음")
        return

    raw_file = RAW_DIR / f"exroad_raw_{ts}.xlsx"
    pd.DataFrame(rows).to_excel(raw_file, index=False)
    log(f"[SAVE] raw={raw_file}")

    target_rows = filter_rows(rows)

    target_file = TARGET_DIR / f"exroad_target_{ts}.xlsx"
    pd.DataFrame(target_rows).to_excel(target_file, index=False)
    log(f"[SAVE] target={target_file}")

    if not target_rows:
        log("[DONE] 조건 통과 대상 없음")
        return

    receivers = DEFAULT_RECEIVERS

    send_ready_rows = make_send_ready_rows(
        target_rows=target_rows,
        receivers=receivers,
        no_mark=no_mark,
    )

    if send_ready_rows:
        send_file = SEND_READY_DIR / f"exroad_send_ready_{ts}.xlsx"
        pd.DataFrame(send_ready_rows).to_excel(send_file, index=False)
        log(f"[SAVE] send_ready={send_file}")
    else:
        log("[DONE] 신규 발송 준비 대상 없음")

    log("[DONE] 완료")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    parser.add_argument("--show-browser", action="store_true")

    # 테스트 시 sent_keys.txt에 기록하지 않음
    parser.add_argument("--no-mark", action="store_true")

    args = parser.parse_args()

    run(
        hours=args.hours,
        no_mark=args.no_mark,
        headless=not args.show_browser,
    )


if __name__ == "__main__":
    main()
