# -*- coding: utf-8 -*-



import hashlib

import io

import json

import re

import zipfile

from pathlib import Path



import requests

from bs4 import BeautifulSoup





DOWNLOAD_URL = "https://ebid.lh.or.kr/ebid.framework.download.dev"

CACHE_DIR = Path(__file__).resolve().parent / "state" / "lh_notice_cache"





def _clean(value):

    return re.sub(r"\s+", " ", value or "").strip()





def extract_notice_attachment(soup):
    """LH 상세 HTML에서 유형코드와 무관하게 모든 첨부정보를 추출한다."""
    result = {}
    attachments = []
    seen = set()

    for anchor in soup.select("a.attach"):
        href = anchor.get("href", "")
        match = re.search(
            r"fn_dds_open\("
            r"'([^']*)'\s*,\s*'([^']*)'\s*,\s*"
            r"'([^']*)'\s*,\s*'([^']*)'\s*\)",
            href,
        )
        if not match:
            continue
        file_type = match.group(1).strip()
        saved_name = match.group(2).strip()
        inner_path = match.group(3).strip()
        display_name = match.group(4).strip()
        identity = (saved_name, display_name)
        if not saved_name or identity in seen:
            continue
        seen.add(identity)
        attachments.append({
            "유형코드": file_type,
            "서버파일명": saved_name,
            "내부경로": inner_path,
            "표시파일명": display_name,
        })

    result["첨부파일목록"] = attachments
    if attachments:
        # 공고문(유형 10)을 기존 공고문 본문 분석 대상으로 유지한다.
        notice_item = next(
            (item for item in attachments if item.get("유형코드") == "10"),
            attachments[0],
        )
        result["공고문 서버파일명"] = notice_item["서버파일명"]
        result["공고문 내부경로"] = notice_item["내부경로"]
        result["공고문 표시파일명"] = notice_item["표시파일명"]
        result["공고문 추출상태"] = "첨부정보 확인"
    else:
        result["공고문 추출상태"] = "입찰공고문 첨부 없음"
    return result


def _extract_hwpx_text(data):

    if not zipfile.is_zipfile(io.BytesIO(data)):

        raise ValueError("다운로드 파일이 정상 HWPX가 아닙니다.")



    texts = []



    with zipfile.ZipFile(io.BytesIO(data)) as zf:

        names = sorted(

            name for name in zf.namelist()

            if name.startswith("Contents/section")

            and name.endswith(".xml")

        )



        if not names:

            raise ValueError("HWPX 본문 XML이 없습니다.")



        for name in names:

            soup = BeautifulSoup(zf.read(name), "xml")

            texts.append(soup.get_text(" ", strip=True))



    return _clean(" ".join(texts))





def _group(text, pattern, default=""):

    match = re.search(pattern, text, re.I | re.S)



    if not match:

        return default



    return _clean(match.group(1))





def _limited(value, maximum=30000):

    value = _clean(value)



    if len(value) <= maximum:

        return value



    return value[:maximum] + " …[이하 생략]"





