
from datetime import datetime, timedelta



WEEKDAY_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]





def format_datetime_range_kr(dt_text: str, default_minutes: int = 60) -> str:

    if not dt_text:

        return ""



    dt = datetime.strptime(dt_text, "%Y-%m-%d %H:%M:%S")

    end_dt = dt + timedelta(minutes=default_minutes)



    start_ampm = "오전" if dt.hour < 12 else "오후"

    start_hour = dt.hour

    if start_hour == 0:

        start_hour = 12

    elif start_hour > 12:

        start_hour -= 12



    end_ampm = "오전" if end_dt.hour < 12 else "오후"

    end_hour = end_dt.hour

    if end_hour == 0:

        end_hour = 12

    elif end_hour > 12:

        end_hour -= 12



    weekday_name = WEEKDAY_KR[dt.weekday()]



    if start_ampm == end_ampm:

        return f"{dt.month}월 {dt.day}일 ({weekday_name})⋅{start_ampm} {start_hour}:{dt.minute:02d}~ {end_hour}:{end_dt.minute:02d}"

    return f"{dt.month}월 {dt.day}일 ({weekday_name})⋅{start_ampm} {start_hour}:{dt.minute:02d}~ {end_ampm} {end_hour}:{end_dt.minute:02d}"





def build_notice_message(notice: dict) -> str:

    title = notice.get("title", "")

    source = notice.get("source", "")

    notice_no = notice.get("notice_no", "")

    notice_ord = notice.get("notice_ord", "")

    agency = notice.get("agency", "")

    site = notice.get("site", "")

    license_name = notice.get("license_name", "")

    estimated_price_text = notice.get("estimated_price_text", "")

    low_limit = notice.get("low_limit", "")

    bid_method = notice.get("bid_method", "")

    joint_region = notice.get("joint_region", "")

    joint_ratio = notice.get("joint_ratio", "")

    joint_condition = notice.get("joint_condition", "")

    open_dt = notice.get("open_dt", "")

    url = notice.get("url", "")

    bid_close_dt = notice.get("bid_close_dt", "")



    time_line = format_datetime_range_kr(bid_close_dt) if bid_close_dt else ""



    lines = [

        f"[입찰마감] {title}",

        time_line,

        f"기관구분: {source}" if source else "",

        f"공고번호: {notice_no}" if notice_no else "",

        f"차수: {notice_ord}" if notice_ord else "",

        f"발주기관: {agency}" if agency else "",

        f"공사현장: {site}" if site else "",

        f"주요면허: {license_name}" if license_name else "",

        f"추정가격: {estimated_price_text}" if estimated_price_text else "",

        f"낙찰하한: {low_limit}" if low_limit else "",

        f"낙찰방식: {bid_method}" if bid_method else "",

        f"공동도급지역: {joint_region} | 비율: {joint_ratio}" if joint_region and joint_ratio else (

            f"공동도급지역: {joint_region}" if joint_region else ""

        ),

        f"공동수급조건: {joint_condition}" if joint_condition else "",

        f"개찰일시: {open_dt}" if open_dt else "",

        url if url else "",

    ]



    return "\n".join([x for x in lines if x])

