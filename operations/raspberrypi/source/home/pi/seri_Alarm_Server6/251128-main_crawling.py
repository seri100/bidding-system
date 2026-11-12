try:
    import db_disable_patch  # optional
except Exception:
    pass  # disable DB

# --- FTP FALLBACK (auto) ---

try:

    from ftp_stub import upload_csv_via_ftp, upload_file_via_ftp

except Exception:

    def upload_csv_via_ftp(*args, **kwargs):

        print("[WARN] ftp_stub not found: upload_csv_via_ftp skipped.", args, kwargs)

        return None

    def upload_file_via_ftp(*args, **kwargs):

        print("[WARN] ftp_stub not found: upload_file_via_ftp skipped.", args, kwargs)

        return None

# --- END FTP FALLBACK ---

# === DB DISABLE PATCH (auto-inserted) ===
import os
from pathlib import Path

# --- IN_CSV_DIR guard (auto) ---

IN_CSV_DIR = os.getenv("IN_CSV_DIR", "/VOL1")

if not Path(IN_CSV_DIR).exists():

    alt = "REDACTED_PRIVATE_VALUE"

    if Path(alt).exists():

        print(f"[WARN] IN_CSV_DIR missing: {IN_CSV_DIR} -> fallback: {alt}")

        IN_CSV_DIR = alt

CSV_PATTERNS = [os.getenv("IN_CSV_GLOB", "LH*.csv"), "LH_*.csv", "LH공사-신규입찰공고-*.csv"]

def _iter_csv_files(base):

    seen = set()

    for pat in CSV_PATTERNS:

        for f in glob(str(Path(base) / pat)):

            if f not in seen:

                seen.add(f)

                yield f

# --- END IN_CSV_DIR guard (auto) ---

# --- RECENCY GUARDS (auto) ---

from datetime import datetime, timedelta

import re as _re



def _file_dt_from_name(path):

    name = os.path.basename(path)

    m = _re.search(r'(\d{8})', name)

    if m:

        try:

            return datetime.strptime(m.group(1), "%Y%m%d")

        except Exception:

            pass

    try:

        return datetime.fromtimestamp(os.path.getmtime(path))

    except Exception:

        return None

# --- END RECENCY GUARDS (auto) ---



# --- SAFE CSV LOADER (auto) ---

import pandas as _pd

def _first_nonempty_line(path, encs=("cp949","REDACTED_PRIVATE_VALUE","utf-8")):

    for enc in encs:

        try:

            with open(path, "r", encoding=enc, errors="ignore") as fh:

                for _ in range(50):

                    line = fh.readline()

                    if not line:

                        break

                    if line.strip():

                        return line.strip(), enc

        except Exception:

            pass

    return "", None

def _guess_sep(sample):

    counts = {",": sample.count(","), "	": sample.count("	"), "|": sample.count("|"), ";": sample.count(";")}

    return max(counts, key=counts.get) if sample else ","

def _load_csv_safely(path, **_kw):

    encodings = [str(_kw.pop("encoding", "")) or "cp949", "REDACTED_PRIVATE_VALUE", "utf-8"]

    seps = [str(_kw.pop("sep", "")) or ",", "	", "|", ";"]

    # 1) 빠른 샘플링으로 구분자/인코딩 가늠

    sample, enc_guess = _first_nonempty_line(path, encs=tuple(encodings))

    sep_guess = _guess_sep(sample)

    if enc_guess and encodings[0] != enc_guess:

        encodings = [enc_guess] + [e for e in encodings if e != enc_guess]

    if seps[0] != sep_guess:

        seps = [sep_guess] + [s for s in seps if s != sep_guess]

    # 2) header=0 시도 → 실패 시 header=None 폴백
    for enc in encodings:
        for sep in seps:
            # (a) header=0
            try:
                df = _pd.read_csv(path, encoding=enc, sep=sep, dtype=str, engine="python", on_bad_lines="skip")
                try:
                    df = _filter_recent_rows(df)
                except Exception as _e:
                    logging.warning("[FILTER] recent rows filter skipped: %s", _e)
                if df.shape[1] > 0:
                    return df
            except Exception:
                pass

            # (b) header=None
            try:
                df = _pd.read_csv(path, encoding=enc, sep=sep, dtype=str, engine="python",
                                  on_bad_lines="skip", header=None)
                if df.shape[1] > 0:
                    # 컬럼명 자동 생성
                    df.columns = [f"col{i+1}" for i in range(df.shape[1])]
                    return df
            except Exception:
                pass
    # 3) 최후: utf-8로 읽어 첫 줄에서 sep 추정 후 header=None

    try:

        df = _pd.read_csv(path, encoding="utf-8", sep=_guess_sep(sample), dtype=str, engine="python",

                          on_bad_lines="skip", header=None)

        if df.shape[1] > 0:

            df.columns = [f"col{i+1}" for i in range(df.shape[1])]

            return df

    except Exception:

        pass

    raise ValueError("No columns to parse after multiple attempts (header inference & none fallback tried)")

