
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import ast
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup
# n_data 알림톡 재사용
sys.path.append("/home/pi/n_data")
try:
    from kakao_send_tb0485 import send_for_item as kakao_send_for_item
except Exception as e:
    print("[WARN] kakao import fail:", e)
    kakao_send_for_item = None
BASE_DIR = Path("/home/pi/bid-nr")
NAS_BASE = Path(os.environ.get("BID_NR_BASE", "/mnt/vol1/bid/bid-nr"))
RAW_DIR = NAS_BASE / "raw"
REPORT_DIR = NAS_BASE / "report"
STATE_DIR = NAS_BASE / "state"
LOG_DIR = BASE_DIR / "logs"
for d in [RAW_DIR, REPORT_DIR, STATE_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)
SENT_KEYS = STATE_DIR / "sent_keys.txt"
LOG_FILE = LOG_DIR / ("run_%s.log" % datetime.now().strftime("%Y%m%d"))
BASE_URL = "https://ebid.kr.or.kr/bid/anc/bidAncList.do"
DETAIL_URL = "https://ebid.kr.or.kr/bid/anc/bidAncDetail.do"
DOWN_URL = "https://ebid.kr.or.kr/common/FileDown.do"
KEYWORDS = ["소방시설", "소방설비", "기계설비"]
DETAIL_NAMES = [
    "gyErBeonho", "crSangtae", "ggDrIrja", "ggNyeondo",
    "ggIrBeonho", "ygGeumaeg", "ggChasu", "cjbcDrMyeong",
    "irBeonho", "ggGubun",
]
HTTP = requests.Session()
HTTP.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://ebid.kr.or.kr/",
})
RECEIVERS = [
    "REDACTED_PRIVATE_VALUE"
]
def send_kakao_one(phone, row, no_send=False):
    fields = {
        # kakao_send_tb0485.py 실제 사용 필드
        "bid_name": row.get("공고명", ""),
        "close_time": row.get("개찰예정일", ""),
        "joint_region": row.get("공동도급지역") or "해당없음",
        "joint_rate": row.get("공동도급비율") or "해당없음",
        "bid_no": row.get("공고번호", ""),
        "bid_ord": "000",
        # 금액 필드
        "amount": row.get("설계금액", 0),
        "amount_str": f'{int(row.get("설계금액", 0)):,}',
        # 참고용 추가 필드
        "agency": "국가철도공단",
        "license": row.get("매칭키워드", ""),
        "method": row.get("처리상태", ""),
        "url": row.get("상세URL", ""),
        "source": "NR",
    }
    msg = (
        "[국가철도공단]\n\n"
        "공고명 : {공고명}\n"
        "공고번호 : {공고번호}\n"
        "공고구분 : {공고구분}\n"
        "설계금액 : {설계금액:,}원\n"
        "공고게시일 : {공고게시일}\n"
        "개찰예정일 : {개찰예정일}\n"
        "처리상태 : {처리상태}\n"
        "키워드 : {매칭키워드}\n"
        "상세URL : {상세URL}"
    ).format(**row)
    if no_send:
        log("[SAFE] DRY RUN SEND -> %s\n%s" % (phone, msg))
        return True
    if kakao_send_for_item is None:
        log("[ERROR] kakao_send_for_item import fail")
        return False
    try:
        res = kakao_send_for_item(phone, fields, dry_run=False)
        log("[SEND][OK] %s %s result=%s" % (phone, row["공고번호"], res))
        return True
    except TypeError:
        # 혹시 서버 코드가 구형 인자순서이면 fallback
        res = kakao_send_for_item(fields, phone, dry_run=False)
        log("[SEND][OK][FALLBACK] %s %s result=%s" % (phone, row["공고번호"], res))
        return True
    except Exception as e:
        log("[SEND][ERROR] %s %s" % (row["공고번호"], e))
        return False
def log(msg):
    s = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(s)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(s + "\n")
def load_sent_keys():
    if not SENT_KEYS.exists():
        return set()
    return set(x.strip() for x in SENT_KEYS.read_text(encoding="utf-8").splitlines() if x.strip())
def append_sent_key(key):
    with open(SENT_KEYS, "a", encoding="utf-8") as f:
        f.write(key + "\n")
def norm_money(v):
    if pd.isna(v):
        return 0
    s = re.sub(r"[^0-9]", "", str(v))
    return int(s) if s else 0

