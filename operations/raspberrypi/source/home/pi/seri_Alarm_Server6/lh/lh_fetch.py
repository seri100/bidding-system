
# -*- coding: utf-8 -*-

import time
import re
import traceback
import requests
from bs4 import BeautifulSoup
from lh_notice_doc import extract_notice_attachment

# ▼ 추가: SSL 인증서 검증 끌 때 경고를 무시하기 위한 설정
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

LH_LIST_URL = "https://ebid.lh.or.kr/ebid.et.tp.cmd.BidMasterListCmd.dev"
LH_DETAIL_URL = "https://ebid.lh.or.kr/ebid.et.tp.cmd.BidConstructDetailListCmd.dev"



def _lh_clean_text(x):

    return re.sub(r"\s+", " ", x or "").strip()





def _extract_required_licenses_from_soup(soup):

    """

    LH 상세화면의 '요구면허' 테이블에서 면허명을 추출한다.

    예: 산업·환경설비공사업 / 기계설비·가스공사업

    """

    found = []



    # 요구면허 테이블이 별도 header 구조일 수 있으므로 table 단위로 탐색

    for tb in soup.select("table"):

        tb_text = _lh_clean_text(tb.get_text(" "))

        if "요구면허" not in tb_text and not any(k in tb_text for k in ["기계설비", "가스공사업", "소방시설공사"]):

            continue



        for cell in tb.find_all(["th", "td"]):

            txt = _lh_clean_text(cell.get_text(" "))

            if not txt:

                continue



            # 헤더/불필요어 제외

            if txt in ["요구면허", "업종", "업종유형", "번호", "순번"]:

                continue



            # 실제 면허명으로 볼 수 있는 키워드

            if (

                "공사업" in txt

                or "소방시설공사" in txt

                or "기계설비" in txt

                or "가스공사" in txt

                or "산업·환경설비" in txt

                or "산업환경설비" in txt

            ):

                # 한 셀에 여러 항목이 붙어 있을 수 있어 너무 긴 안내문은 제외

                # __LH_LICENSE_ATTACHMENT_FILTER_V1__
                lower_txt = txt.lower()
                is_attachment = any(ext in lower_txt for ext in (
                    '.hwp', '.hwpx', '.xls', '.xlsx', '.pdf', '.zip',
                    '.doc', '.docx', '.ppt', '.pptx', '.txt',
                ))
                has_attachment_word = any(word in txt for word in (
                    '현장설명서', '단가산출서', '입찰공고문',
                    '첨부파일', '다운로드',
                ))
                if (
                    len(txt) <= 80
                    and not is_attachment
                    and not has_attachment_word
                ):
                    found.append(txt)



    # 중복 제거

    out = []

    seen = set()

    for x in found:

        x = x.strip()

        if not x or x in seen:

            continue

        seen.add(x)

        out.append(x)



    return out








