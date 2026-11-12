
"""

formatter.py

- 공고(dict) -> 문자 메시지 문자열

- 새판 공통 포맷: [세리공영] + 핵심 필드 + 공고번호

"""



from typing import Dict, Any, Optional





def _s(v: Any) -> str:

    """None/빈값 안전 문자열"""

    if v is None:

        return ""

    v = str(v).strip()

    return v





def _money(v: Any) -> str:

    """숫자/문자 혼합 금액 -> 보기좋게 (가능하면 콤마)"""

    s = _s(v)

    if not s:

        return ""

    # 숫자만 남겨보기

    digits = "".join(ch for ch in s if ch.isdigit())

    if not digits:

        return s

    try:

        n = int(digits)

        return f"{n:,}원"

    except Exception:

        return s





def build_message(row: Dict[str, Any]) -> str:

    """

    row 예시 키(없어도 동작):

      - 공고명 / bidNtceNm

      - 입찰마감일시 / bidClseDt

      - 공동도급지역 / jntcontrctDutyRgnNm1

      - 공동도급비율 / jntcontrctDutyRgnRt or joint_rate

      - 추정금액 / presmptPrce or bdgtAmt

      - 공고번호 / bidNtceNo, bidNtceOrd or 공고번호문자열

    """



    # 1) 공고명

    title = _s(row.get("공고명") or row.get("bidNtceNm") or row.get("bidNtceNmKr"))



    # 2) 마감일시

    close_dt = _s(row.get("입찰마감일시") or row.get("bidClseDt") or row.get("bidClseDtTm"))



    # 3) 공동도급지역/비율

    joint_region = _s(

        row.get("공동도급지역")

        or row.get("jntcontrctDutyRgnNm1")

        or row.get("jntcontrctDutyRgnNm")

        or "해당없음"

    )

    joint_rate = _s(

        row.get("공동도급비율")

        or row.get("jntcontrctDutyRgnRt")

        or row.get("joint_rate")

        or "해당없음"

    )



    # 4) 금액

    amount = _money(row.get("추정금액") or row.get("presmptPrce") or row.get("bdgtAmt") or row.get("bssamt"))



    # 5) 공고번호(번호-차수 형태 선호)

    bid_no = _s(row.get("bidNtceNo") or row.get("공고번호") or "")

    bid_ord = _s(row.get("bidNtceOrd") or row.get("공고차수") or "")



    bid_disp = ""

    if bid_no and bid_ord:

        bid_disp = f"{bid_no} - {bid_ord}"

    else:

        bid_disp = bid_no or _s(row.get("공고번호문자열"))



    # 6) 마감일시가 없으면 '미기재'로

    if not close_dt:

        close_dt = "미기재"



    if not joint_region:

        joint_region = "해당없음"

    if not joint_rate:

        joint_rate = "해당없음"



    lines = [

        "[세리공영]",

        "",

        f"공고명 : {title}",

        f"입찰마감일시 : {close_dt}",

        f"공동도급지역 : {joint_region}",

        f"공동도급비율 : {joint_rate}",

        f"추정금액 : {amount}",

        f"공고번호 : {bid_disp}",

    ]



    return "\n".join(lines).strip()





def build_debug_message(row: Dict[str, Any], extra: Optional[str] = None) -> str:

    """

    디버그용: 핵심 필드 + extra 로그

    """

    msg = build_message(row)

    if extra:

        msg += f"\n\n[DEBUG]\n{extra}"

    return msg