def parse_detail_calls(html):
    result = {}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["a", "button"]):
        code = "%s %s" % (tag.get("href", ""), tag.get("onclick", ""))
        m = re.search(r"\bdetail\s*\((.*?)\)", code, re.I | re.S)
        if not m:
            continue
        try:
            args = ast.literal_eval("(" + m.group(1) + ",)")
        except Exception:
            args = tuple(re.findall(r"""['"]([^'"]*)['"]""", m.group(1)))
        if len(args) < len(DETAIL_NAMES):
            continue
        payload = dict(zip(DETAIL_NAMES, [str(x) for x in args]))
        bid_no = "%s-%s-%s-%s" % (
            payload["ggNyeondo"], payload["ggGubun"],
            payload["ggIrBeonho"], payload["ggChasu"],
        )
        result[bid_no] = payload
    return result

def choose_notice_link(detail_html):
    candidates = []
    soup = BeautifulSoup(detail_html, "html.parser")
    for link in soup.find_all("a", href=True):
        m = re.search(r"\bdownload\s*\((.*?)\)", link["href"], re.I | re.S)
        if not m:
            continue
        args = re.findall(r"""['"]([^'"]*)['"]""", m.group(1))
        if len(args) < 3:
            continue
        server_file, original_name, dir_id = args[:3]
        score = (
            (100 if "입찰공고문" in original_name else 0)
            + (20 if original_name.lower().endswith(".hwp") else 0)
            + (10 if "공고" in original_name else 0)
        )
        candidates.append((score, server_file, original_name, dir_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1:]

def download_notice(link, destination):
    server_file, original_name, dir_id = link
    res = HTTP.post(
        DOWN_URL,
        params={
            "atchFileId": server_file,
            "orignlFileNm": original_name,
            "atchDirId": dir_id,
        },
        headers={"Referer": DETAIL_URL},
        timeout=60,
    )
    res.raise_for_status()
    if len(res.content) < 1000 or b"<html" in res.content[:500].lower():
        raise RuntimeError("HWP 대신 오류 응답 수신 (%d bytes)" % len(res.content))
    destination.write_bytes(res.content)

def hwp_to_text(hwp_path, work_dir):
    hwp5txt = shutil.which("hwp5txt")
    if hwp5txt:
        proc = subprocess.run(
            [hwp5txt, str(hwp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
        )
        if proc.returncode == 0:
            return proc.stdout.decode("utf-8", errors="replace")
    office = shutil.which("libreoffice") or shutil.which("soffice")
    if office:
        proc = subprocess.run(
            [
                office, "--headless", "--convert-to", "txt:Text",
                "--outdir", str(work_dir), str(hwp_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        txt_path = work_dir / (hwp_path.stem + ".txt")
        if proc.returncode == 0 and txt_path.exists():
            return txt_path.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError("HWP 본문 변환 도구가 없습니다(hwp5txt/libreoffice)")

REGION_NAMES = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시",
    "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
    "경기도", "강원특별자치도", "충청북도", "충청남도",
    "전북특별자치도", "전라남도", "경상북도", "경상남도",
    "제주특별자치도",
]

def extract_joint_info(text):
    clean = re.sub(r"\s+", " ", text or "")
    anchors = list(re.finditer(r"지역의무(?:공동계약|공동도급)|공동도급", clean))
    regions = []
    rate = ""
    for anchor in anchors:
        area = clean[max(0, anchor.start() - 500):anchor.end() + 1000]
        for region in REGION_NAMES:
            if region in area and region not in regions:
                regions.append(region)
        rates = re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(?:이상)?", area)
        if rates:
            nums = [float(x) for x in rates]
            preferred = [x for x in nums if 10 <= x <= 60]
            rate = "%g%% 이상" % (preferred[0] if preferred else nums[0])
        if regions and rate:
            break
    return ", ".join(regions), rate

def enrich_joint_info(row):
    payload = row.pop("_상세인자", None)
    row["공동도급지역"] = ""
    row["공동도급비율"] = ""
    row["공고문파일명"] = ""
    row["공동도급분석상태"] = "상세인자없음"
    if not payload:
        return row
    try:
        detail = HTTP.post(
            DETAIL_URL, data=payload,
            headers={"Referer": BASE_URL}, timeout=30,
        )
        detail.raise_for_status()
        detail.encoding = detail.apparent_encoding or "utf-8"
        link = choose_notice_link(detail.text)
        if not link:
            row["공동도급분석상태"] = "입찰공고문없음"
            return row
        row["공고문파일명"] = link[1]
        with tempfile.TemporaryDirectory(prefix="bid_nr_") as tmp:
            work_dir = Path(tmp)
            hwp_path = work_dir / "notice.hwp"
            download_notice(link, hwp_path)
            text = hwp_to_text(hwp_path, work_dir)
        region, rate = extract_joint_info(text)
        row["공동도급지역"] = region
        row["공동도급비율"] = rate
        row["공동도급분석상태"] = "추출완료" if (region or rate) else "해당없음"
    except Exception as e:
        row["공동도급분석상태"] = "분석실패: %s" % e
        log("[JOINT][ERROR] %s %s" % (row.get("공고번호"), e))
    return row
def fetch_page(page):
    params = {
        "menuNo": "14000",
        "pageIndex": str(page),
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://ebid.kr.or.kr/",
    }
    r = HTTP.get(BASE_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text
def parse_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    detail_calls = parse_detail_calls(html)
    # 줄 단위가 아니라 전체 텍스트에서 공고 패턴을 찾는다.
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    rows = []
    status_words = (
        "공고게시|변경공고|재공고|취소공고|개찰완료|투찰완료|"
        "유찰|낙찰|무효공고|개찰"
    )
    pat = re.compile(
        r"(공사|용역|구매|물품)\s+"
        r"(\d{4}-\d{2}-\d{6}-\d{2})\s+"
        r"(.+?)\s+"
        r"([\d,]+)\s+"
        r"(\d{4}-\d{2}-\d{2})\s+"
        r"(\d{4}-\d{2}-\d{2})\s+"
        r"(" + status_words + r")"
    )
    for m in pat.finditer(text):
        kind, bid_no, title, amount, post_dt, open_dt, status = m.groups()
        item = {
            "기관구분": "국가철도공단",
            "공고구분": kind,
            "공고번호": bid_no,
            "공고명": title.strip(),
            "설계금액": norm_money(amount),
            "설계금액표시": amount,
            "공고게시일": post_dt,
            "개찰예정일": open_dt,
            "처리상태": status.strip(),
            "상세URL": BASE_URL + "?menuNo=14000",
            "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if bid_no in detail_calls:
            item["_상세인자"] = detail_calls[bid_no]
        rows.append(item)
    return rows
def collect_all(max_pages=30):
    all_rows = []
    seen = set()
    for page in range(1, max_pages + 1):
        html = fetch_page(page)
        rows = parse_rows(html)
        log("[COLLECT] page=%d rows=%d" % (page, len(rows)))
        if not rows:
            break
        new_count = 0
        for r in rows:
            key = r["공고번호"]
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(r)
            new_count += 1
        if new_count == 0:
            break
        time.sleep(0.3)
    return all_rows
def classify_keyword(title):
    hits = [k for k in KEYWORDS if k in str(title)]
    return ",".join(hits)
def main():
    no_send = "--no-send" in sys.argv
    log("[MAIN] === bid-nr START ===")
    log("[CONF] NAS_BASE=%s no_send=%s" % (NAS_BASE, no_send))
    rows = collect_all()
    log("[MERGE] raw rows=%d" % len(rows))
    ts = datetime.now().strftime("%Y%m%d%H%M")
    if rows:
        raw_path = RAW_DIR / ("국가철도공단_전체공고_%s.xlsx" % ts)
        pd.DataFrame(rows).to_excel(raw_path, index=False)
        log("[SAVE] raw %s rows=%d" % (raw_path, len(rows)))
    targets = []
    for r in rows:
        hit = classify_keyword(r["공고명"])
        if not hit:
            continue
        rr = dict(r)
        rr["매칭키워드"] = hit
        rr["발송키"] = "NR:%s" % rr["공고번호"]
        targets.append(rr)
    log("[FILTER] target rows=%d keywords=%s" % (len(targets), ",".join(KEYWORDS)))
    for index, row in enumerate(targets, 1):
        log("[JOINT] analyze %d/%d %s" % (index, len(targets), row["공고번호"]))
        enrich_joint_info(row)
    if targets:
        target_path = REPORT_DIR / ("국가철도공단_소방기계설비_%s.xlsx" % ts)
        pd.DataFrame(targets).to_excel(target_path, index=False)
        log("[SAVE] target %s rows=%d" % (target_path, len(targets)))
    sent = load_sent_keys()
    send_targets = []
    for r in targets:
        key = r["발송키"]
        if key in sent:
            log("[SEND][SKIP_ALREADY] %s %s" % (key, r["공고명"]))
            continue
        send_targets.append(r)
    log("[SEND] new target rows=%d no_send=%s" % (len(send_targets), no_send))
    for r in send_targets:
        ok_all = True
        for phone in RECEIVERS:
            ok = send_kakao_one(phone, r, no_send=no_send)
            if not ok:
                ok_all = False
        if ok_all and not no_send:
            append_sent_key(r["발송키"])
    log("[MAIN] === bid-nr END ===")
if __name__ == "__main__":
    main()
