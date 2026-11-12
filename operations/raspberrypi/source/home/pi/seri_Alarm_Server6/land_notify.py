
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import os, csv, json, hashlib

from pathlib import Path

from datetime import datetime



# ---------------------------

# 고정 경로(요구대로 그대로)

# ---------------------------

BASE_DIR = Path(os.getenv("BASE_DIR", "/mnt/vol1REDACTED_PRIVATE_VALUE"))

HISTORY = BASE_DIR / "sent_history.jsonl"



# ---------------------------

# 공종/수신 룰

# ---------------------------

CODES_ALL = {"0037","0038","0039","0040","6202"}

CODES_GENERAL = {"0038","0039","0040","6202"}  # 일반 룰 적용 공종



RECIP_GENERAL = {

    "전국": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "세종": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "충북": ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"],

    "대구": ["REDACTED_PRIVATE_VALUE"],

    "경북": ["REDACTED_PRIVATE_VALUE"],

}

# 예외: 전기공사(0037) + 전국일 때만 2명

RECIP_0037_NATION = ["REDACTED_PRIVATE_VALUE","REDACTED_PRIVATE_VALUE"]



# ---------------------------

# 유틸

# ---------------------------

def _norm_phone(p: str) -> str:

    p = (p or "").strip().replace("-","")

    return p



def _pick(d: dict, keys):

    for k in keys:

        if k in d and str(d[k]).strip() != "":

            return str(d[k]).strip()

    return ""



def _classify_region(s: str) -> str:

    t = (s or "").strip()

    if not t:

        return ""

    if "전국" in t:

        return "전국"

    if "세종" in t:

        return "세종"

    if "충북" in t or "충청북도" in t:

        return "충북"

    if "대구" in t:

        return "대구"

    if "경북" in t or "경상북도" in t:

        return "경북"

    # 그 외는 룰 미정 → 발송 안 함

    return ""



def _load_history_set():

    sent = set()

    if HISTORY.exists():

        with open(HISTORY, "r", encoding="utf-8") as f:

            for line in f:

                line = line.strip()

                if not line:

                    continue

                try:

                    obj = json.loads(line)

                    sent.add(obj.get("key",""))

                except Exception:

                    continue

    return sent



def _append_history(key: str, meta: dict):

    HISTORY.parent.mkdir(parents=True, exist_ok=True)

    obj = {

        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "key": key,

        **meta,

    }

    with open(HISTORY, "a", encoding="utf-8") as f:

        f.write(json.dumps(obj, ensure_ascii=False) + "\n")



def _make_key(row: dict) -> str:

    # 공고 식별자 후보(없으면 내용 해시)

    bid = _pick(row, ["공고번호","bidNtceNo","bid_no","notice_no","공고ID","id"])

    ordv = _pick(row, ["차수","bidNtceOrd","ord","notice_ord"])

    code = _pick(row, ["공종","공종코드","업종코드","indstrytyCd","ind_code"])

    name = _pick(row, ["공고명","bidNtceNm","제목","title"])

    base = f"{bid}-{ordv}-{code}-{name}"

    if base.strip("-") == "":

        base = json.dumps(row, ensure_ascii=False, sort_keys=True)

    return hashlib.sha1(base.encode("utf-8")).hexdigest()



def _build_message(row: dict, region_for_msg: str) -> str:

    name = _pick(row, ["공고명","bidNtceNm","제목","title"])

    deadline = _pick(row, ["입찰마감일시","bidClseDt","마감","close_dt","마감일시"])

    joint_rgn = _pick(row, ["공동도급지역","jntcontrctDutyRgnNm1","공동도급","공동도급지역명"])

    joint_rt = _pick(row, ["공동도급비율","rgnDutyJntcontrctRt","비율","공동도급비율(%)"])

    amt = _pick(row, ["추정금액","presmptPrce","기초금액","bdgtAmt","금액"])

    bidno = _pick(row, ["공고번호","bidNtceNo","notice_no","bid_no"])

    ordv = _pick(row, ["차수","bidNtceOrd","ord","notice_ord"])



    if joint_rgn == "":

        joint_rgn = region_for_msg or ""

    if joint_rt == "":

        joint_rt = "해당없음"

    if joint_rgn == "":

        joint_rgn = "해당없음"



    # 메시지 포맷(너가 원하던 스타일 유지)

    msg = (

        "[세리공영]\n\n"

        f"공고명 : {name}\n"

        f"입찰마감일시 : {deadline}\n"

        f"공동도급지역 : {joint_rgn}\n"

        f"공동도급비율 : {joint_rt}\n"

        f"추정금액 : {amt}\n"

        f"공고번호 : {bidno}"

    )

    if ordv:

        msg += f" - {ordv}"

    return msg



