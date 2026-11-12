
# -*- coding: utf-8 -*-

import os

import re

import pandas as pd

from datetime import datetime, timedelta



EXCEL_PATH = "/mnt/vol1/road/latest_exbid.xlsx"

SENT_FILE = "/mnt/vol1/road/sent_road_exbid_keys.txt"

RESULT_DIR = "/mnt/vol1/road/result"

KEEP_DAYS = 30



TARGET_KEYWORDS = [

    "전기공사업",

    "소방시설공사업",

    "전문소방시설공사업",

    "일반소방시설공사업",

    "기계설비공사업",

]



MIN_AMOUNT = 30000000





def money_to_int(v):

    if pd.isna(v):

        return 0

    s = re.sub(r"[^0-9]", "", str(v))

    return int(s) if s else 0





def load_sent():

    if not os.path.exists(SENT_FILE):

        return set()

    with open(SENT_FILE, "r", encoding="utf-8") as f:

        return set(x.strip() for x in f if x.strip())





def mark_sent(key):

    with open(SENT_FILE, "a", encoding="utf-8") as f:

        f.write(key + "\n")



def cleanup_old_excels():

    os.makedirs(RESULT_DIR, exist_ok=True)

    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)



    for fn in os.listdir(RESULT_DIR):

        if not fn.lower().endswith((".xlsx", ".xls")):

            continue

        path = os.path.join(RESULT_DIR, fn)

        try:

            mt = datetime.fromtimestamp(os.path.getmtime(path))

            if mt < cutoff:

                os.remove(path)

                print("[CLEANUP] removed old file %s" % path)

        except Exception as e:

            print("[CLEANUP][WARN] %s %s" % (path, e))





def save_excel(rows, filename):

    os.makedirs(RESULT_DIR, exist_ok=True)

    path = os.path.join(RESULT_DIR, filename)



    if rows:

        pd.DataFrame(rows).to_excel(path, index=False)

    else:

        pd.DataFrame().to_excel(path, index=False)



    print("[SAVE] %s rows=%d" % (path, len(rows)))

    return path





def match_license(row):

    text = "%s %s" % (

        row.get("입찰면허", ""),

        row.get("Unnamed: 6", ""),

    )

    return any(k in text for k in TARGET_KEYWORDS)





def build_message(row):

    return """[도로공사 입찰공고]



공고명 : {name}

공고번호 : {no}

지역 : {region}

입찰면허 : {lic1} {lic2}

설계금액 : {amount:,}원

제한유형 : {limit_type}

계약방법 : {contract}

공고일자 : {date}

상태 : {status}

""".format(

        name=row.get("공고명", ""),

        no=row.get("공고번호", ""),

        region=row.get("지역", ""),

        lic1=row.get("입찰면허", ""),

        lic2=row.get("Unnamed: 6", ""),

        amount=money_to_int(row.get("설계금액", 0)),

        limit_type=row.get("제한유형", ""),

        contract=row.get("계약방법", ""),

        date=row.get("공고일자", ""),

        status=row.get("상태", ""),

    )





def main(no_send=True):

    cleanup_old_excels()



    df = pd.read_excel(EXCEL_PATH)

    sent = load_sent()



    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    targets = []

    sent_rows = []

    run_rows = []



    for _, row in df.iterrows():

        key = str(row.get("공고번호", "")).strip()

        status = str(row.get("상태", "")).strip()

        amount = money_to_int(row.get("설계금액", 0))



        if not key:

            continue

        if key in sent:

            continue

        if status != "공고중":

            continue

        if amount < MIN_AMOUNT:

            continue

        if not match_license(row):

            continue



        targets.append(row)

        run_rows.append(dict(row))



    print("[ROAD] excel rows=%d target rows=%d no_send=%s" % (len(df), len(targets), no_send))



    save_excel([dict(r) for r in targets], "road_target_%s.xlsx" % ts)



    for row in targets:

        key = str(row.get("공고번호", "")).strip()

        msg = build_message(row)



        print("=" * 60)

        print(msg)



        if no_send:

            print("[SAFE] SKIP SEND key=%s" % key)

        else:

            from kakao_send_tb0485 import send_for_item



            fields = {

                "bid_no": str(row.get("공고번호", "")).strip(),

                "bid_name": str(row.get("공고명", "")).strip(),

                "license": ("%s %s" % (

                    str(row.get("입찰면허", "")).strip(),

                    str(row.get("Unnamed: 6", "")).strip()

                )).strip(),

                "amount": "{:,}".format(money_to_int(row.get("설계금액", 0))),

                "limit_type": str(row.get("제한유형", "")).strip(),

            }



            receivers = ["REDACTED_PRIVATE_VALUE"]



            all_ok = True

            for phone in receivers:

                ok = send_for_item(phone, fields, dry_run=False)

                print("[SEND] key=%s phone=%s ok=%s" % (key, phone, ok))

                if not ok:

                    all_ok = False



            if all_ok:

                sent_rows.append(dict(row))

                mark_sent(key)



    save_excel(sent_rows, "road_sent_%s.xlsx" % ts)

    save_excel(run_rows, "road_run_%s.xlsx" % ts)





if __name__ == "__main__":

    no_send = "--send" not in os.sys.argv

    main(no_send=no_send)

