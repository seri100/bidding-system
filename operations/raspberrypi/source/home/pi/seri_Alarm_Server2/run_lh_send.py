
# -*- coding: utf-8 -*-



import os

from pathlib import Path



from app.alligo_client import AlligoClient

from app.lh_fetcher import fetch_lh_from_excel

from app.kakao_vars import build_lh_vars

from app.message_formatter import build_lh_message_preview

from app.dedup import is_sent, mark_sent

from app.logger import log_line



def load_env(path=".env"):

    p = Path(path)

    if not p.exists():

        return

    for line in p.read_text(encoding="utf-8").splitlines():

        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:

            continue

        k, v = line.split("=", 1)

        os.environ.setdefault(k.strip(), v.strip())



def main():

    load_env("/home/pi/seri_Alarm_Server2/.env")



    tpl_code = os.environ.get("LH_TPL_CODE", "TZ_4492")

    msg_head = os.environ.get("LH_MSG_HEAD", "REDACTED_PRIVATE_VALUE")

    sender = os.environ.get("SENDER_PHONE", "REDACTED_PRIVATE_VALUE")



    receivers_raw = os.environ.get("RECEIVERS", sender)

    receivers = [x.strip() for x in receivers_raw.split(",") if x.strip()]



    log_dir = os.environ.get("LOG_DIR", "REDACTED_PRIVATE_VALUE")



    log_line(log_dir, "lh_send", "=== RUN START ===")



    items = fetch_lh_from_excel()

    if not items:

        log_line(log_dir, "lh_send", "NO LH EXCEL")

        print("❌ LH 엑셀 없음")

        return



    a = AlligoClient()

    a.get_token()



    sent_cnt = 0

    skip_cnt = 0



    for it in items:

        lh_no = it.get("lhNo")

        if not lh_no:

            continue



        if is_sent(lh_no):

            skip_cnt += 1

            log_line(log_dir, "lh_send", f"SKIP sent {lh_no}")

            continue



        vars_dict = build_lh_vars(

            lh_no=lh_no,

            lh_type=it.get("lhType") or "공사",

            lh_nm=it.get("lhNm") or "",

            lh_amount=it.get("lhAmount") or "",

            lh_loc=it.get("lhLoc") or "",

            lh_start=it.get("lhStartDate") or "",

            lh_end=it.get("lhEndDate") or "",

        )



        message = build_lh_message_preview(vars_dict)



        ok = a.send_alimtalk(

            tpl_code=tpl_code,

            sender=sender,

            msg_head=msg_head,

            message=message,

            receivers=receivers,

        )



        log_line(log_dir, "lh_send", f"SEND {lh_no} ok={ok}")



        if ok:

            mark_sent(lh_no)

            sent_cnt += 1



    log_line(log_dir, "lh_send", f"=== RUN END sent={sent_cnt} skip={skip_cnt} ===")

    print(f"✅ DONE sent={sent_cnt} skip={skip_cnt}")



if __name__ == "__main__":

    main()

