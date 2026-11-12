
# -*- coding: utf-8 -*-

from __future__ import print_function



import math

import re

from datetime import datetime



from lh_fetch import LHCrawler as WebLHCrawler

from lh_gw_fetch import LHGatewayClient, api_item_to_detail, clean





class LHCrawler(WebLHCrawler):

    """

    GW API 목록 + 기존 LH 웹 상세정보 결합 수집기.



    1. 목록은 새 중앙형 GW API 사용

    2. 상세정보와 첨부파일은 기존 LH 웹페이지 사용

    3. 웹 상세조회 실패 시 GW API 자료로 대체

    """



    PAGE_SIZE = 10



    def __init__(self):

        WebLHCrawler.__init__(self)

        self.gw_client = LHGatewayClient()

        self._gw_notices = None

        self._gw_period = None

        self._gw_enabled = False



    def _load_gw_notices(self, start_date, end_date):

        period = (str(start_date), str(end_date))



        if self._gw_notices is not None and self._gw_period == period:

            return self._gw_notices



        start_digits = re.sub(r"[^0-9]", "", str(start_date))

        end_digits = re.sub(r"[^0-9]", "", str(end_date))

        today_digits = datetime.now().strftime("%Y%m%d")



        if len(start_digits) != 8:

            raise ValueError(

                "GW 시작일 형식 오류: {}".format(start_date)

            )



        if len(end_digits) != 8:

            raise ValueError(

                "GW 종료일 형식 오류: {}".format(end_date)

            )



        # GW는 공고등록일 기준이므로 미래 입찰일은 조회하지 않는다.

        query_end = min(end_digits, today_digits)



        if start_digits > query_end:

            start_digits = query_end



        raw_rows = self.gw_client.fetch_all(

            start_digits,

            query_end,

            num_rows=100,

        )



        notices = []

        for item in raw_rows:

            job_name = clean(item.get("cstrtnJobGbNm"))



            # 기존 수집기도 시설공사 코드 10만 조회했으므로 동일하게 제한

            if "시설공사" not in job_name:

                continue



            notices.append({

                "notice_no": clean(item.get("bidNum")),

                "degree": clean(item.get("bidDegree")) or "00",

                "job_gb": "10",

                "emergency": "",

                "_gw_item": item,

            })



        # API 정상 응답에도 웹 목록을 조회하여 누락 공고를 보완한다.
        merged = {}
        for notice in notices:
            key = (clean(notice.get("notice_no")), clean(notice.get("degree")).zfill(2))
            if key[0]:
                merged[key] = notice
        gw_count = len(merged)
        web_count = 0
        try:
            web_pages = WebLHCrawler.get_page_count(self, start_date, end_date)
            if web_pages > 50:
                raise RuntimeError("웹 목록 페이지 제한 초과: {}".format(web_pages))
            for page_no in range(1, web_pages + 1):
                web_rows = WebLHCrawler.fetch_list_page(self, page_no, start_date, end_date)
                for web_notice in web_rows:
                    key = (clean(web_notice.get("notice_no")), clean(web_notice.get("degree")).zfill(2))
                    if not key[0]:
                        continue
                    web_count += 1
                    previous = merged.get(key, {})
                    combined = dict(previous)
                    combined.update(web_notice)
                    combined["degree"] = key[1]
                    combined["_web_list"] = True
                    merged[key] = combined
        except Exception as exc:
            # 정상 API 목록과 이미 조회한 웹 목록은 보존하고 장애를 명시한다.
            print("[LH_WEB_MERGE_ERROR] 웹 목록 보완 불완전: {}".format(exc), flush=True)
        notices = list(merged.values())
        print("[LH_LIST_MERGE] GW={} WEB={} merged={} web_only={}".format(
            gw_count, web_count, len(notices), len(notices) - gw_count), flush=True)

        self._gw_notices = notices

        self._gw_period = period

        self._gw_enabled = True



        print(

            "[LH_GW_ADAPTER] 시설공사 목록={} 기간={}~{}".format(

                len(notices),

                start_date,

                end_date,

            )

        )



        return notices



    def get_page_count(self, start_date, end_date):

        try:

            notices = self._load_gw_notices(start_date, end_date)

            return max(

                1,

                int(math.ceil(float(len(notices)) / self.PAGE_SIZE)),

            )

        except Exception as exc:

            self._gw_enabled = False

            self._gw_notices = None

            print(

                "[LH_GW_FALLBACK] GW 목록 실패, 기존 웹 목록 사용: {}".format(

                    exc

                )

            )

            return WebLHCrawler.get_page_count(

                self,

                start_date,

                end_date,

            )



    def fetch_list_page(self, page_no, start_date, end_date):

        if not self._gw_enabled:

            return WebLHCrawler.fetch_list_page(

                self,

                page_no,

                start_date,

                end_date,

            )



        notices = self._load_gw_notices(start_date, end_date)

        begin = (int(page_no) - 1) * self.PAGE_SIZE

        end = begin + self.PAGE_SIZE

        return notices[begin:end]



    def fetch_detail(self, notice):

        gw_item = notice.get("_gw_item") or {}

        gw_detail = api_item_to_detail(gw_item) if gw_item else {}



        try:

            web_detail = WebLHCrawler.fetch_detail(self, notice)

        except Exception as exc:

            print(

                "[LH_GW_DETAIL_FALLBACK] 공고번호={} 웹 상세 실패: {}".format(

                    notice.get("notice_no"),

                    exc,

                )

            )

            web_detail = None



        if not web_detail:
            if not gw_item:
                return None
            gw_detail["수집출처"] = "GW API"
            return gw_detail



        # 웹 상세정보를 우선하고, 공란만 GW API로 보완

        for key, value in gw_detail.items():

            if value and not clean(web_detail.get(key)):

                web_detail[key] = value



        web_detail["수집출처"] = ("GW API + LH 웹 상세" if gw_item else "LH 웹 목록 + LH 웹 상세")

        return web_detail