# --- END SAFE CSV LOADER (auto) ---

# --- CSV CHOOSER (auto) ---

def choose_and_load_csv():

    # FORCE_CSV 있으면 그걸 먼저 시도

    force = os.getenv("FORCE_CSV")

    if force and os.path.exists(force):

        try:

            df = _load_csv_safely(force)

            if getattr(df, "shape", (0,0))[1] >= 1:

                logging.info("[IN-CSV] using %s (FORCE_CSV)", force)

                return force, df

        except Exception as e:

            logging.warning("[IN-CSV] FORCE_CSV failed: %s", e)

    errs = []

    for f in _collect_csvs():

        try:

            print(f"[INFO] [IN-CSV] trying {f}")

            path, df = choose_and_load_csv()  # keyword 인자 무시

            # 최소 조건: 컬럼 >= 2, 행 >= 1 정도면 유효로 간주

            if getattr(df, "shape", (0,0))[1] >= 1:

                logging.info("[IN-CSV] using %s", f)

                return f, df

        except Exception as e:

            errs.append((f, str(e)))

    raise RuntimeError("No readable CSV. errors=" + repr(errs))

# --- END CSV CHOOSER (auto) ---

# --- CSV COLLECT (auto) ---

def _collect_csvs():

    try:

        files = list(_iter_csv_files(IN_CSV_DIR))

    except Exception:

        files = []

    from datetime import datetime, timedelta

    def _k(p):

        dt = _file_dt_from_name(p)

        return dt or datetime.min

    files.sort(key=_k, reverse=True)



    cleaned = []

    for f in files:

        try:

            if os.path.basename(f).startswith("land_crawl_"):

                continue

            if os.path.getsize(f) < 200:

                continue

            cleaned.append(f)

        except Exception:

            continue



    days = int(os.getenv("RECENT_FILE_DAYS", "2") or "2")

    cutoff = datetime.now() - timedelta(days=days)

    recent = [f for f in cleaned if (_file_dt_from_name(f) or cutoff) >= cutoff]



    return recent if recent else cleaned if cleaned else files

# --- END CSV COLLECT (auto) ---

from glob import glob

DB_ENABLED = os.getenv("DB_ENABLED", "true").lower() == "true"

# If DB is disabled, monkey-patch pymysql.connect to a no-op connection

if not DB_ENABLED:

    try:

        import pymysql

  # type: ignore

        class _DummyCursor:

            def execute(self, *a, **k): return 0

            def fetchone(self): return None

            def fetchall(self): return []

            def close(self): pass

        class _DummyConn:

            def cursor(self, *a, **k): return _DummyCursor()

            def commit(self): pass

            def rollback(self): pass

            def close(self): pass

        def _dummy_connect(*a, **k):

            return _DummyConn()

        pymysql.connect = _dummy_connect  # type: ignore

    except Exception:

        # If pymysql isn't present, just ignore — code won't be able to use it anyway

        pass

# === /DB DISABLE PATCH ===

# -*- coding: utf-8 -*-

"""

main_crawling.py (안정 통합본)

- .env.prod 로드, 토큰 자동 보장

- 수신자 엑셀: REDACTED_PRIVATE_VALUE (로그에 경로 출력)

- 템플릿: Alligo 서버에서 tpl_content를 받아 그대로 치환/발송(불일치 방지)

- CSV 저장: REDACTED_PRIVATE_VALUE (REDACTED_PRIVATE_VALUE)

"""

import os

import sys

import time

import logging

import pandas as pd

from datetime import datetime, timezone, timedelta

from typing import List, Dict, Any

from dotenv import load_dotenv

from alligo_token_manager import ensure_alligo_token

from alligo_client import AlligoClient

try:

 from apscheduler.schedulers.background import BackgroundScheduler

except Exception:

    BackgroundScheduler = None

# ----- 공통 -----

KST = timezone(timedelta(hours=9))

def setup_logger(level=logging.INFO):
    """
    안전한 로거 설정:
      1) /home/pi/seri_Alarm_Server6/logs 시도
      2) 안되면 /tmp/seri_Alarm_Server6_logs 로 폴백
    중복 핸들러 방지 및 UTF-8 FileHandler 적용.
    """
    base_dirs = [
        "/home/pi/seri_Alarm_Server6/logs",
        "/tmp/seri_Alarm_Server6_logs",  # fallback
    ]

    log_dir = None
    log_file = None
    last_err = None

    for d in base_dirs:
        try:
            os.makedirs(d, exist_ok=True)
            # 쓰기 테스트: 실제 FileHandler 생성까지 시도
            log_file_try = os.path.join(
                d, f"main_crawling_{datetime.now().strftime('%Y%m%d')}.log"
            )
            fh_test = logging.FileHandler(log_file_try, encoding="utf-8")
            fh_test.close()  # 생성만 확인하고 닫기 (아래서 다시 정식으로 붙임)
            log_dir = d
            log_file = log_file_try
            break
        except Exception as e:
            last_err = e
            continue

    if log_dir is None or log_file is None:
        raise RuntimeError(
            f"로그 디렉토리 생성/접근 실패: {base_dirs} / last_error={last_err}"
        )

    logger = logging.getLogger()  # root logger 사용
    logger.setLevel(level)

    # 중복 핸들러 제거
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)

    # 포맷터
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 파일 핸들러 (정식)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # 콘솔 핸들러
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 폴백으로 내려왔는지 안내
    if log_dir.startswith("/tmp/"):
        print(f"[WARN] logs 폴더 권한 문제로 {log_dir} 로 폴백했습니다. "
              f"권한 수정 후 원래 경로를 사용하려면 아래 chown/chmod 참고.")

    logger.info(f"[BOOT] logger on {log_file}")
    return log_file