# ---------------------------

# 발송 함수(기존 n_data 모듈 재사용)

# ---------------------------

def _send_kakao(message: str, phones: list) -> dict:

    """

    1순위: /home/pi/n_data 쪽 카카오 발송 모듈이 있으면 재사용

    - kakao_send_tb0485.send_for_item(receiver, fields, dry_run=False) 패턴을 최대한 흉내

    실패하면 예외 발생.

    """

    # PYTHONPATH를 /home/pi/n_data로 잡아둔 상태에서 import 시도

    try:

        from kakao_send_tb0485 import send_for_item as kakao_send_for_item  # type: ignore

    except Exception as e:

        raise RuntimeError(f"kakao_send_tb0485 import failed: {e}")



    ok = 0

    fail = 0

    for p in phones:

        try:

            receiver = _norm_phone(p)

            # fields는 기존 send_for_item 구현에 따라 달라질 수 있어,

            # 우선 message만 전달하는 형태가 지원되도록 최대한 단순화

            fields = {"msg": message, "message": message, "text": message}

            kakao_send_for_item(receiver, fields, dry_run=False)

            ok += 1

        except Exception:

            fail += 1

    return {"sent_ok": ok, "sent_fail": fail}



def process_csv(csv_path: Path, sent_set: set) -> dict:

    sent_cnt = 0

    skip_cnt = 0

    err_cnt = 0



    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:

            code = _pick(row, ["공종","공종코드","업종코드","indstrytyCd","ind_code"])

            code = (code or "").strip()

            if code not in CODES_ALL:

                continue



            # 지역 문자열 후보들(없으면 스킵)

            region_raw = _pick(row, ["대표지역","지역","참가가능지역","prtcptLmtRgnNm","prtcptLmtRgnNm1","prtcptLmtRgnNm2","prtcptLmtRgnNm3","prtcptLmtRgnNm4","prtcptLmtRgnNm5","지역명"])

            region = _classify_region(region_raw)



            # 룰에 맞는 수신자 결정

            phones = []

            if code == "0037":

                if region == "전국":

                    phones = RECIP_0037_NATION[:]

                else:

                    phones = []

            else:

                if region in RECIP_GENERAL:

                    phones = RECIP_GENERAL[region][:]

                else:

                    phones = []



            if not phones:

                # 룰 미해당은 스킵

                continue



            key = _make_key(row)

            if key in sent_set:

                skip_cnt += 1

                continue



            msg = _build_message(row, region)

            try:

                res = _send_kakao(msg, phones)

                # 한 명이라도 성공이면 발송 처리로 간주

                if res.get("sent_ok", 0) > 0:

                    sent_set.add(key)

                    _append_history(key, {

                        "csv": str(csv_path),

                        "code": code,

                        "region": region,

                        "phones": phones,

                        "sent_ok": res.get("sent_ok", 0),

                        "sent_fail": res.get("sent_fail", 0),

                    })

                    sent_cnt += 1

                else:

                    err_cnt += 1

            except Exception as e:

                err_cnt += 1

                # 실패 로그는 별도 파일로 남김

                BASE_DIR.mkdir(parents=True, exist_ok=True)

                with open(BASE_DIR / "notify_errors.log", "a", encoding="utf-8") as ef:

                    ef.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} SEND_FAIL csv={csv_path} err={e}\n")



    return {"sent_rows": sent_cnt, "skip_rows": skip_cnt, "err_rows": err_cnt}



def main():

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    sent_set = _load_history_set()



    # BASE_DIR 내 최신 CSV들 처리(너무 많아지는 경우 대비: 최신 30개만)

    csvs = sorted(BASE_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime)

    csvs = csvs[-30:]



    total = {"sent_rows": 0, "skip_rows": 0, "err_rows": 0, "files": 0}

    for p in csvs:

        r = process_csv(p, sent_set)

        total["sent_rows"] += r["sent_rows"]

        total["skip_rows"] += r["skip_rows"]

        total["err_rows"] += r["err_rows"]

        total["files"] += 1



    print(f"[LAND_NOTIFY] files={total['files']} sent_rows={total['sent_rows']} skip_rows={total['skip_rows']} err_rows={total['err_rows']}")



if __name__ == "__main__":

    main()

