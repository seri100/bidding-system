
# -*- coding: utf-8 -*-

"""

region_filter.py

지역 분류 + 수신자 자동 결정 (최종 확정 버전)

"""



from typing import Dict, Any, List



# ----------------------------------------------

# 대표지역 분류

# ----------------------------------------------

def classify_region(text: str) -> str:

    if not isinstance(text, str):

        return ""

    t = text.strip()

    if "충북" in t or "충청북도" in t:

        return "충북"

    if "세종" in t:

        return "세종"

    if "대구" in t:

        return "대구"

    if "경북" in t or "경상북도" in t:

        return "경북"

    return "기타"



# ----------------------------------------------

# 수신자 규칙 (요청한 표 그대로)

# ----------------------------------------------

VALID_INDS = {"0038", "0039", "0040", "6202"}



RECV_NATION    = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

RECV_SEJONG    = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

RECV_CHUNGBUK  = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]

RECV_DAEGU     = ["REDACTED_PRIVATE_VALUE"]

RECV_GYEONGBUK = ["REDACTED_PRIVATE_VALUE"]



# ----------------------------------------------

# 수신자 결정

# ----------------------------------------------

def decide_receivers(row: Dict[str, Any]) -> List[str]:

    ind = str(row.get("공고업종코드", "")).strip()

    if ind not in VALID_INDS:

        return []



    amount = int(row.get("추정금액", 0) or 0)

    region = classify_region(str(row.get("대표지역", "")))



    # 전국 발송 기준: 11억 이상

    if amount >= 1_100_000_000:

        return RECV_NATION



    if region == "세종":

        return RECV_SEJONG

    if region == "충북":

        return RECV_CHUNGBUK

    if region == "대구":

        return RECV_DAEGU

    if region == "경북":

        return RECV_GYEONGBUK



    return []

