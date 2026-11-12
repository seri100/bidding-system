# -*- coding: utf-8 -*-

from __future__ import print_function



import os

import re

import sys

from pathlib import Path



import pandas as pd



SEND_READY_DIR = Path("/mnt/vol1/bid/exroad/send_ready")

DELIVERED_FILE = Path("/mnt/vol1/bid/exroad/delivered_keys.txt")





def clean(v):

    if v is None:

        return ""

    try:

        if pd.isna(v):

            return ""

    except Exception:

        pass

    return str(v).strip()





def normalize_phone(v):

    s = re.sub(r"[^0-9]", "", clean(v))

    if len(s) == 10 and s.startswith("1"):

        s = "0" + s

    return s





def load_delivered():

    if not DELIVERED_FILE.exists():

        return set()

    with DELIVERED_FILE.open("r", encoding="utf-8") as f:

        return {line.strip() for line in f if line.strip()}





def mark_delivered(key):

    DELIVERED_FILE.parent.mkdir(parents=True, exist_ok=True)

    with DELIVERED_FILE.open("a", encoding="utf-8") as f:

        f.write(key + "\n")

        f.flush()

        os.fsync(f.fileno())





def load_ready_rows():

    rows = []



    for excel_path in sorted(SEND_READY_DIR.glob("exroad_send_ready_*.xlsx")):

        try:

            df = pd.read_excel(str(excel_path))

        except Exception as e:

            print("[EXROAD_READY][READ_ERROR] file=%s error=%s" % (excel_path, e))

            continue



        for _, row in df.iterrows():

            item = dict(row)

            item["_source_file"] = str(excel_path)

            rows.append(item)



    return rows





def main(no_send=True):

    delivered = load_delivered()

    rows = load_ready_rows()



    ready_count = 0

    sent_count = 0

    skip_count = 0

    fail_count = 0



    for row in rows:

        status = clean(row.get("send_status")).upper()

        key = clean(row.get("notice_key"))

        bid_no = clean(row.get("bid_no"))

        receiver = normalize_phone(row.get("receiver"))



        if status and status != "READY":

            skip_count += 1

            continue



        if not key:

            key = "EXROAD_DELIVERY:%s:%s" % (bid_no, receiver)



        if key in delivered:

            skip_count += 1

            continue



        ready_count += 1



        fields = {

            "bid_no": bid_no,

            "bid_ord": clean(row.get("bid_ord")) or "000",

            "bid_name": clean(row.get("bid_name")),

            "license": clean(row.get("license")),

            "amount": clean(row.get("amount")).replace("원", "").strip(),

            "limit_type": clean(row.get("limit_type")) or "미확인",

            "close_time": clean(row.get("close_time")) or "미기재",

            "joint_region": clean(row.get("joint_region")),

            "joint_rate": clean(row.get("joint_rate")),

            "joint_method": clean(row.get("joint_method")),

            "joint_member_min_rate": clean(row.get("joint_member_min_rate")),

        }



        print(

            "[EXROAD_READY][TARGET] key=%s bid_no=%s receiver=%s name=%s"

            % (key, bid_no, receiver, fields["bid_name"])

        )



        if no_send:

            print("[EXROAD_READY][DRY] 발송하지 않음")

            continue



        if not receiver:

            print("[EXROAD_READY][FAIL] 수신번호 없음 key=%s" % key)

            fail_count += 1

            continue



        try:

            from kakao_send_tb0485 import send_for_item

            ok = send_for_item(receiver, fields, dry_run=False)

            print(

                "[EXROAD_READY][SEND] key=%s receiver=%s ok=%s"

                % (key, receiver, ok)

            )

        except Exception as e:

            print("[EXROAD_READY][SEND_ERROR] key=%s error=%s" % (key, e))

            ok = False



        if ok:

            mark_delivered(key)

            delivered.add(key)

            sent_count += 1

        else:

            fail_count += 1



    print(

        "[EXROAD_READY][DONE] files=%d rows=%d ready=%d sent=%d skip=%d fail=%d"

        % (

            len(list(SEND_READY_DIR.glob("exroad_send_ready_*.xlsx"))),

            len(rows),

            ready_count,

            sent_count,

            skip_count,

            fail_count,

        )

    )



    return 1 if fail_count else 0





if __name__ == "__main__":

    sys.exit(main(no_send=("--send" not in sys.argv)))
