
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import os

import re

import json

import glob

import datetime

import sys



import pandas as pd



# ✅ alligo.py는 /home/pi/seri_Alarm_Server6/alligo.py 에 있음

# lh 폴더에서 실행되므로 상위폴더를 path에 추가해서 import

sys.path.insert(0, "/home/pi/seri_Alarm_Server6")

from alligo import Alligo  # noqa





# -----------------------------

# 고정 설정

# -----------------------------

BASE_DIR = "REDACTED_PRIVATE_VALUE"   # 엑셀 생성되는 위치

PATTERN  = "LH_*.xlsx"

STATE_FILE = "/home/pi/seri_Alarm_Server6/lh/lh_notify_sent.json"  # ✅ 로컬 고정

TPL_CODE = "TZ_4492"



# ✅ 알림 수신번호

RECEIVERS = ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"]



# ✅ 공종 필터(이 4개만 전송)

JOB_LIST = ["기계설비", "가스공사", "소방시설공사", "전기공사"]



# 업종유형에서 공종을 직접 판정(있으면 우선)

JOB_TYPE_MATCH = {

    "기계설비": ["기계설비"],

    "가스공사": ["가스공사", "가스"],

    "소방시설공사": ["소방시설공사", "소방"],

    "전기공사": ["전기공사", "전기"],

}



# 업종유형이 '전문공사'처럼 뭉뚱그려져 있을 때 공고명(입찰공고건명)에서 추정

JOB_NAME_MATCH = {

    "소방시설공사": ["소방", "스프링클러", "화재", "경보", "감지기"],

    "전기공사": ["전기", "수변전", "배전", "분전", "UPS", "변압기", "케이블", "조명"],

    "기계설비": ["기계", "설비", "냉방", "난방", "공조", "에어컨", "덕트", "환기", "보일러", "펌프"],

    "가스공사": ["가스", "LPG", "도시가스", "가스배관"],

}



def detect_job(job_type: str, job_name: str) -> str:

    jt = (job_type or "").strip()

    jn = (job_name or "").strip()



    # 1) 업종유형 우선

    for job, keys in JOB_TYPE_MATCH.items():

        if any(k in jt for k in keys):

            return job



    # 2) 공고명으로 추정

    for job, keys in JOB_NAME_MATCH.items():

        if any(k in jn for k in keys):

            return job



    return ""





def now():

    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def log(msg):

    print(msg, flush=True)



def load_state():

    try:

        with open(STATE_FILE, "r", encoding="utf-8") as f:

            return set(json.load(f))

    except Exception:

        return set()



def save_state(s):

    tmp = STATE_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:

        json.dump(sorted(list(s)), f, ensure_ascii=False, indent=2)

    os.replace(tmp, STATE_FILE)



def latest_xlsx():

    files = sorted(glob.glob(os.path.join(BASE_DIR, PATTERN)))

    if not files:

        return None

    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    return files[0]



def pick_col(row, col):

    v = row.get(col, "")

    if v is None:

        return ""

    return str(v).strip()



def amount_num(s: str) -> str:

    s = str(s or "")

    digits = re.sub(r"[^0-9]", "", s)

    return digits if digits else ""



def join_locs(row) -> str:

    locs = []

    for c in ["참가지역1","참가지역2","참가지역3","참가지역4"]:

        v = pick_col(row, c)

        if v:

            locs.append(v)

    return ", ".join(locs) if locs else "해당없음"



def build_message(row, job_name: str):

    # 템플릿 변수:

    # #{lhNo}, #{lhType}, #{lhNm}, #{lhAmount}, #{lhLoc}, #{lhStartDate}, #{lhEndDate}



    lh_no = pick_col(row, "공고번호")

    lh_type = pick_col(row, "업종유형") or "미기재"

    lh_nm = pick_col(row, "입찰공고건명") or "(공고명 미기재)"



    lh_amount_raw = pick_col(row, "추정가격")

    lh_amount = amount_num(lh_amount_raw) or "미기재"



    lh_loc = join_locs(row)

    lh_start = pick_col(row, "입찰서접수개시일시") or "미기재"

    lh_end = pick_col(row, "입찰서접수마감일시") or "미기재"



    msg = (

        f"[세리공영]\n\n"

        f"공고번호 : {lh_no} - 000\n"

        f"공고명 : {lh_nm}\n"

        f"공종 : {job_name or '미분류'}\n"

        f"업종유형 : {lh_type}\n"

        f"추정가격 : {lh_amount_raw or '미기재'}\n"

        f"참가지역 : {lh_loc}\n"

        f"접수개시 : {lh_start}\n"

        f"접수마감 : {lh_end}\n"

    )

    return msg



def main():

    fx = latest_xlsx()

    if not fx:

        log(f"[NOTIFY] no xlsx found in {BASE_DIR}/{PATTERN}")

        return 0



    df = pd.read_excel(fx, dtype=str).fillna("")

    sent = load_state()



    new_rows = []

    skipped_nojob = 0



    for _, r in df.iterrows():

        bid = str(r.get("공고번호","")).strip()

        if not bid:

            continue

        if bid in sent:

            continue



        job = detect_job(

            job_type=str(r.get("업종유형","")),

            job_name=str(r.get("입찰공고건명","")),

        )



        # ✅ 공종 필터 적용

        if job not in JOB_LIST:

            skipped_nojob += 1

            continue



        # 판정된 공종을 row에 임시로 저장(메시지에 넣기 위함)

        r["_JOB_NAME_"] = job

        new_rows.append(r)



    log(f"[NOTIFY] latest_xlsx={fx} rows={len(df)} new={len(new_rows)} skipped_nojob={skipped_nojob}")



    if not new_rows:

        return 0



    a = Alligo()

    ok_cnt = 0



    for r in new_rows:

        bid = str(r.get("공고번호","")).strip()

        job = str(r.get("_JOB_NAME_","")).strip()



        msg = build_message(r, job_name=job)

        subject = "REDACTED_PRIVATE_VALUE"



        ok = a.sendTalk(

            tpl_code=TPL_CODE,

            sender="REDACTED_PRIVATE_VALUE",     # 발신번호(등록된 번호 사용)

            msgHead=subject,

            message=msg,

            receiverList=RECEIVERS

        )



        if ok:

            ok_cnt += 1

            sent.add(bid)

            save_state(sent)

            log(f"[SEND] OK bid={bid} job={job}")

        else:

            log(f"[SEND] FAIL bid={bid} job={job}")



    log(f"[NOTIFY] done. sent_total={ok_cnt}")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())