class LHCrawler:
    """
    LH 목록 및 상세 공고 크롤러
    """

    def __init__(self):
        self.session = requests.Session()
        # ▼ 이 세션에서는 SSL 인증서 검증을 하지 않음 (LH 전용)
        self.session.verify = False
        # 선택사항: User-Agent를 명시적으로 넣어주면 서버가 더 안정적으로 응답하는 경우가 있음
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) LHCrawler/1.0"
        })




    def get_page_count(self, start_date, end_date):

        """

        첫 페이지를 불러 페이지 수 파악

        """

        payload = {

            "s_bidNum": "",

            "s_cstrtnJobGbCd": 10,

            "s_bidnm": "",

            "s_tndrdocAcptOpenDtm": start_date,

            "s_tndrdocAcptEndDtm": end_date,

        }

        resp = self.session.post(

            LH_LIST_URL,

            data=payload,

            timeout=(10, 30),

        )

        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")



        lis = soup.select("ul > li")

        for li in lis:

            if "페이지" in li.get_text():

                txt = li.get_text().split("/")

                max_page = txt[1].replace(")", "").replace("페이지", "").strip()

                return int(max_page)



        return 1



    def fetch_list_page(self, page_no, start_date, end_date):

        """

        페이지 번호(page_no)의 목록 HTML 테이블을 가져옴

        """

        payload = {

            "s_bidProgrsStatus": "",

            "s_bidNum": "",

            "s_bidnm": "",

            "selectednum": "",

            "pageSpec": "default",

            "s_cstrtnJobGbCd": "10",

            "s_tndrdocAcptOpenDtm": start_date,

            "s_tndrdocAcptEndDtm": end_date,

            "targetRow": ((page_no - 1) * 10) + 1,

        }



        resp = self.session.post(

            LH_LIST_URL,

            data=payload,

            timeout=(10, 30),

        )

        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")



        tables = soup.select("table")

        if len(tables) < 2:

            return []



        trs = tables[1].select("tbody > tr")

        out = []



        for tr in trs:

            try:

                onclick = tr["onclick"]

                onclick = re.sub(r"[()'\";\s]", "", onclick.replace("fn_dds_open", ""))

                vals = onclick.split(",")



                if len(vals) >= 4:

                    out.append({

                        "notice_no": vals[0],

                        "degree": vals[1],

                        "job_gb": vals[2],

                        "emergency": vals[3],

                    })

            except Exception:

                continue



        return out



    def fetch_detail(self, notice):

        """

        상세 공고 페이지 파싱

        """

        detail_payload = {

            "bidNum": notice["notice_no"],

            "bidDegree": notice["degree"],

            "cstrtnJobGbCd": notice["job_gb"],

            "emrgncyOrder": notice["emergency"],

        }



        resp = self.session.post(

            LH_DETAIL_URL,

            data=detail_payload,

            timeout=(10, 30),

        )

        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        tables = soup.select("table")



        if len(tables) == 0:

            return None



        detail = {}



        for tb in tables:

            try:

                trs = tb.select("tbody > tr")

                for tr in trs:

                    ths = tr.select("th > label")

                    tds = tr.select("td")

                    for (th, td) in zip(ths, tds):

                        key = th.get_text().strip()

                        val = re.sub(r"\s+", " ", td.get_text()).strip()

                        detail[key] = val



            except Exception:

                traceback.print_exc()





        # __LH_REGION_SECTION_SPLIT_V1_BEGIN__

        # 같은 이름의 '참가지역1~4'가 두 표에 있으므로

        # table summary를 기준으로 지역제한과 지역의무를 분리한다.

        region_table_specs = (

            ("투찰제한정보", "지역제한"),

            ("지역의무공동업체제한", "지역의무"),

        )



        for table_summary, output_prefix in region_table_specs:

            region_table = soup.find(

                "table",

                attrs={"summary": table_summary},

            )



            values = []



            if region_table is not None:

                for tr in region_table.select("tbody > tr"):

                    ths = tr.select("th > label")

                    tds = tr.select("td")



                    for th, td in zip(ths, tds):

                        source_key = th.get_text().strip()



                        if not source_key.startswith("참가지역"):

                            continue



                        suffix = source_key.replace(

                            "참가지역",

                            "",

                            1,

                        )



                        value = re.sub(

                            r"\s+",

                            " ",

                            td.get_text(),

                        ).strip()



                        detail[

                            "{}{}".format(

                                output_prefix,

                                suffix,

                            )

                        ] = value



                        if value and value not in values:

                            values.append(value)



            # 항상 1~4 키를 만들어 공란도 명확히 보존한다.

            for region_no in range(1, 5):

                detail.setdefault(

                    "{}{}".format(

                        output_prefix,

                        region_no,

                    ),

                    "",

                )



            detail[output_prefix] = ", ".join(values)



        # 기존 코드와의 호환을 위한 통합 지역값

        combined_regions = []



        for prefix in ("지역제한", "지역의무"):

            for region_no in range(1, 5):

                value = str(

                    detail.get(

                        "{}{}".format(prefix, region_no)

                    )

                    or ""

                ).strip()



                if value and value not in combined_regions:

                    combined_regions.append(value)



        detail["참가지역"] = ", ".join(combined_regions)

        # __LH_REGION_SECTION_SPLIT_V1_END__



        # __REDACTED_PRIVATE_VALUE_ATTACHMENT_V1_BEGIN__

        try:

            detail.update(

                extract_notice_attachment(soup)

            )

        except Exception:

            traceback.print_exc()

            detail["공고문 추출상태"] = "첨부정보 분석 실패"

        # __REDACTED_PRIVATE_VALUE_ATTACHMENT_V1_END__



        # 공고번호 보정

        detail.setdefault("공고번호", notice["notice_no"])





        # 요구면허 별도 추출

        try:

            req_licenses = _extract_required_licenses_from_soup(soup)

            if req_licenses:

                detail["요구면허"] = " / ".join(req_licenses)

                for i, v in enumerate(req_licenses[:10], 1):

                    detail["요구면허{}".format(i)] = v

        except Exception:

            traceback.print_exc()



        return detail

