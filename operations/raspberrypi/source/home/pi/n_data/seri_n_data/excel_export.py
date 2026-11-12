
# -*- coding: utf-8 -*-

"""

seri_n_data.excel_export



- RAW 통합 엑셀 저장

- 지역/업종/금액 정보 포함

- 대표지역/금액 기준 수신번호 결정

- 대표지역별 분할 엑셀 저장

"""



import os

import re

import json

from datetime import datetime

from pathlib import Path

from typing import Any, Dict, List, Optional



import pandas as pd



from .config import OUTDIR, DIR_RAW, DIR_SPLIT

from .utils import log, _norm, sanitize_for_excel

from .region_filter import (

    decide_receivers,

    classify_region,

    extract_region_tags,  # 지금은 안 써도 import 만 유지

)



# ------------------------------------------------------

# 금액 문자열 → 정수

# ------------------------------------------------------





def _to_amount(val: Any) -> int:

    if val is None:

        return 0

    s = str(val)

    digits = re.sub(r"[^0-9]", "", s)

    return int(digits) if digits else 0





def _parse_estimate(r: Dict[str, Any], raw: Dict[str, Any]) -> (str, int):

    """

    추정금액 숫자/문자열을 통합해서 하나의 값으로 만든다.

    우선순위: r['추정금액'] → asignBdgtAmt → presmptPrce → cntrctAmt

    """

    cand = [

        r.get("추정금액"),

        raw.get("asignBdgtAmt"),

        raw.get("presmptPrce"),

        raw.get("cntrctAmt"),

    ]

    val_int = 0

    for v in cand:

        val_int = _to_amount(v)

        if val_int > 0:

            break



    if val_int > 0:

        est_str = f"{val_int:,d}"

    else:

        est_str = ""

    return est_str, val_int





# ------------------------------------------------------

# 단일 row → 엑셀용 dict 로 변환

# ------------------------------------------------------





def _build_row_dict(r: Dict[str, Any]) -> Dict[str, Any]:

    """

    fetcher.fetch_ind() 가 만든 row(dict)를

    엑셀 저장용 dict 로 변환

    """

    raw = r.get("원문") or {}

    if isinstance(raw, str):

        try:

            raw = json.loads(raw)

        except Exception:

            raw = {}



    # ------------------------------

    # 지역 관련 텍스트 정리

    # ------------------------------

    # 공동도급 1지역 (jntcontrctDutyRgnNm1) – K열(지역태그)에 그대로 사용

    jnt_primary = _norm(raw.get("jntcontrctDutyRgnNm1"))



    # 공동도급지역 표시용(엑셀 F열)

    region_display = _norm(r.get("공동도급지역"))

    if not region_display:

        region_display = jnt_primary

        if not region_display:

            region_display = _norm(raw.get("cnstrtsiteRgnNm"))



    # 수요지역/공사위치(엑셀 G열)

    demand_region = _norm(r.get("수요지역"))

    if not demand_region:

        demand_region = _norm(raw.get("cnstrtsiteRgnNm"))



    # 게시일시

    bid_notice_dt = _norm(raw.get("bidNtceDt") or r.get("게시일시"))



    # 추정금액 / 공동도급비율

    est_str, est_val = _parse_estimate(r, raw)

    jnt_str = _norm(r.get("공동도급비율") or raw.get("rgnDutyJntcontrctRt") or "")



    # ------------------------------

    # 대표지역 계산 (region_filter 사용)

    # ------------------------------

    row_for_region: Dict[str, Any] = {

        "추정금액": est_val,

        "참여업체지역": region_display,

        "공동도급비율": jnt_str,

        "지역명": demand_region,

        "공고명": r.get("공고명", ""),

    }

    rep_region = classify_region(row_for_region)



    # 지역태그(K열): 공동도급 1지역 그대로 사용

    region_tag = jnt_primary or ""



    # ------------------------------
    # 1차: 이론상 수신번호 (규칙상 대상인지 판단용)
    #   - region_filter.decide_receivers() 가
    #     classify_region(row)를 다시 호출하므로
    #     참여업체지역/지역명/공고명까지 같이 넘겨준다.
    # ------------------------------
    planned_receivers = decide_receivers(
        {
            "공고업종코드": r.get("공고업종코드", ""),
            "추정금액": est_val,
            "참여업체지역": region_display,
            "지역명": demand_region,
            "공고명": r.get("공고명", ""),
        }
    )




    # ------------------------------

    # 2차: 실제 발송된 수신번호 우선

    # ------------------------------

    actual_recv_raw = r.get("수신번호") or ""

    actual_recv_raw = str(actual_recv_raw).strip()



    if actual_recv_raw:

        recv_list_str = actual_recv_raw  # main_send 가 넣어준 실제 수신번호

        alarm_flag = "Y"

        skip_reason = ""

    else:

        # 실제 발송 정보 없음 → 규칙 기준으로만 대상 여부 판단

        if planned_receivers:

            alarm_flag = "Y"

            skip_reason = ""

        else:

            alarm_flag = "N"

            skip_reason = "수신번호없음"

        recv_list_str = ""



    # ------------------------------

    # 기본 컬럼 구성

    # ------------------------------

    base: Dict[str, Any] = {

        "공고업종코드": r.get("공고업종코드", ""),

        "공고번호": r.get("공고번호", ""),

        "차수": r.get("차수", ""),

        "공고명": r.get("공고명", ""),

        "입찰마감일시": r.get("입찰마감일시", ""),

        "공동도급지역": region_display,

        "수요지역": demand_region,

        "게시일시": bid_notice_dt,

        "알림대상": alarm_flag,

        "SKIP이유": skip_reason,

        "지역태그": region_tag,  # K열: jntcontrctDutyRgnNm1

        "수신번호": "",  # 아래에서 따옴표 처리해서 채움

        "추정금액": est_str,

        "추정금액_원": est_val,

        "공동도급비율": jnt_str,

        "심사기준": _norm(raw.get("aplBssCntnts")),  # P열: 심사기준 (행자부 등)

        "대표지역": rep_region,  # 분할 엑셀용

        "원문": json.dumps(raw, ensure_ascii=False),

    }



    # 수신번호: 엑셀에서 0 빠지지 않도록 작은따옴표로 감싸기

    if recv_list_str:

        base["수신번호"] = "'" + recv_list_str + "'"



    # 엑셀 제어문자 제거

    for k, v in list(base.items()):

        base[k] = sanitize_for_excel(v)



    return base