def extract_notice_conditions(text):

    """공고문 본문에서 입찰 핵심조건을 구조화한다."""

    text = _clean(text)
    result = {}



    result["공고문 입찰방법"] = _limited(_group(

        text,

        r"\b\d+\.\s*입찰방법\s*:\s*(.*?)"

        r"(?=\s*\d+\.\s*낙찰자\s*결정방법)",

    ))



    result["공고문 입찰참가자격"] = _limited(_group(

        text,

        r"\b4\.\s*입찰참가자격\s*(.*?)"

        r"(?=\s*5\.\s*공동계약)",

    ), 20000)



    result["공고문 공동계약"] = _limited(_group(

        text,

        r"\b5\.\s*공동계약\s*(.*?)"

        r"(?=\s*6\.\s*)",

    ), 15000)



    # 공고에 명시된 금액만 사용한다. row의 다른 금액으로 대체하지 않는다.
    capacity = re.search(
        r"시공능력\s*평가액\s*이\s*(?:본|당해|해당)\s*공사\s*추정가격"
        r"\s*[（(]\s*([0-9][0-9,\s]*원)\s*[）)]\s*이상(?:인\s*자)?",
        text,
    )
    result["시공능력 참가요건"] = ""
    result["시공능력 제한 요약"] = ""
    result["시공능력 제한 상세"] = ""
    if capacity:
        amount = re.sub(r"\s+", "", capacity.group(1))
        result["시공능력 참가요건"] = amount
        result["시공능력 제한 요약"] = "시공능력평가액 {} 이상".format(amount)
        prefix = text[max(0, capacity.start() - 250):capacity.start()]
        basis = list(re.finditer(r"입찰공고일\s*기준", prefix))
        detail_start = max(0, capacity.start() - 250) + basis[-1].start() if basis else capacity.start()
        result["시공능력 제한 상세"] = _clean(text[detail_start:capacity.end()])

    result["지역업체 자격"] = _limited(_group(

        text,

        r"(법인등기부상\s*본점소재지.*?"

        r"90일\s*이상\s*경과한\s*자)",

    ), 3000)



    result["지역업체 최소지분율"] = _group(

        text,

        r"지역업체의\s*최소지분율은\s*"

        r"([0-9.]+\s*%\s*이상)",

    )



    result["공동계약 방식(공고문)"] = (

        "공동이행"

        if re.search(r"공동이행방식", text)

        else ""

    )



    result["구성원별 최소지분율"] = _group(

        text,

        r"구성원별\s*최소\s*지분율은\s*"

        r"([0-9.]+\s*%\s*이상)",

    )



    result["공동수급체 구성원 수"] = _group(

        text,

        r"대표자를\s*포함한\s*전체\s*공동수급체\s*"

        r"구성원\s*수는\s*([0-9]+\s*인\s*이내)",

    )



    result["공동수급체 대표자 요건"] = _group(

        text,

        r"공동수급체\s*대표자는\s*([^\.]+)",

    )



    result["시공능력 평가기준"] = _limited(_group(

        text,

        r"(공동수급체\s*각\s*구성원의\s*공사참여\s*"

        r"지분율에\s*추정금액을\s*곱한\s*금액이.*?"

        r"배분하여\s*평가하지\s*않습니다\.)",

    ), 4000)



    result["주된 공사"] = _group(

        text,

        r"시공비율\s*산정에\s*기준이\s*되는\s*"

        r"주된\s*공사는\s*([^,이며]+?)\s*이며",

    )



    result["주된 공사 추정금액"] = _group(

        text,

        r"주된\s*공사의\s*추정금액은\s*"

        r"([0-9,\s]+원)",

    )



    result["시공경험 평가기준"] = _limited(_group(

        text,

        r"(시공경험\s*평가는.*?"

        r"공사예정금액은\s*설계금액(?:의\s*값)?과\s*동일\s*합니다\.)",

    ), 4000)



    result["실적계수"] = _group(

        text,

        r"실적계수는\s*[“\"']?\s*(.*?)"

        r"\s*[”\"']?\s*(?:으로|로)\s*평가합니다",

    )



    result["공사실적 평가대상"] = _group(
        text, r"(공사실적금액은\s*.*?실적\s*으로\s*평가합니다\.)"
    )
    result["공고문 조건 버전"] = 2
    return result


def calendar_notice_condition_lines(row):
    """공고문에서 실제 확인된 조건만 캘린더에 표시한다."""
    fields = (
        ("입찰방법", "공고문 입찰방법"),
        ("시공능력 제한", "시공능력 제한 상세"),
        ("시공경험 평가기준", "시공경험 평가기준"),
        ("실적계수", "실적계수"),
        ("공사실적 평가대상", "공사실적 평가대상"),
    )
    return ["{} : {}".format(label, _clean(str(row[key])))
            for label, key in fields if row.get(key)]


def enrich_row_from_notice(row, session=None):

    """새 공고의 HWPX를 다운로드해 row에 핵심조건을 추가한다."""

    saved_name = str(row.get("공고문 서버파일명") or "").strip()

    display_name = str(row.get("공고문 표시파일명") or "").strip()



    if not saved_name:

        row["공고문 추출상태"] = (

            row.get("공고문 추출상태")

            or "입찰공고문 첨부 없음"

        )

        return row



    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha256(

        saved_name.encode("utf-8")

    ).hexdigest()

    cache_path = CACHE_DIR / (cache_key + ".json")



    if cache_path.exists():

        try:

            cached = json.loads(

                cache_path.read_text(encoding="utf-8")

            )

            if cached.get("공고문 조건 버전") != 2:
                raise ValueError("공고문 조건 캐시 갱신 필요")

            row.update(cached)

            row["공고문 추출상태"] = "정상(캐시)"

            return row

        except Exception:

            pass



    http = session or requests.Session()



    try:

        response = http.post(

            DOWNLOAD_URL,

            data={

                "download.filespec": "bidinfo",

                "download.filename": display_name.replace(" ", ""),

                "download.savedname": saved_name,

                "download.bidnum": "",

            },

            timeout=(10, 60),

        )

        response.raise_for_status()



        text = _extract_hwpx_text(response.content)

        extracted = extract_notice_conditions(text)

        extracted["공고문 추출상태"] = "정상(HWPX)"

        extracted["공고문 본문 글자수"] = len(text)



        row.update(extracted)



        cache_path.write_text(

            json.dumps(

                extracted,

                ensure_ascii=False,

                indent=2,

            ),

            encoding="utf-8",

        )



    except Exception as exc:

        row["공고문 추출상태"] = "실패: {}: {}".format(

            type(exc).__name__,

            exc,

        )



    return row

