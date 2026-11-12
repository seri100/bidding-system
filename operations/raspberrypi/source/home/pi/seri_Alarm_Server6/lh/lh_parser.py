
# -*- coding: utf-8 -*-

import re







def _pick_first_value(d, *keys):

    """Return first non-empty value from dict by candidate keys."""

    if not isinstance(d, dict):

        return ""

    for k in keys:

        v = d.get(k)

        if v not in (None, ""):

            return str(v).strip()

    return ""



class LHParser:

    """

    LH 상세 공고 데이터 표준화 / 정제 모듈

    """



    @staticmethod

    def normalize(detail_raw):

        """

        LH 상세 공고 detail_raw(dict) → 표준화된 데이터 dict 로 변환

        파일 저장/엑셀/알림톡 모두 이 데이터 구조를 사용

        """



        out = {}



        # 공고 기본 정보

        out["공고번호"] = (detail_raw.get("공고번호") or "").strip()

        out["입찰공고일"] = (detail_raw.get("입찰공고일") or "").strip()



        # ---- 공고명에서 "본 공고는 지문인식..." 꼬리 제거 ----

        raw_title = (detail_raw.get("입찰공고건명") or "").strip()

        # "본 공고는 지문인식 전자입찰제도가 적용되오니" 가 등장하면 그 앞까지만 사용

        clean_title = re.sub(

            r"\s*본 공고는 지문인식 전자입찰제도가 적용되오니.*$",

            "",

            raw_title,

        ).strip()

        out["입찰공고건명"] = clean_title



        # 가격 관련

        out["추정가격"] = (detail_raw.get("추정가격") or "").strip()

        out["설계가격"] = (detail_raw.get("설계가격") or "").strip()

        out["기초금액"] = (detail_raw.get("기초금액") or "").strip()

        out["가격점수제외금액(A)"] = _pick_first_value(detail_raw, "가격점수제외금액(A)", "가격점수제외금액", "가격점수 제외금액(A)", "가격점수 제외금액", "prcScrExclAmt", "priceScoreExcludeAmount")

        out["낙찰제외기준금액"] = _pick_first_value(detail_raw, "낙찰제외기준금액", "낙찰제외 기준금액", "낙찰 제외기준금액", "낙찰 제외 기준금액", "sucsfbidExclBssAmt", "bidExcludeBaseAmount")



        # 입찰 일정

        out["입찰서접수개시일시"] = (detail_raw.get("입찰서접수개시일시") or "").strip()

        out["입찰서접수마감일시"] = (detail_raw.get("입찰서접수마감일시") or "").strip()
        out["공동수급협정서접수마감일시"] = (detail_raw.get("공동수급협정서접수마감일시") or "").strip()
        out["공동수급협정서 접수/구성 방식"] = (detail_raw.get("공동수급협정서 접수/구성 방식") or "").strip()

        out["개찰일시"] = (detail_raw.get("개찰일시") or "").strip()



        # 지역 정보

        out["참가지역1"] = (detail_raw.get("참가지역1") or "").strip()

        out["참가지역2"] = (detail_raw.get("참가지역2") or "").strip()

        out["참가지역3"] = (detail_raw.get("참가지역3") or "").strip()

        out["참가지역4"] = (detail_raw.get("참가지역4") or "").strip()





        # __LH_REGION_SECTION_NORMALIZE_V1_BEGIN__

        for prefix in ("지역제한", "지역의무"):

            values = []



            for region_no in range(1, 5):

                key = "{}{}".format(

                    prefix,

                    region_no,

                )

                value = str(

                    detail_raw.get(key)

                    or ""

                ).strip()



                out[key] = value



                if value and value not in values:

                    values.append(value)



            aggregate = str(

                detail_raw.get(prefix)

                or ""

            ).strip()



            out[prefix] = (

                aggregate

                if aggregate

                else ", ".join(values)

            )



        combined_regions = []



        for prefix in ("지역제한", "지역의무"):

            value = out.get(prefix, "").strip()



            if value and value not in combined_regions:

                combined_regions.append(value)



        out["참가지역"] = ", ".join(combined_regions)

        # __LH_REGION_SECTION_NORMALIZE_V1_END__





        # __REDACTED_PRIVATE_VALUE_ATTACHMENT_NORMALIZE_V1_BEGIN__

        for key in (

            "공고문 서버파일명",

            "공고문 내부경로",

            "공고문 표시파일명",

            "공고문 추출상태",

        ):

            out[key] = str(

                detail_raw.get(key)

                or ""

            ).strip()

        raw_attachments = detail_raw.get("첨부파일목록") or []
        out["첨부파일목록"] = raw_attachments if isinstance(raw_attachments, list) else []

        # __REDACTED_PRIVATE_VALUE_ATTACHMENT_NORMALIZE_V1_END__





        # 업종



        out["업종유형"] = (detail_raw.get("업종유형") or detail_raw.get("업종") or "").strip()



        # 요구면허

        out["요구면허"] = (detail_raw.get("요구면허") or "").strip()

        for i in range(1, 11):

            key = "요구면허{}".format(i)

            out[key] = (detail_raw.get(key) or "").strip()







        return out