# ------------------------------------------------------

# 엑셀 저장 (통합 + 대표지역 분할)

# ------------------------------------------------------





def save_excel(rows: List[Dict[str, Any]]) -> Optional[str]:

    """

    - 통합 엑셀: DIR_RAW/입찰공고_YYYYMMDD_HHMM.xlsx

    - 대표지역별 분할 엑셀:

        DIR_SPLIT/입찰공고_YYYYMMDD_HHMM_{대표지역}.xlsx



    :param rows: fetch_ind/filter_rows 에서 넘어온 dict 리스트

    :return: 통합 엑셀 경로 (str)

    """

    if not rows:

        return None



    now = datetime.now()

    now_str = now.strftime("%Y%m%d_%H%M")



    # ------------------------------

    # 통합 엑셀 작성

    # ------------------------------

    dict_rows: List[Dict[str, Any]] = [_build_row_dict(r) for r in rows]

    df = pd.DataFrame(dict_rows)



    cols = [

        "공고업종코드",

        "공고번호",

        "차수",

        "공고명",

        "입찰마감일시",

        "공동도급지역",

        "수요지역",

        "게시일시",

        "알림대상",

        "SKIP이유",

        "지역태그",      # K열

        "수신번호",

        "추정금액",

        "추정금액_원",

        "공동도급비율",

        "심사기준",      # P열

        "대표지역",      # Q열 (분할용)

        "원문",

    ]

    df = df.reindex(columns=cols)



    main_path = DIR_RAW / f"입찰공고_{now_str}.xlsx"

    main_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_excel(main_path, index=False)

    log(f"[SAVE] {main_path}")



    # ------------------------------

    # 대표지역별 분할 엑셀

    # ------------------------------

    DIR_SPLIT.mkdir(parents=True, exist_ok=True)



    if "대표지역" in df.columns:

        region_series = df["대표지역"].fillna("")



        for region in region_series.unique():

            region_str = str(region or "").strip()

            if not region_str:

                region_str = "기타"



            # 파일명에 쓸 수 있도록 안전하게 변환

            safe_region = re.sub(r"[^0-9A-Za-z가-힣]+", "_", region_str).strip("_")

            if not safe_region:

                safe_region = "기타"



            split_name = f"입찰공고_{now_str}_{safe_region}.xlsx"

            split_path = DIR_SPLIT / split_name



            mask = region_series == region

            g = df[mask]

            if g.empty:

                continue



            g.to_excel(split_path, index=False)

            log(f"[SAVE] split for region={region_str} -> {split_path}")



    return str(main_path)