def load_env():

    cwd = os.getcwd()

    prod = os.path.join(cwd, ".env.prod")

    dev  = os.path.join(cwd, ".env.dev")

    envfile = prod if os.path.exists(prod) else (dev if os.path.exists(dev) else None)

    if envfile:

        load_dotenv(envfile)

        logging.info("[ENV] loaded: %s", envfile)

    else:

        logging.warning("[ENV] .env.prod/.env.dev not found")

    return envfile

# ----- 템플릿/렌더링 -----

TEMPLATE_CODE = os.getenv("TEMPLATE_CODE", "TZ_4492")

LH_TEMPLATE = (

    "[세리공영]\n\n"

    "LH 입찰공고\n"

    "공고번호 : #{lhNo}\n"

    "업종유형 : #{lhType}\n"

    "입찰공고건명 : #{lhNm}\n"

    "기초금액 : #{lhAmount}\n"

    "참가지역 : #{lhLoc}\n"

    "입찰서접수개시일시 : #{lhStartDate}\n"

    "입찰서접수마감일시 : #{lhEndDate}"

)

class SafeDict(dict):

    def __missing__(self, key):

        return ""

def _fmt_amt(v):

    try:

        s = str(v).replace(",","").replace("원","").strip()

        if not s: return ""

        return "{:,}원".format(int(float(s)))

    except Exception:

        return str(v)

def _fmt_dt(v):

    if not v: return ""

    if isinstance(v, datetime): return v.astimezone(KST).strftime("%Y-%m-%d %H:%M")

    s = str(v).strip().replace("/", "-").replace(".", "-")

    if len(s) >= 16 and s[10] == " ": s = s[:16]

    return s

def render_msg(tpl: str, **kw) -> str:

    d = SafeDict(**kw)

    d["lhAmount"]    = _fmt_amt(d.get("lhAmount"))

    d["lhStartDate"] = _fmt_dt(d.get("lhStartDate"))

    d["lhEndDate"]   = _fmt_dt(d.get("lhEndDate"))

    msg = tpl

    for k, v in d.items():

        msg = msg.replace("#{{{}}}".format(k), str(v))

    return msg.strip()

def extract_loc(row: Dict[str, Any]) -> str:

    for k in ["참가지역1","참가지역","참가지역2","참가지역3","참가지역4"]:

        v = (row.get(k) or "").strip()

        if v: return v.split(",")[0].strip()

    dept = (row.get("공고부서") or "").strip()

    import re

    m = re.search(r"([가-힣·]+)\s*지역본부", dept)

    if m: return m.group(1).replace("·","").strip()

    return ""

import requests

def fetch_tpl_content(tpl_code: str) -> str:

    """Alligo에서 템플릿 본문을 그대로 가져와 반환(실패 시 빈문자열)."""

    try:

        params = {

            "apikey":   os.getenv("ALLIGO_APIKEY"),

            "userid":   os.getenv("ALLIGO_USERID"),

            "token":    os.getenv("ALLIGO_TOKEN"),

            "senderkey":os.getenv("ALLIGO_SENDER"),

        }

        r = requests.post("https://kakaoapi.aligo.in/akv10/template/list/", data=params, timeout=10)

        if "application/json" in r.headers.get("content-type","").lower():

            data = r.json()

            for it in (data.get("list") or []):

                if str(it.get("tpl_code")) == str(os.getenv("TEMPLATE_CODE", tpl_code)):

                    body = it.get("tpl_content","")

                    logging.info("[TPL] fetched tpl_code=%s len=%s", it.get("tpl_code"), len(body))

                    return body

    except Exception as e:

        logging.warning("[TPL] fetch failed: %s", e)

    return ""

# ----- 수신자/소스/CSV -----

def load_receivers_from_excel(xlsx: str) -> List[str]:

    if not os.path.exists(xlsx):

        logging.warning("[RECV] excel not found: %s", xlsx)

        return []

    try:

        df = pd.read_excel(xlsx, dtype=str).fillna("")

    except Exception as e:

        logging.error("[RECV] read error: %s", e)

        return []

    receivers = []

    for col in [c for c in df.columns if str(c).startswith("전화번호")]:

        for v in df[col].tolist():

            v = str(v).strip()

            if v and v not in receivers:

                receivers.append(v)

    logging.info("[RECV] loaded %d numbers", len(receivers))

    return receivers

