
def make_dedup_key(notice: dict) -> str:

    source = str(notice.get("source", "")).strip()

    notice_no = str(notice.get("notice_no", "")).strip()

    notice_ord = str(notice.get("notice_ord", "")).strip()

    bid_close_dt = str(notice.get("bid_close_dt", "")).strip()



    return f"{source}|{notice_no}|{notice_ord}|{bid_close_dt}"

