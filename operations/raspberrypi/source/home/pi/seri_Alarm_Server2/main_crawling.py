
# -*- coding: utf-8 -*-
import os
import re
import time
import csv
import fcntl
import traceback
import datetime
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

import alligo

# ============================================================
# ✅ 실행 중복(겹침) 100% 차단: 프로세스 락
# ============================================================
def acquire_run_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("[LOCK] already running -> exit")
        raise SystemExit(0)
    return f  # 파일핸들 유지해야 락 유지됨

# ============================================================
# 기본 경로/설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

OUT_DIR = Path(os.getenv("LH_OUT_DIR", "REDACTED_PRIVATE_VALUE"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUN_LOCK = OUT_DIR / "_history" / ".lh_run.lock"
SAVE_CSV = OUT_DIR / "lh_notice.csv"

CA_BUNDLE = "/home/pi/seri_Alarm_Server2/certs/combined_ca_bundle.pem"

BASE_URL = "https://ebid.lh.or.kr/ebid.et.tp.cmd.BidMasterListCmd.dev"
DETAIL_URL = "https://ebid.lh.or.kr/ebid.et.tp.cmd.BidConstructDetailListCmd.dev"

# 테스트 모드(1이면 REDACTED_PRIVATE_VALUE 단독 발송)
TEST_MODE = os.getenv("TEST_MODE", "0").strip() == "1"
TEST_PHONE = "REDACTED_PRIVATE_VALUE"


def _now():
    return datetime.datetime.now()


def clean(x):
    if x is None:
        return ""
    x = str(x)
    x = x.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", x).strip()


# ============================================================
# ✅ 중복 발송 100% 차단용: 영구 히스토리 (복합키 + 즉시 append + 락)
# ============================================================

HISTORY_DIR = OUT_DIR / "_history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

SENT_HISTORY_CSV = HISTORY_DIR / "lh_sent_history.csv"
SENT_HISTORY_LOCK = HISTORY_DIR / ".lh_sent_history.lock"


def make_sent_key(bidNum: str, bidDegree: str, cstrtnJobGbCd: str, emrgncyOrder: str) -> str:
    return f"{(bidNum or '').strip()}|{(bidDegree or '').strip()}|{(cstrtnJobGbCd or '').strip()}|{(emrgncyOrder or '').strip()}"


def load_sent_history(path: Path) -> set:
    s = set()
    if not path.exists():
        return s
    try:
        with path.open("r", encoding="REDACTED_PRIVATE_VALUE", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                k = (row.get("sent_key") or "").strip()
                if k:
                    s.add(k)
    except Exception:
        pass
    return s


def append_sent_history(path: Path, lock_path: Path, sent_key: str,
                        bidNum: str, bidDegree: str, cstrtnJobGbCd: str, emrgncyOrder: str) -> None:
    """
    ✅ 발송 성공 직후 즉시 1줄 append (다음 타이머 실행 전에 반영)
    ✅ flock으로 동시 실행 경합 방지
    """
    with lock_path.open("a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)

        is_new = not path.exists()
        with path.open("a", encoding="REDACTED_PRIVATE_VALUE", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["ts", "sent_key", "bidNum", "bidDegree", "cstrtnJobGbCd", "emrgncyOrder"])
            w.writerow([_now().strftime("%Y-%m-%d %H:%M:%S"),
                        sent_key, bidNum, bidDegree, cstrtnJobGbCd, emrgncyOrder])

        fcntl.flock(lf, fcntl.LOCK_UN)


# ============================================================
# 알림톡 템플릿 (TZ_4492)
# ============================================================

TPL_CODE = "TZ_4492"
MSG_HEAD = "LH 입찰공고"
SENDER_PHONE = "REDACTED_PRIVATE_VALUE"

VAR_MAP = {
    "공고번호": "lhNo",
    "업종유형": "lhType",
    "입찰공고건명": "lhNm",
    "기초금액": "lhAmount",
    "참가지역": "lhLoc",
    "입찰서접수개시일시": "lhStartDate",
    "입찰서접수마감일시": "lhEndDate",
}

REMOVE_PHRASE = "본 공고는 지문인식 전자입찰제도가 적용되오니 사전에 조달청이 정한 절차에 따라 지문보안토큰에지문정보를 등록 하여야 합니다."


def sanitize_title(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = s.replace(REMOVE_PHRASE, "").strip()
    return s


# ============================================================
# 페이지/리스트/상세 파싱
# ============================================================

def find_max_page(soup: BeautifulSoup) -> int:
    for li in soup.select("ul > li"):
        t = clean(li.get_text())
        if "페이지" in t and "/" in t:
            try:
                right = t.split("/")[1]
                right = right.replace(")", "").replace("페이지", "").strip()
                return int(re.sub(r"[^0-9]", "", right))
            except Exception:
                pass
    return 1


def extract_list_rows(soup: BeautifulSoup):
    rows = []
    for tr in soup.select("tr[onclick]"):
        oc = tr.get("onclick", "")
        if "fn_dds_open" in oc:
            rows.append(tr)
    return rows


def parse_onclick(tr) -> list:
    oc = tr.get("onclick", "")
    oc = oc.replace("fn_dds_open", "")
    oc = oc.replace("(", "").replace(")", "").replace(";", "")
    oc = oc.replace("'", "").replace('"', "")
    oc = re.sub(r"\s+", "", oc)
    parts = oc.split(",")
    return parts[:4]  # [bidNum, bidDegree, cstrtnJobGbCd, emrgncyOrder]


def scrape_detail(detail_payload) -> dict:
    r = requests.post(DETAIL_URL, data=detail_payload, verify=CA_BUNDLE, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    detail = {}
    for tr in soup.select("table tbody tr"):
        ths = tr.select("th")
        tds = tr.select("td")
        if not ths or not tds:
            continue

        labels = tr.select("th label")
        if labels and len(labels) == len(tds):
            for lb, td in zip(labels, tds):
                k = clean(lb.get_text())
                v = clean(td.get_text())
                if k:
                    detail[k] = v
        else:
            for th, td in zip(ths, tds):
                k = clean(th.get_text())
                v = clean(td.get_text())
                if k:
                    detail[k] = v

    for k in VAR_MAP.keys():
        detail.setdefault(k, "")

    return detail


# ============================================================
# 세리공영 룰: 공종/지역 -> 수신자
# ============================================================

VALID_CODES = {"0037", "0038", "0039", "0040", "6202"}


def lh_ind_code(ind_text: str) -> str:
    t = (ind_text or "").strip()

    if "전기" in t and "공사" in t:
        return "0037"

    if "소방" in t:
        if "(기계" in t or "기계)" in t:
            return "0038"
        if "(전기" in t or "전기)" in t:
            return "0039"
        if "시설" in t and "공사" in t:
            return "0040"
        return "0040"

    if "기계설비" in t:
        return "6202"

    return ""


def lh_rep_region(loc_text: str) -> str:
    t = (loc_text or "").strip()
    if "세종" in t:
        return "세종"
    if "충북" in t or "충청북도" in t:
        return "충북"
    if "대구" in t:
        return "대구"
    if "경북" in t or "경상북도" in t:
        return "경북"
    return "전국"


def decide_receivers_by_rule(ind_code: str, rep_region: str) -> list:
    # ✅ 전기공사(0037)는 항상 REDACTED_PRIVATE_VALUE만
    if ind_code == "0037":
        return ["REDACTED_PRIVATE_VALUE"]

    # 사용자 요청 룰: 공종 0038/0039/0040/6202
    RULE_CODES = {"0038","0039","0040","6202"}

    R = {
        "전국": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],
        "세종": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],
        "충북": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],
        "대구": ["REDACTED_PRIVATE_VALUE"],
        "경북": ["REDACTED_PRIVATE_VALUE"],
    }

    if ind_code in RULE_CODES:
        return R.get(rep_region, R["전국"])

    return []

# ============================================================
# 알림톡 발송
# ============================================================

def send_alimtalk(alligo_obj, receivers, detail: dict) -> bool:
    # 토큰
    alligo_obj.getToken()

    regions = " / ".join(filter(None, [
        detail.get("참가지역1", ""),
        detail.get("참가지역2", ""),
        detail.get("참가지역3", ""),
        detail.get("참가지역4", ""),
        detail.get("참가지역", ""),
    ]))

    clean_title = sanitize_title(detail.get("입찰공고건명", ""))

    msg1 = (
        f"[세리공영]\n"
        f"LH 입찰공고\n"
        f"공고번호 : {clean(detail.get('공고번호',''))}\n"
        f"업종유형 : {clean(detail.get('업종유형',''))}\n"
        f"입찰공고건명 : {clean(clean_title)}\n"
        f"기초금액 : {clean(detail.get('기초금액',''))}\n"
        f"참가지역 : {clean(regions)}\n"
        f"입찰서접수개시일시 : {clean(detail.get('입찰서접수개시일시',''))}\n"
        f"입찰서접수마감일시 : {clean(detail.get('입찰서접수마감일시',''))}"
    )

    params = {
        "apikey": alligo_obj.apikey,
        "userid": alligo_obj.id,
        "token": alligo_obj.token,
        "senderkey": alligo_obj.kakaoSender,
        "tpl_code": TPL_CODE,
        "sender": SENDER_PHONE,
        "title": MSG_HEAD,
    }

    for i, rcv in enumerate(receivers, start=1):
        params[f"receiver_{i}"] = rcv
        params[f"message_{i}"] = msg1
        for src_key, var_name in VAR_MAP.items():
            params[f"variable_{i}_{var_name}"] = clean(detail.get(src_key, ""))

    resp = requests.post(alligo_obj.sendTalkUrl, data=params, timeout=30)
    print("[SEND] HTTP", resp.status_code)
    print("[SEND] RAW", resp.text[:500])

    try:
        j = resp.json()
        return (resp.status_code == 200) and (str(j.get("code")) == "0")
    except Exception:
        return (resp.status_code == 200)


# ============================================================
# Main
# ============================================================

class MainCrawling:
    def __init__(self):
        self.alligo = alligo.Alligo()

        # 수신자 로딩(기본: companys_copy.xlsx)
        from openpyxl import load_workbook
        wb = load_workbook(str(BASE_DIR / "companys_copy.xlsx"), data_only=True)
        ws = wb.active

        headers = [str(c).strip() if c is not None else ""
                   for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        idx = {h: i for i, h in enumerate(headers) if h}

        recv = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            for col in ["전화번호1", "전화번호2", "전화번호3"]:
                j = idx.get(col)
                if j is None:
                    continue
                v = clean(row[j] if row[j] is not None else "")
                if v and v not in recv:
                    recv.append(v)

        # FORCE_RECV 지원
        forced = os.getenv("FORCE_RECV", "").strip()
        if forced:
            forced_list = [x.strip() for x in forced.split(",") if x.strip()]
            if forced_list:
                recv = forced_list

        self.receivers = recv
        print("[BOOT] receivers =", self.receivers)

        # 히스토리 로딩
        self.ignore_history = os.getenv("IGNORE_HISTORY", "0").strip() == "1"
        if self.ignore_history:
            self.sent = set()
            print("[HISTORY] IGNORE_HISTORY=1")
        else:
            self.sent = load_sent_history(SENT_HISTORY_CSV)
            print(f"[HISTORY] loaded={len(self.sent)} from {SENT_HISTORY_CSV}")

    def run(self):
        start_date = _now().strftime("%Y/%m/%d")
        end_date = (_now() + relativedelta(months=5)).strftime("%Y/%m/%d")
        print(f"[RUN] start_date={start_date}, end_date={end_date}")

        base_payload = {
            "s_bidNum": "",
            "s_cstrtnJobGbCd": "10",
            "s_bidnm": "",
            "s_tndrdocAcptOpenDtm": start_date,
            "s_tndrdocAcptEndDtm": end_date,
            "s_tndrCtrctMedCd": "",
            "s_zoneHqCd": "",
            "s_designPrc": "",
            "s_zone": "",
            "s_bidProgrsStatus": "",
            "s_licenceNm": "",
            "s_licenceCd": "",
        }

        r0 = requests.post(BASE_URL, data=base_payload, verify=CA_BUNDLE, timeout=30)
        soup0 = BeautifulSoup(r0.text, "html.parser")
        max_page = find_max_page(soup0)
        print(f"[PAGE] max_page={max_page}")

        collected_rows = []
        sent_count = 0
        list_total = 0

        for page_idx in range(1, max_page + 1):
            payload = dict(base_payload)
            payload.update({
                "pageSpec": "default",
                "targetRow": str(page_idx),
                "devonOrderBy": "",
                "selectednum": "",
            })

            rp = requests.post(BASE_URL, data=payload, verify=CA_BUNDLE, timeout=30)
            soup = BeautifulSoup(rp.text, "html.parser")
            trs = extract_list_rows(soup)

            print(f"[PAGE] {page_idx}/{max_page}, rows={len(trs)}")

            for tr in trs:
                try:
                    parts = parse_onclick(tr)
                    if len(parts) < 4:
                        continue

                    bidNum, bidDegree, cstrtnJobGbCd, emrgncyOrder = parts[0], parts[1], parts[2], parts[3]
                    list_total += 1

                    sent_key = make_sent_key(bidNum, bidDegree, cstrtnJobGbCd, emrgncyOrder)

                    if (not self.ignore_history) and (sent_key in self.sent):
                        print(f"[SKIP][HISTORY] {sent_key}")
                        continue

                    detail_payload = {
                        "bidNum": bidNum,
                        "bidDegree": bidDegree,
                        "cstrtnJobGbCd": cstrtnJobGbCd,
                        "emrgncyOrder": emrgncyOrder,
                    }

                    detail = scrape_detail(detail_payload)
                    detail["공고번호"] = bidNum

                    # 제목 정제
                    if "입찰공고건명" in detail:
                        detail["입찰공고건명"] = sanitize_title(detail.get("입찰공고건명", ""))

                    # 저장용 row
                    row = {k: clean(detail.get(k, "")) for k in VAR_MAP.keys()}
                    collected_rows.append(row)

                    # 자동 엑셀 저장(누적)
                    ts = _now().strftime("%Y%m%d_%H%M%S")
                    xlsx = OUT_DIR / f"LH_{ts}.xlsx"
                    pd.DataFrame(collected_rows).to_excel(xlsx, index=False)
                    print("[LH][AUTO_SAVE] saved =>", xlsx)

                    # 발송 룰
                    ind_text = (detail.get("업종유형") or "").strip()
                    ind_code = lh_ind_code(ind_text)

                    loc_text = (detail.get("참가지역") or "").strip()
                    rep = lh_rep_region(loc_text)

                    if os.getenv("FORCE_RECV", "").strip():
                        final_receivers = self.receivers
                    else:
                        final_receivers = decide_receivers_by_rule(ind_code, rep)

                    if TEST_MODE:
                        final_receivers = [TEST_PHONE]
                        print(f"[TEST_MODE] force receiver => {final_receivers}")

                    if (not ind_code) or (ind_code not in VALID_CODES):
                        print(f"[SKIP][IND] ind_text={ind_text} -> ind_code={ind_code}")
                        continue

                    if not final_receivers:
                        print(f"[SKIP][RECV] ind_code={ind_code}, rep={rep}, loc={loc_text}")
                        continue

                    print(f"[RULE] ind_code={ind_code}, rep={rep}, recv={final_receivers}")

                    ok = send_alimtalk(self.alligo, final_receivers, detail)

                    if ok:
                        sent_count += 1
                        self.sent.add(sent_key)
                        append_sent_history(
                            SENT_HISTORY_CSV, SENT_HISTORY_LOCK,
                            sent_key, bidNum, bidDegree, cstrtnJobGbCd, emrgncyOrder
                        )
                    else:
                        print(f"[SEND][FAIL] {sent_key}")

                    time.sleep(1)

                except Exception:
                    print(traceback.format_exc())
                    continue

            time.sleep(1)

        # csv 저장(발송 여부와 무관)
        pd.DataFrame(collected_rows).to_csv(SAVE_CSV, index=False, encoding="REDACTED_PRIVATE_VALUE")
        print(f"[DONE] list_total={list_total}, sent_ok={sent_count}, saved_rows={len(collected_rows)}")
        print("[SAVE] csv =>", str(SAVE_CSV))
        print("[SAVE] history =>", str(SENT_HISTORY_CSV))


if __name__ == "__main__":
    _lock_fh = acquire_run_lock(RUN_LOCK)
    MainCrawling().run()



