
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
ATTACH_DIR = NAS_BASE / "attachments"
LOG_DIR = BASE_DIR / "logs"
for d in [RAW_DIR, REPORT_DIR, STATE_DIR, ATTACH_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)
SENT_KEYS = STATE_DIR / "sent_keys.txt"
LOG_FILE = LOG_DIR / ("run_%s.log" % datetime.now().strftime("%Y%m%d"))
BASE_URL = "https://ebid.kr.or.kr/bid/anc/bidAncList.do"
DETAIL_URL = "https://ebid.kr.or.kr/bid/anc/bidAncDetail.do"
DOWN_URL = "https://ebid.kr.or.kr/common/FileDown.do"
KEYWORDS = ["전기공사", "소방시설", "소방설비", "기계설비"]
NATIONWIDE_AMOUNT = 1_000_000_000
RECEIVER_BY_REGION = {
    "전국": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],
    "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],
    "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],
    "대구": ["REDACTED_PRIVATE_VALUE"],
    "경북": ["REDACTED_PRIVATE_VALUE"],
}
ELECTRIC_NATIONWIDE_RECEIVERS = ["REDACTED_PRIVATE_VALUE"]
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

        ok = bool(res.get("ok")) if isinstance(res, dict) else bool(res)



        if not ok:

            log("[SEND][FAIL] %s %s result=%s" % (

                phone, row["공고번호"], res

            ))

            return False



        log("[SEND][OK] %s %s result=%s" % (

            phone, row["공고번호"], res

        ))

        return True



    except TypeError:

        # 혹시 서버 코드가 구형 인자순서이면 fallback

        res = kakao_send_for_item(fields, phone, dry_run=False)

        ok = bool(res.get("ok")) if isinstance(res, dict) else bool(res)



        if not ok:

            log("[SEND][FAIL][FALLBACK] %s %s result=%s" % (

                phone, row["공고번호"], res

            ))

            return False



        log("[SEND][OK][FALLBACK] %s %s result=%s" % (

            phone, row["공고번호"], res

        ))

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


def recipient_sent_key(row, phone):
    return "%s:%s" % (row["발송키"], phone)


def classify_trade_codes(text, title=""):
    clean = re.sub(r"\s+", "", "%s %s" % (text or "", title or ""))
    codes = []
    patterns = [
        ("0037", r"전기공사업"),
        ("0038", r"(?:일반소방시설공사업.{0,30}기계|소방기계)"),
        ("0039", r"(?:일반소방시설공사업.{0,30}전기|소방전기)"),
        ("0040", r"전문소방시설공사업"),
        ("6202", r"(?:기계가스설비공사업|기계설비공사업)"),
    ]
    for code, pattern in patterns:
        if re.search(pattern, clean):
            codes.append(code)

    if not codes:
        if "전기공사" in clean:
            codes.append("0037")
        if "소방시설" in clean or "소방설비" in clean:
            codes.append("0040")
        if "기계설비" in clean:
            codes.append("6202")
    return codes


def extract_participation_region(text):
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""

    clauses = []
    for marker in ("입찰참가자격", "입찰 참가자격", "지역제한"):
        start = clean.find(marker)
        if start >= 0:
            clauses.append(clean[start:start + 2500])
    search_text = " ".join(clauses) if clauses else clean

    region_aliases = [
        ("세종", ("세종특별자치시", "세종시")),
        ("충북", ("충청북도", "충북")),
        ("대구", ("대구광역시", "대구시")),
        ("경북", ("경상북도", "경북")),
    ]
    restriction_words = (
        "본점", "주된 영업소", "법인등기부", "사업자등록증",
        "지역제한", "소재한 업체", "소재하여야",
    )
    for canonical, aliases in region_aliases:
        for alias in aliases:
            for match in re.finditer(re.escape(alias), search_text):
                around = search_text[
                    max(0, match.start() - 350):match.end() + 350
                ]
                if any(word in around for word in restriction_words):
                    return canonical
    return "전국"


def select_receivers(row):
    codes = set(row.get("공종코드목록") or [])
    region = row.get("발송지역", "")
    if codes == {"0037"}:
        return (
            list(ELECTRIC_NATIONWIDE_RECEIVERS)
            if region == "전국"
            else []
        )
    if codes.intersection({"0038", "0039", "0040", "6202"}):
        return list(RECEIVER_BY_REGION.get(region, []))
    return []
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

