
# -*- coding: utf-8 -*-



def build_lh_vars(

    lh_no: str,

    lh_type: str,

    lh_nm: str,

    lh_amount: str,

    lh_loc: str,

    lh_start: str,

    lh_end: str,

) -> dict:

    """

    템플릿 치환변수:

      #{lhNo}, #{lhType}, #{lhNm}, #{lhAmount}, #{lhLoc}, #{lhStartDate}, #{lhEndDate}

    """

    return {

        "lhNo": lh_no,

        "lhType": lh_type,

        "lhNm": lh_nm,

        "lhAmount": lh_amount,

        "lhLoc": lh_loc,

        "lhStartDate": lh_start,

        "lhEndDate": lh_end,

    }