def fetch_lh_notices() -> list:

    """가장 최신 CSV 1건을 읽어 공고 리스트 반환"""

    import os, glob, pandas as pd, logging

    in_dir   = os.getenv("LH_IN_DIR", "/VOL1")

    pattern  = os.getenv("LH_IN_PATTERN", "LH*.csv")

    encs     = [os.getenv("LH_IN_ENCODING", "cp949"), "REDACTED_PRIVATE_VALUE", "utf-8"]

    files = sorted(_iter_csv_files(IN_CSV_DIR), key=lambda p: os.path.getmtime(p), reverse=True)

    if not files:

        pattern = "|".join(CSV_PATTERNS)
        in_dir = IN_CSV_DIR
        logging.info("[IN-CSV] no files in %s matching %s", in_dir, pattern)

        return []

    f = files[0]

    logging.info("[IN-CSV] using %s", f)

    df = None

    last_err = None

    for enc in encs:

        try:

            df = _load_csv_safely(f, encoding=enc)

            logging.info("[IN-CSV] read ok: %s (%d rows)", enc, len(df))

            break

        except Exception as e:

            last_err = e

    if df is None:

        logging.error("[IN-CSV] failed to read %s: %s", f, last_err)

        return []

    # 컬럼 매핑(들어오는 CSV의 컬럼명이 달라도 최대한 맞춰줌)

    colmap = {

        "공고번호": ["입찰공고번호","공고번호 "],

        "업종유형": ["공사종류","업종"],

        "입찰공고건명": ["공고명","건명","입찰공고명"],

        "기초금액": ["기초금액(원)","추정가격"],

        "참가지역": ["지역","공사위치","발주지역"],

        "입찰서접수개시일시": ["입찰개시일시","입찰서접수개시일시 "],

        "입찰서접수마감일시": ["입찰마감일시","입찰서접수마감일시 "],

        "공고부서": ["담당부서","발주부서"],

    }

    def pick(row, key):

        for name in [key] + colmap.get(key, []):

            if name in row.index:

                val = str(row.get(name, "")).strip()

                if val:

                    return val

        return ""

    rows = []

    for _, r in df.iterrows():

        rec = {k: pick(r, k) for k in colmap.keys()}

        if not rec["공고번호"]:

            continue

        rows.append(rec)

    logging.info("[IN-CSV] parsed %d rows from %s", len(rows), f)

    max_rows = int(os.getenv("LH_MAX_ROWS", "1"))

    return rows[:max_rows]

def save_notices_to_csv(rows):

    """rows(list[dict])를 CSV로 저장(REDACTED_PRIVATE_VALUE)"""

    if not rows:

        logging.info("[CSV] no rows to save; skip")

        return None

    out_dir = os.getenv("OUT_CSV_DIR") or os.getenv("OUT_DIR") or "./exports"

    os.makedirs(out_dir, exist_ok=True)

    fn = datetime.now(KST).strftime("LH_%Y%m%d_%H%M%S.csv")

    out_path = os.path.join(out_dir, fn)

    # 정리

    norm=[]

    for r in rows:

        x={}

        for k,v in (r or {}).items():

            s = "" if v is None else str(v)

            s = s.replace("\r\n"," ").replace("\n"," ").strip()

            x[str(k)] = s

        norm.append(x)

    df = pd.DataFrame(norm)

    prefer = ["공고번호","입찰공고번호","업종유형","입찰공고건명","기초금액","참가지역",

              "입찰서접수개시일시","입찰서접수마감일시","공고부서"]

    cols = [c for c in prefer if c in df.columns] + [c for c in df.columns if c not in prefer]

    df = df.loc[:, cols]

    df.to_csv(out_path, index=False, encoding="REDACTED_PRIVATE_VALUE")

    logging.info("[CSV] saved %d rows -> %s", len(df), out_path)

    return out_path

# ----- 메인 클래스 -----

