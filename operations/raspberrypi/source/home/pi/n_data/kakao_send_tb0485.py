# -*- coding: utf-8 -*-



import os

from alligo import Alligo













def _alimtalk_award_title_v1(bid_name, fields):

    import html

    import re

    import unicodedata



    title = str(bid_name or "").strip()

    method = str(fields.get("낙찰방법세부기준") or "")

    text = unicodedata.normalize("NFKC", html.unescape(method))

    text = re.sub(r"\s+", "", text)

    bid_no = str(fields.get("bid_no") or "")



    def unchanged(reason):

        print("[AWARD_LABEL] bid={} reason={} method={!r}".format(

            bid_no, reason, method

        ))

        return title



    # PROCUREMENT_COMPREHENSIVE_LABEL_V1

    if "조달청공사계약종합심사낙찰제심사세부기준" in text:

        label = "조달 종합심사"

        title = re.sub(

            r"\s*/\s*(?:(?:지자체|조달)\s*(?:\d+억이상_\d+억미만|2억미만)|조달\s*종합심사)\s*$",

            "",

            title,

        ).rstrip()

        print("[AWARD_LABEL] bid={} label={}".format(bid_no, label))

        return "{}/{}".format(title, label)



    if (

        "지방자치단체입찰시낙찰자결정기준" in text

        or text == (

            "적격심사제-추정가격이30억원미만10억원이상인입찰공사"

            "(실적제한아님)"

        )

        or text == (

            "적격심사제-추정가격이50억원미만30억원이상인입찰공사"

            "(실적제한아님,그밖의공사)"

        )

    ):

        agency = "지자체"

        allowed = ((2, 4), (4, 10), (10, 30), (30, 50), (50, 100))

    elif (

        "조달청시설공사적격심사세부기준" in text

        or text == (

            "적격심사제-추정가격50억원미만10억원이상인공사"

            "(실적에의한경쟁입찰이외,"

            "전기·정보통신·소방시설·국가유산공사등)"

        )

    ):

        agency = "조달"

        allowed = ((10, 50), (50, 100))

    else:

        return unchanged("기준명 없음 또는 미지원")



    # 두 금액 사이의 쉼표, 물결표, 구분기호 등을 허용한다.

    prefix = r"추정가격(?:이|은)?[:：]?"

    separator = r"(?:(?:이고|이며|및)|[,·ㆍ~∼～/＿_－—–\-])*"

    match = re.search(

        prefix

        + r"(?:(\d+)억(?:원)?미만" + separator

        + r"(\d+)억(?:원)?이상"

        + r"|(\d+)억(?:원)?이상" + separator

        + r"(\d+)억(?:원)?미만)",

        text,

    )



    label = ""

    if match:

        a, b, c, d = match.groups()

        lower, upper = (int(b), int(a)) if a is not None else (int(c), int(d))

        if (lower, upper) not in allowed:

            return unchanged("지원 구간 외")

        label = "{} {}억이상_{}억미만".format(agency, lower, upper)

    elif agency == "지자체" and re.search(

        prefix + r"2억(?:원)?미만(?!.*\d+억(?:원)?이상)", text

    ):

        label = "지자체 2억미만"

    else:

        return unchanged("추정가격 구간 해석 불가")



    title = re.sub(

        r"\s*/\s*(?:지자체|조달)\s*(?:\d+억이상_\d+억미만|2억미만)\s*$",

        "", title

    ).rstrip()

    print("[AWARD_LABEL] bid={} label={}".format(bid_no, label))

    return title + "/" + label



def _short_region_name(v):

    s = str(v or "").strip()

    repl = {

        "서울특별시": "서울",

        "부산광역시": "부산",

        "대구광역시": "대구",

        "인천광역시": "인천",

        "광주광역시": "광주",

        "대전광역시": "대전",

        "울산광역시": "울산",

        "세종특별자치시": "세종",

        "경기도": "경기",

        "강원특별자치도": "강원",

        "충청북도": "충북",

        "충청남도": "충남",

        "전북특별자치도": "전북",

        "전라남도": "전남",

        "경상북도": "경북",

        "경상남도": "경남",

        "제주특별자치도": "제주",

    }

    for a, b in repl.items():

        s = s.replace(a, b)

    return s





def _alimtalk_joint_region(fields):

    """

    TB_0485 공동도급지역 전용.

    실제 공동도급지역만 사용한다.

    참가가능지역/대표지역/전국 값은 사용하지 않는다.

    없으면 공란.

    """

    keys = [

        "joint_region",

        "jntcontrctDutyRgnNm1",

        "공동도급지역",

        "공동도급의무지역",

        "공동도급의무지역명",

    ]



    for k in keys:
        value = str(fields.get(k) or "").strip()
        if not value or value.lower() in ("nan", "none", "null"):
            continue
        parts = [x.strip() for x in value.split("|") if x.strip()]
        parts = [x for x in parts if x not in ("없음", "해당없음", "전국")]
        if parts:
            return " / ".join(dict.fromkeys(_short_region_name(x) for x in parts))
    return ""



def _alimtalk_joint_ratio(fields):

    """

    TB_0485 공동도급비율 전용.

    실제 공동도급비율만 사용한다.

    없으면 없음.

    """

    keys = [

        "joint_rate",

        "rgnDutyJntcontrctRt",

        "공동도급비율",

        "공동도급의무지역비율",

        "공동도급의무비율",

    ]



    for k in keys:

        v = fields.get(k)

        if v is None:

            continue



        v = str(v).strip()



        if not v or v.lower() in ("nan", "none", "null"):

            continue



        if v in ("없음", "해당없음"):

            continue



        if v.replace(".", "", 1).isdigit() and not v.endswith("%"):

            v = v + "%"



        return v



    return "없음"









