
#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

publicdata_notice.py

- 공공데이터 포털(data.go.kr) 조달청 공고 API 다중 엔드포인트 조회(세미콜론 분리)

- 조건 필터 → 신규만 Alligo v10(토큰 방식) 알림톡 → 엑셀 저장

- ✔ 발송 성공/실패 로그 분리 (logs/success.log, logs/error.log)

"""



import os, sys, json, argparse, platform, datetime as dt, pathlib

import requests, pandas as pd

from dotenv import load_dotenv



DEFAULT_ROWS = 200



def is_windows(): return platform.system().lower().startswith("win")

def default_outdir(): return r"Z:\VOL1\bid\g2b_api" if is_windows() else "/mnt/vol1/bid/g2b_api"

def ensure_dir(p): pathlib.Path(p).mkdir(parents=True, exist_ok=True); return p



# --------- 로그 유틸 (성공/실패 분리) ----------

LOG_DIR = "/home/pi/g2b/logs"

def _ts(): return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_success(msg):

    ensure_dir(LOG_DIR)

    with open(os.path.join(LOG_DIR,"success.log"),"a",encoding="utf-8") as fp:

        fp.write(f"[{_ts()}] {msg}\n")

def log_error(msg):

    ensure_dir(LOG_DIR)

    with open(os.path.join(LOG_DIR,"error.log"),"a",encoding="utf-8") as fp:

        fp.write(f"[{_ts()}] {msg}\n")



# -------------- Alligo v10 --------------

def alligo_get_token(user_id, api_key, token_url):

    try:

        r = requests.post(token_url, data={"apikey": api_key, "userid": user_id}, timeout=10)

        r.raise_for_status()

        j = r.json() if r.headers.get("content-type","").startswith("application/json") else {}

        if isinstance(j, dict) and j.get("code") == 0 and j.get("token"):

            return True, j["token"], r.text

        if isinstance(j, dict) and j.get("token"):

            return True, j["token"], r.text

        return False, f"token_resp={r.text[:200]}", r.text

    except Exception as e:

        return False, str(e), None



def alligo_send_talk_v10(user_id, api_key, token, sender_key, sender_num, to_list, tpl_code, msg, send_url):

    data = {

        "apikey": api_key,

        "userid": user_id,

        "token": token,

        "senderkey": sender_key,

        "tpl_code": tpl_code,

        "sender": sender_num,

        "receiver_1": ",".join(to_list),

        "message_1": msg,

        "subject_1": "입찰 알림",

    }

    try:

        r = requests.post(send_url, data=data, timeout=10)

        r.raise_for_status()

        return True, r.text

    except Exception as e:

        # HTTP 에러/타임아웃 등 원문 남김

        resp = getattr(e, "response", None)

        body = ""

        if resp is not None:

            try: body = resp.text[:500]

            except Exception: body = str(resp)

        return False, f"{type(e).__name__}: {e} {body}"



def build_msg(row):

    def _fmt_num(n):

        try:

            n = int(float(str(n).replace(",","").strip()))

            return f"{n:,}"

        except Exception:

            return str(n)

    return (

        "[세리공영]\n"

        f"공고명 : {row.get('bidNtceNm','')}\n"

        f"입찰마감일시 : {row.get('bidClseDt','')}\n"

        f"공동도급지역 : {row.get('prtcptLmtRgnNm','')}\n"

        f"공동도급비율 : {row.get('jointRate','')}\n"

        f"추정금액 : {_fmt_num(row.get('presumptPrce') or row.get('amount') or 0)}\n"

        f"공고번호 : {row.get('bidNtceNo','')} - {row.get('bidNtceOrd','')}"

    )



KEEP_COLS = [

    "bidNtceNo","bidNtceOrd","bidNtceNm","bidClseDt","opengDt",

    "prtcptLmtRgnNm","jointRate","presumptPrce","amount",

    "indstrytyNm","license","indCode","insttNm","dminsttNm",

]



def normalize_records(items):

    out=[]

    for it in items:

        r=dict(it)

        r.setdefault("bidNtceOrd", r.get("bidNtceOrd") or r.get("bid_no_seq") or r.get("notinumSeq"))

        r.setdefault("bidNtceNo",  r.get("bidNtceNo")  or r.get("bid_no")     or r.get("notinum"))

        r.setdefault("bidNtceNm",  r.get("bidNtceNm")  or r.get("bid_name")   or r.get("notiName"))

        r.setdefault("bidClseDt",  r.get("bidClseDt")  or r.get("bid_end_dt") or r.get("rcptDt"))

        r.setdefault("opengDt",    r.get("opengDt")    or r.get("open_date"))

        r.setdefault("prtcptLmtRgnNm", r.get("prtcptLmtRgnNm") or r.get("region") or r.get("area"))

        r.setdefault("jointRate",  r.get("jointRate")  or r.get("joint_rate") or r.get("jointRatePct"))

        r.setdefault("presumptPrce", r.get("presumptPrce") or r.get("amount") or r.get("estAmt"))

        r.setdefault("indstrytyNm", r.get("indstrytyNm") or r.get("industry") or r.get("licenseNm"))

        r.setdefault("indCode",    r.get("indCode")    or r.get("license")    or r.get("indstCd"))

        out.append({k:r.get(k) for k in KEEP_COLS})

    return out



def parse_date(s):

    if not s: return None

    s=str(s).strip()

    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d","%Y%m%d%H%M","%Y%m%d"):

        try: return dt.datetime.strptime(s,fmt)

        except Exception: pass

    return None



def normalize_region(x: str) -> str:

    # 지역 문자열을 완화 매칭용으로 정규화: 공백 제거, 소문자

    if x is None:

        return ""

    return str(x).replace(" ", "").lower()



def _to_amount(v):

    # 'presumptPrce' or 'amount' 등 숫자화

    if v is None: return 0

    try:

        return int(float(str(v).replace(',', '').strip()))

    except Exception:

        return 0



def apply_filters(df, args):

    """

    - 마감일(due_from/due_to), 지역(args.regions), 업종(args.ind) 1차 필터

    - 비즈니스 규칙:

        * 추정금액(또는 amount) 10억 이상: 전국 허용

        * 10억 미만: 세종/충북/대구/경북 "부분 일치(완화)"일 때만 허용

    - 공고번호+차수 중복 제거

    """

    # 1) 마감일 필터

    if "bidClseDt" in df.columns:

        from datetime import datetime as _dt

        def _parse_date(s):

            if not s:

                return None

            s = str(s).strip()

            for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d","%Y%m%d%H%M","%Y%m%d"):

                try:

                    return _dt.strptime(s, fmt)

                except Exception:

                    pass

            return None

        df["bidClseDt_dt"] = df["bidClseDt"].apply(_parse_date)



        if getattr(args, "due_from", None):

            d0 = _parse_date(args.due_from)

            if d0 is not None:

                df = df[df["bidClseDt_dt"] >= d0]



        if getattr(args, "due_to", None):

            d1 = _parse_date(args.due_to)

            if d1 is not None:

                df = df[df["bidClseDt_dt"] <= d1]



    # 2) 지역 인자 필터(선택)

    if getattr(args, "regions", None):

        regs = [r.strip() for r in str(args.regions).split(",") if r.strip()]

        if regs:

            df = df[df["prtcptLmtRgnNm"].fillna("").apply(lambda v: any(r in str(v) for r in regs))]



    # 3) 업종 인자 필터(선택)

    if getattr(args, "ind", None):

        inds = [x.strip() for x in str(args.ind).split(",") if x.strip()]

        if inds:

            col = "indCode" if "indCode" in df.columns else None

            if col:

                df = df[df[col].fillna("").astype(str).apply(lambda x: any(i in x for i in inds))]



    # 4) 비즈니스 규칙(완화 지역 매칭 적용)

    #    - 10억 이상: 전국 허용

    #    - 10억 미만: allowed_tokens 부분 일치 시에만 유지

    if not df.empty:

        amt_col = "presumptPrce" if "presumptPrce" in df.columns else ("amount" if "amount" in df.columns else None)

        if amt_col:

            allowed_tokens = [

                "세종", "세종시", "세종특별자치시",

                "충북", "충청북도",

                "대구", "대구광역시",

                "경북", "경상북도",

            ]

            allowed_tokens_norm = [normalize_region(t) for t in allowed_tokens]



            def _keep(row):

                amt = _to_amount(row.get(amt_col))

                if amt >= 1_000_000_000:

                    return True

                reg_raw = row.get("prtcptLmtRgnNm") or ""

                reg = normalize_region(reg_raw)

                return any(tok in reg for tok in allowed_tokens_norm)



            df = df[df.apply(_keep, axis=1)]



    # 5) 중복 제거

    if {"bidNtceNo", "bidNtceOrd"}.issubset(df.columns):

        df = df.sort_values(["bidNtceNo","bidNtceOrd"]).drop_duplicates(["bidNtceNo","bidNtceOrd"], keep="last")



    return df

def fetch_publicdata(base, path, key, page=1, rows=DEFAULT_ROWS):

    params={"serviceKey": key, "pageNo": page, "numOfRows": rows, "_type": "json"}

    url=f"{base.rstrip('/')}{path}"

    r=requests.get(url, params=params, timeout=15)

    r.raise_for_status()

    try: return r.json()

    except Exception: return {}



def extract_items(resp):

    try: return resp["response"]["body"]["items"]["item"]

    except Exception: return []



def state_file(): return os.path.join(default_outdir(),"sent_state.json")

def load_state():

    f=state_file()

    if os.path.isfile(f):

        try: return json.load(open(f,encoding="utf-8"))

        except Exception: return {}

    return {}

def save_state(st):

    ensure_dir(os.path.dirname(state_file()))

    json.dump(st, open(state_file(),"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def bid_key(row): return f"{row.get('bidNtceNo','')}_{row.get('bidNtceOrd','')}"



def main():

    ap=argparse.ArgumentParser()

    ap.add_argument("--ind", default=None, help="업종코드 예: 0040,0039")

    ap.add_argument("--regions", default=None, help="지역 쉼표구분")

    ap.add_argument("--due_from", default=None)

    ap.add_argument("--due_to", default=None)

    ap.add_argument("--rows", type=int, default=DEFAULT_ROWS)

    ap.add_argument("--pages", type=int, default=3)

    args=ap.parse_args()



    # env

    for e in ["/home/pi/.env.g2b_api",".env"]:

        if os.path.isfile(e): load_dotenv(e)



    key=os.getenv("DATA_GO_KR_KEY")

    base=os.getenv("G2B_API_BASE","http://apis.data.go.kr")

    paths=os.getenv("G2B_API_PATHS","").split(";") if os.getenv("G2B_API_PATHS") else []

    if not key:

        print("[FATAL] DATA_GO_KR_KEY 누락"); log_error("DATA_GO_KR_KEY missing"); sys.exit(1)

    if not paths:

        print("[FATAL] G2B_API_PATHS 누락"); log_error("G2B_API_PATHS missing"); sys.exit(1)



    outdir=ensure_dir(default_outdir())

    sent=load_state()



    # 다중 엔드포인트 조회/병합

    all_items=[]

    for path in [p.strip() for p in paths if p.strip()]:

        for pno in range(1, args.pages+1):

            try:

                resp=fetch_publicdata(base, path, key, page=pno, rows=args.rows)

                items=extract_items(resp)

                print(f"[INFO] {path} page {pno}: {len(items)}건")

                if not items: break

                all_items.extend(items)

            except Exception as e:

                emsg=f"{path} page {pno} 실패: {e}"

                print(f"[WARN] {emsg}")

                log_error(emsg)

                break



    if not all_items:

        print("[INFO] 수집 0건")

        log_error("no items collected")

        return



    df=pd.DataFrame(normalize_records(all_items))

    print(f"[INFO] 정규화: {len(df)}건")

    df_f=apply_filters(df,args)

    print(f"[INFO] 필터 후: {len(df_f)}건")



    # 저장

    ts=dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    f_all=os.path.join(outdir,f"publicdata_all_{ts}.xlsx")

    f_fil=os.path.join(outdir,f"publicdata_filtered_{ts}.xlsx")

    with pd.ExcelWriter(f_all) as w: df.to_excel(w,index=False)

    with pd.ExcelWriter(f_fil) as w: df_f.to_excel(w,index=False)

    print("[SAVE]",f_all); print("[SAVE]",f_fil)



    # 알림톡(신규만)

    to=[os.getenv("ALLIGO_TO_DEFAULT","REDACTED_PHONE")]

    user_id=os.getenv("ALLIGO_USER_ID","")

    api_key=os.getenv("ALLIGO_API_KEY","")

    sender_key=os.getenv("ALLIGO_SENDERKEY","")

    sender_num=os.getenv("ALLIGO_SENDER","")

    tpl=os.getenv("ALLIGO_TMPL_CODE","")

    token_url=os.getenv("ALLIGO_TOKEN_URL","")

    send_url=os.getenv("ALLIGO_SEND_URL","")



    will=[r for _,r in df_f.iterrows() if not sent.get(bid_key(r))]

    print(f"[INFO] 신규 알림 대상: {len(will)}건")



    if user_id and api_key and sender_key and sender_num and tpl and token_url and send_url and will:

        ok, token_or_err, raw = alligo_get_token(user_id, api_key, token_url)

        if not ok:

            print("[WARN] 토큰 발급 실패:", token_or_err)

            log_error(f"token_fail: {token_or_err}")

        else:

            token=token_or_err

            log_success("token_ok")

            for r in will:

                key_id = bid_key(r)

                msg=build_msg(r)

                ok2, resp=alligo_send_talk_v10(user_id, api_key, token, sender_key, sender_num, to, tpl, msg, send_url)

                if ok2:

                    sent[key_id]=dt.datetime.now().isoformat()

                    log_success(f"SEND_OK {key_id} {r.get('bidNtceNm','')[:60]} resp={str(resp)[:120]}")

                else:

                    log_error(f"SEND_FAIL {key_id} {r.get('bidNtceNm','')[:60]} resp={str(resp)[:200]}")

            save_state(sent); print("[INFO] 발송/상태 저장 완료")

    else:

        if not will: print("[INFO] 보낼 새 항목 없음"); log_success("no new items")

        else: print("[WARN] Alligo 설정 불충분(발송 스킵)"); log_error("alligo config incomplete")



if __name__=="__main__":

    main()