class MainCrawling:

    def __init__(self):

        setup_logger()

        envfile = load_env()

        # 토큰 보장

        try:

            tok = ensure_alligo_token(env_path=envfile or ".env.prod", force=False)

            logging.info("[TOKEN] ensured (%s chars)", len(tok))

        except Exception as e:

            logging.error("[TOKEN] failed: %s", e)

            raise

        # Alligo 래퍼

        self.alligo = AlligoClient(

            apikey=os.getenv("ALLIGO_APIKEY"),

            userid=os.getenv("ALLIGO_USERID"),

            token=os.getenv("ALLIGO_TOKEN"),

            kakao_sender=os.getenv("ALLIGO_SENDER"),

            send_url=os.getenv("ALLIGO_URL"),

        )

        self.sender  = os.getenv("SENDER_PHONE", "070-0000-0000")

        self.msgHead = os.getenv("MSG_HEAD", "REDACTED_PRIVATE_VALUE")

        # 수신자 로드(경로 로그 포함)

        recv_path = os.getenv("RECEIVER_XLSX", "REDACTED_PRIVATE_VALUE")

        logging.info("[RECV] path: %s", recv_path)

        self.receiverList = load_receivers_from_excel(recv_path)

        # 스케줄 옵션

        self.scheduler = None

        if os.getenv("USE_SCHEDULER","0") == "1" and BackgroundScheduler:

            self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")

            self.scheduler.add_job(self.execute_crawling, 'cron',

                                   hour=int(os.getenv("CRON_HOUR","7")),

                                   minute=int(os.getenv("CRON_MINUTE","0")))

            self.scheduler.start()

            logging.info("[SCHED] started")

    def send_notice(self, row: Dict[str, Any]):

        if not self.receiverList:

            logging.warning("[SEND] no receivers; skip")

            return

        def pick(*ks):

            for k in ks:

                v = row.get(k, "")

                if v: return v

            return ""

        lhNo        = pick("공고번호","입찰공고번호","bidNtceCode")

        lhType      = pick("업종유형","업종")

        lhNm        = pick("입찰공고건명","공고명","공고건명")

        lhAmount    = pick("기초금액","예정가격","추정가격")

        lhLoc       = pick("참가지역1","참가지역","prtcptPsblRgnNm") or extract_loc(row)

        lhStartDate = pick("입찰서접수개시일시","접수개시일시","opengDt","입찰개시일시")

        lhEndDate   = pick("입찰서접수마감일시","접수마감일시","입찰마감일시")

        # 서버 템플릿 본문 → 치환

        tpl_body = fetch_tpl_content(TEMPLATE_CODE) or LH_TEMPLATE

        message  = render_msg(tpl_body,

                              lhNo=lhNo, lhType=lhType, lhNm=lhNm,

                              lhAmount=lhAmount, lhLoc=lhLoc,

                              lhStartDate=lhStartDate, lhEndDate=lhEndDate)

        res = self.alligo.sendTalk(

            bid_code=lhNo or lhNm,

            tpl_code=TEMPLATE_CODE,

            sender=self.sender,

            msgHead=self.msgHead,

            message=message,

            receiverList=self.receiverList,

        )

        logging.info("[SEND] %s -> %s", (lhNo or lhNm), res)

    def execute_crawling(self):

        try:

            logging.info("[RUN] start")

            rows = fetch_lh_notices()

            logging.info("[RUN] notices: %d", len(rows))

            for r in rows:

                self.send_notice(r)

            if os.getenv("SAVE_TO_CSV", "0") == "1":

                save_notices_to_csv(rows)

            csv_path = None
            if os.getenv('SAVE_TO_CSV','0')=='1':
                csv_path = save_notices_to_csv(rows)
            if os.getenv('FTP_UPLOAD','0')=='1' and csv_path:
                logging.info("[FTP] skipped: disabled");
            csv_path = None
            if os.getenv("SAVE_TO_CSV","0") == "1":
                csv_path = save_notices_to_csv(rows)
            if os.getenv("FTP_UPLOAD","0") == "1" and csv_path:
                logging.info("[FTP] skipped: disabled");
                logging.info("[RUN] done")

        except Exception as e:

            logging.exception("[RUN] error: %s", e)

# === BEGIN RUNTIME PATCH (force sender via requests.post only, guarded) ===

try:

    import requests, os, urllib.parse

    if not hasattr(requests, "_aligo_post_orig"):

        requests._aligo_post_orig = requests.post

        def _force_sender(kw):

            sender = (os.getenv("ALLIGO_SENDER_TEL","") or "").replace("-","")

            if not sender: 

                return kw

            data = kw.get("data")

            if isinstance(data, dict):

                data["sender"] = sender

                kw["data"] = data

            elif isinstance(data, (list, tuple)):

                pairs = [(k,v) for (k,v) in data if k!="sender"]

                pairs.append(("sender", sender))

                kw["data"] = pairs

            elif isinstance(data, str):

                qs = urllib.parse.parse_qsl(data, keep_blank_values=True)

                qs = [(k,v) for (k,v) in qs if k!="sender"]

                qs.append(("sender", sender))

                kw["data"] = urllib.parse.urlencode(qs, doseq=True)

            js = kw.get("json")

            if isinstance(js, dict):

                js["sender"] = sender

                kw["json"] = js

            return kw

        def _aligo_post(url, *a, **kw):

            if "kakaoapi.aligo.in/akv10/alimtalk/send" in url:

                kw = _force_sender(kw)

            resp = requests._aligo_post_orig(url, *a, **kw)

            try:

                if "kakaoapi.aligo.in/akv10/alimtalk/send" in url:

                    os.makedirs("logs", exist_ok=True)

                    # 요청 본문 프리뷰 저장(민감정보 주의)

                    form_preview = ""

                    d = kw.get("data")

                    if isinstance(d, dict):

                        form_preview = "&".join([f"{k}={d.get(k)}" for k in d])

                    elif isinstance(d, (list, tuple)):

                        form_preview = "&".join([f"{k}={v}" for k,v in d])

                    elif isinstance(d, str):

                        form_preview = d

                    with open("logs/alligo_last_request_form.txt","w",encoding="utf-8") as f: f.write(form_preview)

                    with open("logs/alligo_last_response.json","w",encoding="utf-8") as f: f.write(resp.text)

            except Exception:

                pass

            return resp

        requests.post = _aligo_post