def send_for_item(receiver, fields, dry_run=False):



    # --- FORCE BLOCK (safety) ---

    if os.environ.get('HARD_NO_SEND', '').strip() == '1':

        print(f"[HARD_NO_SEND] blocked send: receivers={receiver}")

        return {'blocked': True}



    a = Alligo()



    def _safe(v, default):

        if v is None:

            return default



        s = str(v).strip()



        if s == "" or s.lower() in ("none", "n/a", "nan"):

            return default



        return s



    def _amount_str():



        s = fields.get("amount_str")



        if s:

            s = str(s).strip()



            if s and s.lower() not in ("none", "n/a", "nan"):

                return s



        v = fields.get("amount", 0)



        try:

            return f"{int(str(v).replace(',', '').strip()):,}"



        except Exception:

            return "0"



    def _amount_display():
        value = _amount_str()
        result = "미확인" if value == "미확인" else value + "원"
        if fields.get("시공경험배점한도") is True:
            result += "/배점한도"
        return result

    bid_name     = _safe(fields.get("bid_name"), "공고명미기재")

    close_time   = _safe(fields.get("close_time"), "미기재")

    joint_region = _safe(fields.get("joint_region"), "해당없음")

    joint_rate   = _safe(fields.get("joint_rate"), "해당없음")

    bid_no       = _safe(fields.get("bid_no"), "")

    bid_ord      = _safe(fields.get("bid_ord"), "000")



    if joint_rate not in ("해당없음", "미기재"):

        try:

            float(str(joint_rate).replace("%", "").strip())



            if not str(joint_rate).endswith("%"):

                joint_rate = f"{joint_rate}%"



        except Exception:

            pass



    prtcpt_region = _safe(

        fields.get("prtcpt_region")

        or fields.get("prtcptPsblRgnNm")

        or fields.get("참가가능지역")

        or "",

        ""

    )



    instt = _safe(

        fields.get("dminsttNm")

        or fields.get("ntceInsttNm")

        or fields.get("발주기관")

        or fields.get("agency")

        or "",

        ""

    )



    is_rail = "국가철도공단" in instt



    if is_rail:



        rail_region = prtcpt_region or joint_region or "확인필요"



        if "|" in rail_region:

            rail_region = rail_region.split("|")[0].strip() + " 외"



        msg = (

            "[세리공영]\n\n"

            f"공고명 : {_alimtalk_award_title_v1(bid_name, fields)}\n"

            f"입찰마감일시 :  {close_time}\n"

            f"발주기관 : {instt}\n"

            f"공동도급지역 : {_alimtalk_joint_region(fields)}\n"

            f"공동도급비율 : {_alimtalk_joint_ratio(fields)}\n"

            f"추정금액 : {_amount_display()}\n"

            f"공고번호 : {bid_no} - {bid_ord}"

        )



    else:



        if (

            _alimtalk_joint_region(fields)

            or _alimtalk_joint_ratio(fields) != "없음"

        ):



            region_line = f"공동도급지역 : {_alimtalk_joint_region(fields)}\n"

            rate_line = f"공동도급비율 : {_alimtalk_joint_ratio(fields)}\n"



        elif prtcpt_region:



            region_line = f"공동도급지역 : {_alimtalk_joint_region(fields)}\n"

            # 공동도급 의무가 없는 공고의 참가가능지역만 괄호 안에 표시한다.
            possible_region = prtcpt_region.strip()
            import re
            regions = []
            for value in re.split(r"[|,/;·\n]+", possible_region):
                value = value.strip().strip("[]() ").strip()
                if value and value.lower() not in ("전국", "없음", "해당없음", "nan", "none", "n/a") and value not in regions:
                    regions.append(value)
            display_region = ",".join(regions) if len(regions) > 1 else (_short_region_name(regions[0]) if regions else "")
            rate_line = f"공동도급비율 : 없음({display_region})\n" if display_region else "공동도급비율 : 없음\n"



        else:



            region_line = f"공동도급지역 : {_alimtalk_joint_region(fields)}\n"

            rate_line = "공동도급비율 : 없음\n"



        msg = (

            "[세리공영]\n\n"

            f"공고명 : {_alimtalk_award_title_v1(bid_name, fields)}\n"

            f"입찰마감일시 :  {close_time}\n"

            f"{region_line}"

            f"{rate_line}"

            f"추정금액 : {_amount_display()}\n"

            f"공고번호 : {bid_no} - {bid_ord}"

        )



    if dry_run:



        print(f"[SAFE] DRY RUN: SKIP SEND → {receiver}")

        print(msg)



        return {

            "ok": True,

            "receiver": receiver,

            "dry_run": True,

            "message": msg

        }



    sender_fixed = os.getenv("ALLIGO_SENDER", "REDACTED_PRIVATE_VALUE").strip()



    ok = a.sendTalk(

        tpl_code="TB_0485",

        sender=sender_fixed,

        msgHead="[세리공영] 입찰 공고 알림",

        message=msg,

        receiverList=[receiver]

    )



    return {

        "ok": bool(ok),

        "receiver": receiver,

        "dry_run": False

    }