def parse_attachment_links(detail_html):
    """상세화면의 download(...) 링크를 화면 순서대로 모두 추출한다."""
    result = []
    seen = set()
    soup = BeautifulSoup(detail_html, "html.parser")
    for link in soup.find_all(["a", "button"]):
        code = "%s %s" % (link.get("href", ""), link.get("onclick", ""))
        m = re.search(r"\bdownload\s*\((.*?)\)", code, re.I | re.S)
        if not m:
            continue
        args = re.findall(r"""['"]([^'"]*)['"]""", m.group(1))
        if len(args) < 3:
            continue
        server_file, original_name, dir_id = args[:3]
        key = (server_file, original_name, dir_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def choose_notice_link(detail_html):
    candidates = []
    for server_file, original_name, dir_id in parse_attachment_links(detail_html):
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


def download_attachment(link, destination, strict=False):
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
    head = res.content[:1000].lower().lstrip()
    content_type = str(res.headers.get("Content-Type", "")).lower()
    if not res.content:
        raise RuntimeError("빈 파일 응답")
    if b"<html" in head or b"<!doctype html" in head or "text/html" in content_type:
        raise RuntimeError("첨부파일 대신 HTML 오류 응답 수신 (%d bytes)" % len(res.content))
    if strict and len(res.content) < 1000:
        raise RuntimeError("공고문 파일 크기 비정상 (%d bytes)" % len(res.content))

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(destination.name + ".part")
    temp_path.write_bytes(res.content)
    os.replace(str(temp_path), str(destination))


def download_notice(link, destination):
    download_attachment(link, destination, strict=True)


def safe_path_name(value, fallback="file"):
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", str(value or "")).strip()
    value = value.rstrip(". ")
    return value[:180] or fallback


def save_all_attachments(row, detail_html):
    """대상 공고의 모든 첨부를 NAS 공고번호 폴더에 저장한다."""
    links = parse_attachment_links(detail_html)
    bid_no = safe_path_name(row.get("공고번호"), "unknown")
    notice_dir = ATTACH_DIR / bid_no
    saved = []
    failed = []
    used_names = set()

    for index, link in enumerate(links, 1):
        original_name = link[1]
        filename = safe_path_name(original_name, "attachment_%02d" % index)
        stem, suffix = os.path.splitext(filename)
        candidate = filename
        serial = 2
        while candidate.lower() in used_names:
            candidate = "%s_%d%s" % (stem, serial, suffix)
            serial += 1
        used_names.add(candidate.lower())
        destination = notice_dir / candidate

        try:
            if destination.exists() and destination.stat().st_size > 0:
                saved.append(candidate)
                log("[ATTACH][SKIP_EXISTS] %s %s" % (row.get("공고번호"), candidate))
                continue
            download_attachment(link, destination)
            saved.append(candidate)
            log("[ATTACH][OK] %s %s bytes=%d" % (
                row.get("공고번호"), candidate, destination.stat().st_size
            ))
        except Exception as e:
            failed.append("%s: %s" % (candidate, e))
            log("[ATTACH][FAIL] %s %s error=%s" % (
                row.get("공고번호"), candidate, e
            ))

    row["첨부파일수"] = len(links)
    row["첨부저장수"] = len(saved)
    row["첨부목록"] = " | ".join(saved)
    row["첨부저장경로"] = str(notice_dir) if links else ""
    row["첨부실패내용"] = " | ".join(failed)
    if not links:
        row["첨부상태"] = "첨부없음"
    elif failed and saved:
        row["첨부상태"] = "일부실패 %d" % len(failed)
    elif failed:
        row["첨부상태"] = "전체실패 %d" % len(failed)
    else:
        row["첨부상태"] = "완료"

def hwp_to_text(hwp_path, work_dir):


    # PDF_PDFFTEXT_FIX_20260812

    # PDF는 LibreOffice 대신 pdftotext로 직접 변환한다.

    if hwp_path.suffix.lower() == ".pdf":

        txt_path = work_dir / (hwp_path.stem + ".txt")



        try:

            proc = subprocess.run(

                [

                    "/usr/bin/pdftotext",

                    "-layout",

                    str(hwp_path),

                    str(txt_path),

                ],

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                timeout=60,

            )

        except subprocess.TimeoutExpired:

            raise RuntimeError("pdftotext 변환 시간 초과(60초)")

        except Exception as e:

            raise RuntimeError("pdftotext 실행오류: %s" % e)



        if proc.returncode != 0:

            raise RuntimeError(

                "pdftotext 실패(rc=%s): %s"

                % (

                    proc.returncode,

                    proc.stderr.decode(

                        "utf-8",

                        errors="replace",

                    )[:300],

                )

            )



        if not txt_path.exists():

            raise RuntimeError("pdftotext 결과 파일이 생성되지 않음")



        extracted = txt_path.read_text(

            encoding="utf-8",

            errors="replace",

        )



        if not extracted.strip():

            raise RuntimeError("pdftotext 결과가 비어 있음")



        replacement_count = extracted.count("\ufffd")

        if replacement_count > max(10, len(extracted) // 100):

            raise RuntimeError(

                "pdftotext 결과 문자깨짐 감지: replacement=%d"

                % replacement_count

            )



        return extracted



    candidates = [

        "/home/pi/.local/bin/hwp5txt",

        shutil.which("hwp5txt"),

        "/usr/local/bin/hwp5txt",

        "/usr/bin/hwp5txt",

    ]



    errors = []



    for executable in candidates:

        if not executable:

            continue



        executable = str(executable)

        if not os.path.isfile(executable) or not os.access(executable, os.X_OK):

            continue



        try:

            proc = subprocess.run(

                [executable, str(hwp_path)],

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                timeout=90,

            )

        except Exception as e:

            errors.append("hwp5txt 실행오류(%s): %s" % (executable, e))

            continue



        stderr = proc.stderr.decode("utf-8", errors="replace").strip()



        if proc.returncode != 0:

            errors.append(

                "hwp5txt 실패(%s, rc=%s): %s"

                % (executable, proc.returncode, stderr[:300])

            )

            continue



        extracted = proc.stdout.decode("utf-8", errors="replace")



        if not extracted.strip():

            errors.append("hwp5txt 결과가 비어 있음: %s" % executable)

            continue



        replacement_count = extracted.count("\ufffd")

        if replacement_count > max(10, len(extracted) // 100):

            errors.append(

                "hwp5txt 결과 문자깨짐 감지: replacement=%d"

                % replacement_count

            )

            continue



        return extracted



    office = shutil.which("libreoffice") or shutil.which("soffice")

    if office:

        txt_path = work_dir / (hwp_path.stem + ".txt")



        try:

            proc = subprocess.run(

                [

                    office,

                    "--headless",

                    "--convert-to",

                    "txt:Text",

                    "--outdir",

                    str(work_dir),

                    str(hwp_path),

                ],

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                timeout=120,

            )



            if proc.returncode == 0 and txt_path.exists():

                extracted = txt_path.read_text(

                    encoding="utf-8",

                    errors="replace",

                )



                replacement_count = extracted.count("\ufffd")

                if (

                    extracted.strip()

                    and replacement_count <= max(10, len(extracted) // 100)

                ):

                    return extracted



                errors.append(

                    "LibreOffice 결과가 비었거나 문자깨짐: replacement=%d"

                    % replacement_count

                )

            else:

                errors.append(

                    "LibreOffice 실패(rc=%s): %s"

                    % (

                        proc.returncode,

                        proc.stderr.decode(

                            "utf-8",

                            errors="replace",

                        )[:300],

                    )

                )

        except Exception as e:

            errors.append("LibreOffice 실행오류: %s" % e)



    if errors:

        raise RuntimeError("; ".join(errors))



    raise RuntimeError(

        "HWP 본문 변환 도구가 없습니다: "

        "/home/pi/.local/bin/hwp5txt 확인 필요"

    )





REGION_NAMES = [

    "서울특별시", "부산광역시", "대구광역시", "인천광역시",

    "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",

    "경기도", "강원특별자치도", "충청북도", "충청남도",

    "전북특별자치도", "전라남도", "경상북도", "경상남도",

    "제주특별자치도",

]





def _unique_regions(text):

    found = []



    for region in REGION_NAMES:

        if region in text and region not in found:

            found.append(region)



    return found

def extract_agreement_deadline(text):
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""

    patterns = [
        r"공동수급협정서\s*(?:등록|제출|접수)?\s*"
        r"(?:기한|마감(?:일시)?)\s*[:：]?\s*"
        r"(20\d{2})\s*[.년/-]\s*(\d{1,2})\s*[.월/-]\s*"
        r"(\d{1,2})\s*[.일]?\s*(?:\([^)]*\)\s*)?"
        r"(\d{1,2})\s*[:시]\s*(\d{2})",
        r"협정서\s*(?:등록|제출|접수)?\s*"
        r"(?:기한|마감(?:일시)?)\s*[:：]?\s*"
        r"(20\d{2})\s*[.년/-]\s*(\d{1,2})\s*[.월/-]\s*"
        r"(\d{1,2})\s*[.일]?\s*(?:\([^)]*\)\s*)?"
        r"(\d{1,2})\s*[:시]\s*(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean)
        if match:
            year, month, day, hour, minute = [
                int(value) for value in match.groups()
            ]
            try:
                value = datetime(year, month, day, hour, minute)
            except ValueError:
                continue
            return value.strftime("%Y-%m-%d %H:%M:%S")
    return ""






def extract_joint_info(text):

    clean = re.sub(r"\s+", " ", text or "").strip()



    result = {

        "region": "",

        "rate": "",

        "method": "",

        "member_min_rate": "",

    }



    if not clean:

        return result



    # 지역은 공사현장 문구가 아니라 지역의무 조항 주변에서만 찾는다.

    region_patterns = [

        r"지역의무\s*(?:공동계약|공동도급)\s*"

        r"\(([^)]{1,150})\)",

        r"지역의무\s*공동도급.{0,700}?"

        r"(?:공사현장을\s*관할하는|본점\s*소재지.{0,100}?)"

        r"(.{0,250}?)(?:에\s*법인등기부|에\s*본점|중\s*1인)",

        r"지역업체.{0,400}?"

        r"((?:서울특별시|부산광역시|대구광역시|인천광역시|"

        r"광주광역시|대전광역시|울산광역시|세종특별자치시|"

        r"경기도|강원특별자치도|충청북도|충청남도|"

        r"전북특별자치도|전라남도|경상북도|경상남도|"

        r"제주특별자치도).{0,150}?)"

        r"(?:에\s*법인등기부|에\s*본점|중\s*1인)",

    ]



    for pattern in region_patterns:

        match = re.search(pattern, clean)

        if not match:

            continue



        regions = _unique_regions(match.group(1))

        if regions:

            if " 또는 " in match.group(1):

                result["region"] = " 또는 ".join(regions)

            else:

                result["region"] = " 또는 ".join(regions)

            break



    # 지역업체 지분율을 우선 추출한다.

    rate_patterns = [

        r"지역업체(?:의)?\s*(?:합산\s*)?"

        r"(?:계약참여\s*)?지분율(?:은|이)?\s*"

        r"(\d+(?:\.\d+)?)\s*[%％]\s*이상",

        r"지역업체.{0,100}?"

        r"(\d+(?:\.\d+)?)\s*[%％]\s*이상",

    ]



    for pattern in rate_patterns:

        match = re.search(pattern, clean)

        if match:

            result["rate"] = "%g%% 이상" % float(match.group(1))

            break



    method_match = re.search(

        r"(공동이행방식|분담이행방식|주계약자관리방식)",

        clean,

    )

    if method_match:

        result["method"] = method_match.group(1)



    member_match = re.search(

        r"구성원별(?:\s*계약참여)?\s*"

        r"(?:최소)?지분율(?:은|이)?\s*"

        r"(\d+(?:\.\d+)?)\s*[%％]\s*이상",

        clean,

    )

    if member_match:

        result["member_min_rate"] = (

            "%g%% 이상" % float(member_match.group(1))

        )



    return result





def enrich_joint_info(row):

    payload = row.pop("_상세인자", None)



    row["공동도급지역"] = ""

    row["공동도급비율"] = ""

    row["공동도급방식"] = ""

    row["구성원별최소지분율"] = ""
    row["협정마감일시"] = ""
    row["협정마감출처"] = ""
    row["협정마감확인상태"] = "상세인자없음"

    row["공고문파일명"] = ""
    row["첨부파일수"] = 0
    row["첨부저장수"] = 0
    row["첨부목록"] = ""
    row["첨부저장경로"] = ""
    row["첨부상태"] = "상세인자없음"
    row["첨부실패내용"] = ""

    row["공동도급분석상태"] = "상세인자없음"
    row["공종코드"] = ""
    row["공종코드목록"] = classify_trade_codes("", row.get("공고명", ""))
    row["참가지역"] = ""
    row["발송지역"] = (
        "전국"
        if norm_money(row.get("설계금액")) >= NATIONWIDE_AMOUNT
        else ""
    )



    if not payload:

        return row



    try:

        detail = HTTP.post(

            DETAIL_URL,

            data=payload,

            headers={"Referer": BASE_URL},

            timeout=30,

        )

        detail.raise_for_status()

        detail.encoding = detail.apparent_encoding or "utf-8"

        save_all_attachments(row, detail.text)

        link = choose_notice_link(detail.text)

        if not link:

            row["공동도급분석상태"] = "입찰공고문없음"
            row["협정마감확인상태"] = "입찰공고문없음"

            return row



        row["공고문파일명"] = link[1]



        suffix = Path(link[1]).suffix.lower() or ".hwp"



        with tempfile.TemporaryDirectory(prefix="bid_nr_") as tmp:

            work_dir = Path(tmp)

            notice_path = work_dir / ("notice" + suffix)



            download_notice(link, notice_path)

            text = hwp_to_text(notice_path, work_dir)



        info = extract_joint_info(text)
        agreement_deadline = extract_agreement_deadline(text)
        codes = classify_trade_codes(text, row.get("공고명", ""))
        participation_region = extract_participation_region(text)

        row["공종코드목록"] = codes
        row["공종코드"] = ",".join(codes)
        row["참가지역"] = participation_region
        row["발송지역"] = (
            "전국"
            if norm_money(row.get("설계금액")) >= NATIONWIDE_AMOUNT
            else participation_region
        )



        row["공동도급지역"] = info["region"]

        row["공동도급비율"] = info["rate"]

        row["공동도급방식"] = info["method"]

        row["구성원별최소지분율"] = info["member_min_rate"]
        row["협정마감일시"] = agreement_deadline
        if agreement_deadline:
            row["협정마감출처"] = "공식 공고문: %s" % row["공고문파일명"]
            row["협정마감확인상태"] = "공식공고문확인"
        else:
            row["협정마감확인상태"] = "공식공고문에명시없음"




        has_joint_clause = bool(

            re.search(

                r"지역의무\s*(?:공동계약|공동도급)|"

                r"공동도급에\s*관한\s*사항",

                re.sub(r"\s+", " ", text),

            )

        )



        if info["region"] or info["rate"] or info["method"]:

            row["공동도급분석상태"] = "추출완료"

        elif has_joint_clause:

            row["공동도급분석상태"] = "공동도급문구있음-조건미추출"

        else:

            row["공동도급분석상태"] = "해당없음"



    except Exception as e:

        row["공동도급분석상태"] = "분석실패: %s" % e
        row["협정마감확인상태"] = "분석실패: %s" % e

        log("[JOINT][ERROR] %s %s" % (row.get("공고번호"), e))



    row["공종코드"] = ",".join(row.get("공종코드목록") or [])
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

    rows = []



    # 각 HTML 표 행 안에서만 공고정보를 추출한다.

    # 페이지 전체 텍스트를 검색하면 서로 다른 공고가 합쳐질 수 있다.

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



    for tr in soup.find_all("tr"):

        row_text = tr.get_text(" ", strip=True)

        row_text = re.sub(r"\s+", " ", row_text)

        if not row_text:

            continue



        match = pat.search(row_text)

        if not match:

            continue



        kind, bid_no, title, amount, post_dt, open_dt, status = (

            match.groups()

        )



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

            "수집일시": datetime.now().strftime(

                "%Y-%m-%d %H:%M:%S"

            ),

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
    pending_count = 0
    for r in targets:
        legacy_key = r["발송키"]
        if legacy_key in sent:
            log("[SEND][SKIP_LEGACY] %s %s" % (legacy_key, r["공고명"]))
            continue

        receivers = select_receivers(r)
        if not receivers:
            log(
                "[SEND][SKIP_ROUTE] %s codes=%s region=%s title=%s"
                % (
                    r["공고번호"],
                    r.get("공종코드") or "미확인",
                    r.get("발송지역") or "미확인",
                    r["공고명"],
                )
            )
            continue

        log(
            "[SEND][ROUTE] %s codes=%s region=%s receivers=%s"
            % (
                r["공고번호"],
                r.get("공종코드"),
                r.get("발송지역"),
                ",".join(receivers),
            )
        )
        for phone in receivers:
            phone_key = recipient_sent_key(r, phone)
            if phone_key in sent:
                log("[SEND][SKIP_ALREADY] %s" % phone_key)
                continue

            pending_count += 1
            ok = send_kakao_one(phone, r, no_send=no_send)
            if ok and not no_send:
                append_sent_key(phone_key)
                sent.add(phone_key)

    log("[SEND] pending recipients=%d no_send=%s" % (pending_count, no_send))
    log("[MAIN] === bid-nr END ===")
if __name__ == "__main__":
    main()