except Exception as _e:

    pass

# === END RUNTIME PATCH (force sender via requests.post only, guarded) ===

# === BEGIN RUNTIME PATCH (single-save CSV + FTP upload) ===

import os, logging

from ftplib import FTP, FTP_TLS

# 기존 save_notices_to_csv가 여러 번 호출돼도 1번만 저장되도록 감싸기

try:

    _orig_save_csv = save_notices_to_csv

    def save_notices_to_csv(rows):

        if hasattr(save_notices_to_csv, "_done") and save_notices_to_csv._done:

            logging.info("[CSV] skip duplicate save (already saved once)")

            return getattr(save_notices_to_csv, "_last", None)

        path = _orig_save_csv(rows)

        save_notices_to_csv._done = True

        save_notices_to_csv._last = path

        return path

except NameError:

    pass

def upload_csv_via_ftp(local_path: str):

    host=os.getenv("FTP_HOST"); port=int(os.getenv("FTP_PORT","21"))

    user=os.getenv("FTP_USER"); pw=os.getenv("FTP_PASS")

    use_tls=os.getenv("FTP_TLS","0")=="1"

    remote_dir=os.getenv("FTP_DIR","REDACTED_PRIVATE_VALUE")

    if not local_path or not os.path.exists(local_path):

        logging.error("[FTP] local file missing: %s", local_path); return None

    if not (host and user and pw):

        logging.error("[FTP] missing host/user/pass"); return None

    ftp = FTP_TLS() if use_tls else FTP()

    ftp.connect(host, port, timeout=20); ftp.login(user, pw)

    if use_tls:

        try: ftp.prot_p()

        except Exception: pass

    try:

        ftp.encoding="utf-8"; ftp.set_pasv(True)

    except Exception:

        pass

    # 경로 보장

    parts=[p for p in remote_dir.strip("/").split("/") if p]; cur=""

    for part in parts:

        cur=cur+"/"+part

        try: ftp.mkd(cur)

        except Exception: pass

    try: ftp.cwd(remote_dir)

    except Exception as e:

        logging.error("[FTP] cwd failed: %s", e); 

        try: ftp.quit()

        except: pass

        return None

    fname=os.path.basename(local_path)

    with open(local_path,"rb") as f:

        ftp.storbinary("STOR "+fname, f)

    logging.info("[FTP] uploaded -> %s/%s", remote_dir, fname)

    try: ftp.quit()

    except: pass

    return remote_dir+"/"+fname

# 실행 흐름만 살짝 교체(요약: 크롤 → 발송 → CSV 1회 저장 → FTP 업로드)

def _patched_execute_crawling(self):

    try:

        logging.info("[RUN] start")

        rows = fetch_lh_notices()

        logging.info("[RUN] notices: %d", len(rows))

        for r in rows:

            self.send_notice(r)

        csv_path = None

        if os.getenv("SAVE_TO_CSV","0") == "1":

            csv_path = save_notices_to_csv(rows)

        if os.getenv("FTP_UPLOAD","0") == "1" and csv_path:

            logging.info("[FTP] skipped: disabled");

            logging.info("[RUN] done")

    except Exception as e:

        logging.exception("[RUN] error: %s", e)

try:

    MainCrawling.execute_crawling = _patched_execute_crawling

except Exception:

    pass

# === END RUNTIME PATCH (single-save CSV + FTP upload) ===

# === BEGIN PROD CRAWL + DB DEDUP + LOG PATCH ===

import os, io, csv, logging

from ftplib import FTP, FTP_TLS

# --- DB helpers ---

def _db_conn():

    try:

        import pymysql

        return pymysql.connect(

            host=os.getenv("DB_HOST","REDACTED_PRIVATE_VALUE"),

            user=os.getenv("DB_USER"),

            password=os.getenv("DB_PASS"),

            database=os.getenv("DB_NAME","kakao"),

            charset="utf8mb4",

            autocommit=True,

        )

    except Exception as e:

        logging.warning("[DB] connect failed: %s", e)

        return None

def db_bid_already_sent(bid_code:str)->bool:

    conn=_db_conn()

    if not conn: return False

    try:

        with conn.cursor() as c:

            c.execute("SELECT 1 FROM sent_bid WHERE bidNtceCode=%s LIMIT 1", (bid_code,))

            return c.fetchone() is not None

    except Exception as e:

        logging.warning("[DB] check sent failed: %s", e)

        return False

    finally:

        try: conn.close()

        except: pass

