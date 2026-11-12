
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

    # 공동도급지역 표시용

    region_display = _norm(r.get("공동도급지역"))

    if not region_display:

        region_display = _norm(raw.get("jntcontrctDutyRgnNm1"))

        if not region_display:

            region_display = _norm(raw.get("cnstrtsiteRgnNm"))



    # 수요지역/공사위치

    demand_region = _norm(r.get("수요지역"))

    if not demand_region:

        demand_region = _norm(raw.get("cnstrtsiteRgnNm"))



    # 게시일시

    bid_notice_dt = _norm(raw.get("bidNtceDt") or r.get("게시일시"))



    # 추정금액 / 공동도급비율

    est_str, est_val = _parse_estimate(r, raw)



    # 도급비율: main_send 에서 '도급비율' 컬럼을 넣어줬으면 그 값 우선

    jnt_str = _norm(

        r.get("도급비율")

        or r.get("공동도급비율")

        or raw.get("rgnDutyJntcontrctRt")

        or ""

    )



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



    # 지역태그: 대표지역/공동도급지역/수요지역 중 하나에서 추출

    tag_source = rep_region or region_display or demand_region or ""

    tags = extract_region_tags(tag_source)

    if isinstance(tags, list):

        region_tag = ",".join(tags)

    else:

        region_tag = str(tags) if tags else ""



    # ------------------------------

    # 수신번호 결정

    #   1순위: main_send 에서 실제 발송 후 넣어준 r["수신번호"]

    #   2순위: region_filter.decide_receivers(row_for_region)

    # ------------------------------

    pre_receivers = r.get("수신번호")

    receivers: List[str] = []



    if isinstance(pre_receivers, str):

        # "010...,010..." 형태

        parts = [x.strip() for x in pre_receivers.split(",") if x.strip()]

        receivers = parts

    elif isinstance(pre_receivers, (list, tuple, set)):

        receivers = [str(x).strip() for x in pre_receivers if str(x).strip()]



    # 사전에 설정된 수신번호가 없다면 규칙 기반으로 계산

    if not receivers:

        receivers = decide_receivers(row_for_region)



    # SKIP이유 (지금은 수신번호 유/무만 반영)

    if receivers:

        skip_reason = ""

        alarm_flag = "Y"

    else:

        skip_reason = "수신번호없음"

        alarm_flag = "N"



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

        "지역태그": region_tag,

        "추정금액": est_str,

        "추정금액_원": est_val,

        "공동도급비율": jnt_str,

        "대표지역": rep_region,

        "원문": json.dumps(raw, ensure_ascii=False),

    }



    # 수신번호: 엑셀에서 0 빠지지 않도록 작은따옴표로 감싸기

    if receivers:

        base["수신번호"] = "'" + "','".join(receivers) + "'"

    else:

        base["수신번호"] = ""



    # 엑셀 제어문자 제거

    for k, v in list(base.items()):

        base[k] = sanitize_for_excel(v)



    return base


