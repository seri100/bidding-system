
def make_notice_dict(

    source="",

    notice_no="",

    notice_ord="",

    title="",

    agency="",

    site="",

    license_name="",

    estimated_price_text="",

    bid_close_dt="",

    open_dt="",

    joint_region="",

    joint_ratio="",

    joint_condition="",

    bid_method="",

    low_limit="",

    url="",

    raw=None,

):

    return {

        "source": source,

        "notice_no": notice_no,

        "notice_ord": notice_ord,

        "title": title,

        "agency": agency,

        "site": site,

        "license_name": license_name,

        "estimated_price_text": estimated_price_text,

        "bid_close_dt": bid_close_dt,

        "open_dt": open_dt,

        "joint_region": joint_region,

        "joint_ratio": joint_ratio,

        "joint_condition": joint_condition,

        "bid_method": bid_method,

        "low_limit": low_limit,

        "url": url,

        "raw": raw or {},

    }