def db_mark_bid_sent(bid_code:str):

    conn=_db_conn()

    if not conn: return

    try:

        with conn.cursor() as c:

            c.execute("INSERT IGNORE INTO sent_bid (bidNtceCode) VALUES (%s)", (bid_code,))

    except Exception as e:

        logging.warning("[DB] mark sent failed: %s", e)

    finally:

        try: conn.close()

        except: pass

def db_log_send(bid_code, receiver, tpl_code, subject, message, code, raw_json):

    conn=_db_conn()

    if not conn: return

    try:

        with conn.cursor() as c:

            c.execute("""

INSERT INTO senddata (bidNtceCode, receiver, tpl_code, subject, message, code, raw)

VALUES (%s,%s,%s,%s,%s,%s,%s)

ON DUPLICATE KEY UPDATE code=VALUES(code), raw=VALUES(raw)

""",(bid_code, receiver, tpl_code, subject, message, code, raw_json))

    except Exception as e:

        logging.warning("[DB] log send failed: %s", e)

    finally:

        try: conn.close()

        except: pass

# --- FTP CSV ingest ---

def _ftp_connect_for_in(host,port,user,pw,use_tls=False):

    ftp = FTP_TLS() if use_tls else FTP()

    ftp.connect(host, port, timeout=20)

    ftp.login(user, pw)

    if use_tls:

        try: ftp.prot_p()

        except Exception: pass

    try:

        ftp.encoding="utf-8"; ftp.set_pasv(True)

    except Exception:

        pass

    return ftp

def _ftp_list_newest(ftp, in_dir, pattern_regex):

    import re

    ftp.cwd(in_dir)

    files = ftp.nlst()

    cand = [f for f in files if re.search(pattern_regex, f)]

    if not cand: return None

    # MDTM 지원 시 최신, 아니면 이름 정렬

    mt = []

    for f in cand:

        try:

            resp = ftp.sendcmd("MDTM "+f)  # '213 YYYYMMDDhhmmss'

            ts  = resp.split()[1]

        except Exception:

            ts  = "00000000000000"

        mt.append((ts,f))

    mt.sort(reverse=True)

    return mt[0][1]

def _ftp_get_bytes(ftp, filename):

    buf = io.BytesIO()

    ftp.retrbinary("RETR "+filename, buf.write)

    return buf.getvalue()

def _decode_csv(data: bytes):

    """

    Decode CSV bytes using preferred encodings with fallbacks.

    Honors env CSV_IN_ENCODING (default 'REDACTED_PRIVATE_VALUE'), then cp949/euc-kr/utf-8/latin-1.

    """

    prefs = [os.getenv("CSV_IN_ENCODING","REDACTED_PRIVATE_VALUE"), "cp949", "euc-kr", "utf-8", "latin-1"]

    for enc in prefs:

        try:

            text = data.decode(enc)

            logging.info("[IN-CSV] decoded with %s", enc)

            return text

        except UnicodeDecodeError:

            continue

        except Exception as e:

            logging.warning("[IN-CSV] decode try %s failed: %s", enc, e)

            continue

    logging.warning("[IN-CSV] decode failed; using utf-8(errors=replace)")

    return data.decode("utf-8", errors="replace")

# END PROD CRAWL + DB DEDUP + LOG PATCH ===

if __name__ == "__main__":

    app = MainCrawling()

    if os.getenv("RUN_ONCE","1") == "1" or app.scheduler is None:

        app.execute_crawling()

    else:

        try:

            while True: time.sleep(60)

        except KeyboardInterrupt:

            pass

# ----- FTP 업로드 -----

def _ftp_makedirs(ftp, path):

    parts = [p for p in path.strip("/").split("/") if p]

    cur = ""

    for part in parts:

        cur = cur + "/" + part

        try:

            ftp.mkd(cur)

        except Exception:

            pass  # 이미 있으면 무시

def upload_csv_via_ftp(local_path: str):

    import os, logging

    from ftplib import FTP, FTP_TLS, error_perm

    host = os.getenv("FTP_HOST")

    port = int(os.getenv("FTP_PORT","21"))

    user = os.getenv("FTP_USER")

    pw   = os.getenv("FTP_PASS")

    use_tls = os.getenv("FTP_TLS","0") == "1"

    remote_dir = os.getenv("FTP_DIR","REDACTED_PRIVATE_VALUE")

    if not host or not user or not pw:

        logging.error("[FTP] missing host/user/pass"); return None

    ftp = None

    try:

        if use_tls:

            ftp = FTP_TLS()

            ftp.connect(host, port, timeout=20)

            ftp.login(user, pw)

            try: ftp.prot_p()

            except Exception: pass

        else:

            ftp = FTP()

            ftp.connect(host, port, timeout=20)

            ftp.login(user, pw)

        try:

            ftp.encoding = "utf-8"

        except Exception:

            pass

        try: ftp.set_pasv(True)

        except Exception: pass

        _ftp_makedirs(ftp, remote_dir)

        try: ftp.cwd(remote_dir)

        except Exception as e:

            logging.error("[FTP] cwd failed: %s", e); return None

        fname = os.path.basename(local_path)

        with open(local_path, "rb") as f:

            ftp.storbinary("STOR " + fname, f)

        logging.info("[FTP] uploaded -> %s/%s", remote_dir, fname)

        try: ftp.quit()

        except Exception: pass

        return remote_dir + "/" + fname

    except Exception as e:

        logging.error("[FTP] upload failed: %s", e)

        try:

            if ftp: ftp.close()

        except Exception:

            pass

        return None

# ----- FTP 업로드 -----

def upload_csv_via_ftp(local_path: str):

    import os, logging

    from ftplib import FTP, FTP_TLS

    host = os.getenv("FTP_HOST")

    port = int(os.getenv("FTP_PORT","21"))

    user = os.getenv("FTP_USER")

    pw   = os.getenv("FTP_PASS")

    use_tls = os.getenv("FTP_TLS","0") == "1"

    remote_dir = os.getenv("FTP_DIR","REDACTED_PRIVATE_VALUE")

    if not local_path or not os.path.exists(local_path):

        logging.error("[FTP] local file missing: %s", local_path); return None

    if not host or not user or not pw:

        logging.error("[FTP] missing host/user/pass"); return None

    ftp = FTP_TLS() if use_tls else FTP()

    ftp.connect(host, port, timeout=20)

    ftp.login(user, pw)

    if use_tls:

        try: ftp.prot_p()

        except Exception: pass

    try: ftp.encoding = "utf-8"

    except Exception: pass

    try: ftp.set_pasv(True)

    except Exception: pass

    # 원격 디렉터리 보장

    parts = [p for p in remote_dir.strip("/").split("/") if p]

    cur = ""

    for part in parts:

        cur = cur + "/" + part

        try: ftp.mkd(cur)

        except Exception: pass  # 이미 있으면 무시

    ftp.cwd(remote_dir)

    fname = os.path.basename(local_path)

    with open(local_path, "rb") as f:

        ftp.storbinary("STOR " + fname, f)

    logging.info("[FTP] uploaded -> %s/%s", remote_dir, fname)

    try: ftp.quit()

    except Exception: pass

    return remote_dir + "/" + fname




def _parse_dt_flex(x):

    from datetime import datetime

    import re as _re

    if not isinstance(x, str): return None

    x = x.strip()

    for fmt in ("%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M", "%Y/%m/%d %H:%M",

                "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):

        try:

            return datetime.strptime(x, fmt)

        except Exception:

            pass

    m = _re.fullmatch(r'(\d{8})(\d{4})?', x)

    if m:

        try:

            if m.group(2):

                return datetime.strptime(m.group(1)+m.group(2), "%Y%m%d%H%M")

            return datetime.strptime(m.group(1), "%Y%m%d")

        except Exception:

            return None

    return None



def _filter_recent_rows(df):

    from datetime import datetime, timedelta

    cands = ["입찰서접수마감일시","입찰마감일시","마감일시","마감일","입찰공고일자"]

    col = next((c for c in cands if c in df.columns), None)

    if not col:

        return df

    days = int(os.getenv("RECENT_ROW_DAYS", "3") or "3")

    cutoff = datetime.now() - timedelta(days=days)

    keep = []

    for i, v in enumerate(df[col].astype(str).tolist()):

        dt = _parse_dt_flex(v)

        keep.append(bool(dt and dt >= cutoff))

    import pandas as _pd

    return df[_pd.Series(keep)].copy()



# --- REPLACE COLLECT (auto) ---

def _collect_csvs_override():

    from datetime import datetime, timedelta

    import os

    files = []

    try:

        files = list(_iter_csv_files(IN_CSV_DIR))

    except Exception:

        files = []



    # 존재하는 파일만

    files = [f for f in files if os.path.exists(f)]



    # 파일명 날짜(없으면 mtime) 기준 내림차순

    def _k(p):

        dt = _file_dt_from_name(p)

        return dt or datetime.min

    try:

        files.sort(key=_k, reverse=True)

    except Exception:

        files.sort()



    # 작은/로그 파일 제거

    cleaned = []

    for f in files:

        try:

            base = os.path.basename(f)

            if base.startswith("land_crawl_"):

                continue

            if os.path.getsize(f) < 200:

                continue

            cleaned.append(f)

        except Exception:

            continue



    # 최근 파일만 남기기

    days = int(os.getenv("RECENT_FILE_DAYS", "2") or "2")

    cutoff = datetime.now() - timedelta(days=days)

    recent = []

    for f in cleaned:

        dt = _file_dt_from_name(f)

        if dt and dt >= cutoff:

            recent.append(f)



    return recent if recent else cleaned if cleaned else files



# 기존 이름으로 바인딩

_collect_csvs = _collect_csvs_override

# --- END REPLACE COLLECT (auto) ---


