
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

import io

import csv

import logging

from datetime import datetime, timezone, timedelta

from typing import List, Dict, Any

from pathlib import Path

from glob import glob



import pandas as pd

import requests

from dotenv import load_dotenv



try:

    from apscheduler.schedulers.background import BackgroundScheduler

except Exception:

    BackgroundScheduler = None



# optional DB patch

try:

    import db_disable_patch  # type: ignore  # optional

except Exception:

    pass  # disable DB or ignore



# ---------------------------------------------------------------------

# FTP FALLBACK (ftp_stub 없을 때 경고만 찍고 아무 것도 안 함)

# ---------------------------------------------------------------------

try:

    from ftp_stub import upload_csv_via_ftp, upload_file_via_ftp  # type: ignore

except Exception:



    def upload_csv_via_ftp(*args, **kwargs):

        print("[WARN] ftp_stub not found: upload_csv_via_ftp skipped.", args, kwargs)

        return None



    def upload_file_via_ftp(*args, **kwargs):

        print("[WARN] ftp_stub not found: upload_file_via_ftp skipped.", args, kwargs)

        return None



# ---------------------------------------------------------------------

# DB DISABLE PATCH (환경변수 DB_ENABLED=false 이면 pymysql을 더미로 교체)

# ---------------------------------------------------------------------



DB_ENABLED = os.getenv("DB_ENABLED", "true").lower() == "true"



if not DB_ENABLED:

    try:

        import pymysql  # type: ignore



        class _DummyCursor:

            def execute(self, *a, **k):

                return 0



            def fetchone(self):

                return None



            def fetchall(self):

                return []



            def close(self):

                pass



        class _DummyConn:

            def cursor(self, *a, **k):

                return _DummyCursor()



            def commit(self):

                pass



            def rollback(self):

                pass



            def close(self):

                pass



        def _dummy_connect(*a, **k):

            return _DummyConn()



        pymysql.connect = _dummy_connect  # type: ignore

    except Exception:

        pass



# ---------------------------------------------------------------------

# IN_CSV_DIR / CSV 패턴 설정

# ---------------------------------------------------------------------



IN_CSV_DIR = os.getenv("IN_CSV_DIR", "/VOL1")



if not Path(IN_CSV_DIR).exists():

    alt = "REDACTED_PRIVATE_VALUE"

    if Path(alt).exists():

        print(f"[WARN] IN_CSV_DIR missing: {IN_CSV_DIR} -> fallback: {alt}")

        IN_CSV_DIR = alt



CSV_PATTERNS = [

    os.getenv("IN_CSV_GLOB", "LH*.csv"),

    "LH_*.csv",

    "LH공사-신규입찰공고-*.csv", '*.xlsx', 'LH*.xlsx', 'LH_*.xlsx', 'LH공사-신규입찰공고-*.xlsx']





def _iter_csv_files(base: str):

    """

    CSV_PATTERNS(리스트) 안의 패턴들을 모두 돌며 파일 목록을 yield 합니다.

    - 패턴 문자열에 '|'가 있으면 split해서 각각 glob 수행

    - 중복 경로는 제거

    """

    seen = set()

    base_path = Path(base)



    for pat in CSV_PATTERNS:

        parts = str(pat).split("|") if "|" in str(pat) else [str(pat)]

        for _pat in parts:

            _pat = str(_pat).strip()

            if not _pat:

                continue

            for f in glob(str(base_path / _pat)):

                if f not in seen:

                    seen.add(f)

                    yield f








# ---------------------------------------------------------------------

# 파일 날짜 파싱 (파일명/mtime)

# ---------------------------------------------------------------------



import re as _re





def _file_dt_from_name(path: str):

    name = os.path.basename(path)

    m = _re.search(r"(\d{8})", name)

    if m:

        try:

            return datetime.strptime(m.group(1), "%Y%m%d")

        except Exception:

            pass

    try:

        return datetime.fromtimestamp(os.path.getmtime(path))

    except Exception:

        return None





# ---------------------------------------------------------------------

# 최근 행 필터용 날짜 파서

# ---------------------------------------------------------------------





def _parse_dt_flex(x):

    if not isinstance(x, str):

        return None

    x = x.strip()

    for fmt in (

        "%Y-%m-%d %H:%M",

        "%Y.%m.%d %H:%M",

        "%Y/%m/%d %H:%M",

        "%Y-%m-%d",

        "%Y.%m.%d",

        "%Y/%m/%d",

    ):

        try:

            return datetime.strptime(x, fmt)

        except Exception:

            pass

    m = _re.fullmatch(r"(\d{8})(\d{4})?", x)

    if m:

        try:

            if m.group(2):

                return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")

            return datetime.strptime(m.group(1), "%Y%m%d")

        except Exception:

            return None

    return None





import pandas as _pd





def _filter_recent_rows(df):

    """

    CSV 안에서 '마감일/입찰마감일시' 기준으로 최근 N일(RECENT_ROW_DAYS, 기본 3일)만 남김.

    """

    cands = [

        "입찰서접수마감일시",

        "입찰마감일시",

        "마감일시",

        "마감일",

        "입찰공고일자",

    ]

    col = next((c for c in cands if c in df.columns), None)

    if not col:

        return df



    days = int(os.getenv("RECENT_ROW_DAYS", "3") or "3")

    cutoff = datetime.now() - timedelta(days=days)



    keep = []

    for _, v in enumerate(df[col].astype(str).tolist()):

        dt = _parse_dt_flex(v)

        keep.append(bool(dt and dt >= cutoff))



    return df[_pd.Series(keep)].copy()

# ---------------------------------------------------------------------

# SAFE CSV LOADER (encoding/sep 자동 추정)

# ---------------------------------------------------------------------





def _first_nonempty_line(path: str, encs=("cp949", "REDACTED_PRIVATE_VALUE", "utf-8")):

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





def _guess_sep(sample: str):

    counts = {

        ",": sample.count(","),

        "\t": sample.count("\t"),

        "|": sample.count("|"),

        ";": sample.count(";"),

    }

    return max(counts, key=counts.get) if sample else ","





def _load_csv_safely(path: str, **_kw):

    encodings = [str(_kw.pop("encoding", "")) or "cp949", "REDACTED_PRIVATE_VALUE", "utf-8"]

    seps = [str(_kw.pop("sep", "")) or ",", "\t", "|", ";"]



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

                df = _pd.read_csv(

                    path,

                    encoding=enc,

                    sep=sep,

                    dtype=str,

                    engine="python",

                    on_bad_lines="skip",

                )

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

                df = _pd.read_csv(

                    path,

                    encoding=enc,

                    sep=sep,

                    dtype=str,

                    engine="python",

                    on_bad_lines="skip",

                    header=None,

                )

                if df.shape[1] > 0:

                    df.columns = [f"col{i+1}" for i in range(df.shape[1])]

                    return df

            except Exception:

                pass



    # 3) 최후: utf-8로 읽어 첫 줄에서 sep 추정 후 header=None

    try:

        df = _pd.read_csv(

            path,

            encoding="utf-8",

            sep=_guess_sep(sample),

            dtype=str,

            engine="python",

            on_bad_lines="skip",

            header=None,

        )

        if df.shape[1] > 0:

            df.columns = [f"col{i+1}" for i in range(df.shape[1])]

            return df

    except Exception:

        pass



    raise ValueError(

        "No columns to parse after multiple attempts (header inference & none fallback tried)"

    )





# ---------------------------------------------------------------------

# CSV 목록 수집 / 최신 파일 선택

# ---------------------------------------------------------------------





def _collect_csvs():

    """

    IN_CSV_DIR에서 CSV_PATTERNS 패턴에 해당하는 파일들을 수집해 최신순으로 반환

    - _iter_csv_files(IN_CSV_DIR) 기반으로 수집 (패턴에 '|' 포함되어도 안전)

    - mtime 기준 최신순 정렬

    """

    in_dir = IN_CSV_DIR

    files = list(_iter_csv_files(in_dir))

    if not files:

        return []



    import os

    try:

        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    except Exception:

        # mtime 정렬 실패 시에는 그냥 이름 역순이라도

        files = sorted(files, reverse=True)



    return files






    def _k(p):

        dt = _file_dt_from_name(p)

        return dt or datetime.min



    try:

        files.sort(key=_k, reverse=True)

    except Exception:

        files.sort()



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





def choose_and_load_csv():

    """

    FORCE_CSV 환경변수가 있으면 그 파일 우선,

    없으면 _collect_csvs()로 찾은 후보들을 순서대로 시도.

    """

    force = os.getenv("FORCE_CSV")

    if force and os.path.exists(force):

        try:

            df = _load_csv_safely(force)

            if getattr(df, "shape", (0, 0))[1] >= 1:

                logging.info("[IN-CSV] using %s (FORCE_CSV)", force)

                return force, df

        except Exception as e:

            logging.warning("[IN-CSV] FORCE_CSV failed: %s", e)



    errs = []

    for f in _collect_csvs():

        try:

            logging.info("[IN-CSV] trying %s", f)

            df = _load_csv_safely(f)

            if getattr(df, "shape", (0, 0))[1] >= 1:

                logging.info("[IN-CSV] using %s", f)

                return f, df

        except Exception as e:

            errs.append((f, str(e)))



    raise RuntimeError("No readable CSV. errors=" + repr(errs))
# ---------------------------------------------------------------------

# 로거 / 환경 로드

# ---------------------------------------------------------------------



KST = timezone(timedelta(hours=9))





def setup_logger(level=logging.INFO):

    """

    안전한 로거 설정:

      1) /home/pi/seri_Alarm_Server6/logs 시도

      2) 안되면 /tmp/seri_Alarm_Server6_logs 로 폴백

    """

    base_dirs = [

        "/home/pi/seri_Alarm_Server6/logs",

        "/tmp/seri_Alarm_Server6_logs",

    ]



    log_dir = None

    log_file = None

    last_err = None



    for d in base_dirs:

        try:

            os.makedirs(d, exist_ok=True)

            log_file_try = os.path.join(

                d, f"main_crawling_{datetime.now().strftime('%Y%m%d')}.log"

            )

            fh_test = logging.FileHandler(log_file_try, encoding="utf-8")

            fh_test.close()

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



    logger = logging.getLogger()

    logger.setLevel(level)



    if logger.handlers:

        for h in list(logger.handlers):

            logger.removeHandler(h)



    fmt = logging.Formatter(

        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",

        datefmt="%Y-%m-%d %H:%M:%S",

    )



    fh = logging.FileHandler(log_file, encoding="utf-8")

    fh.setLevel(level)

    fh.setFormatter(fmt)

    logger.addHandler(fh)



    sh = logging.StreamHandler(sys.stdout)

    sh.setLevel(level)

    sh.setFormatter(fmt)

    logger.addHandler(sh)



    if log_dir.startswith("/tmp/"):

        print(

            f"[WARN] logs 폴더 권한 문제로 {log_dir} 로 폴백했습니다. "

            f"권한 수정 후 원래 경로를 사용하려면 chown/chmod 필요."

        )



    logger.info(f"[BOOT] logger on {log_file}")

    return log_file





def load_env():

    cwd = os.getcwd()

    prod = os.path.join(cwd, ".env.prod")

    dev = os.path.join(cwd, ".env.dev")

    envfile = prod if os.path.exists(prod) else (dev if os.path.exists(dev) else None)

    if envfile:

        load_dotenv(envfile)

        logging.info("[ENV] loaded: %s", envfile)

    else:

        logging.warning("[ENV] .env.prod/.env.dev not found")

    return envfile





# ---------------------------------------------------------------------

# 템플릿/메시지 렌더링

# ---------------------------------------------------------------------



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

        s = str(v).replace(",", "").replace("원", "").strip()

        if not s:

            return ""

        return "{:,}원".format(int(float(s)))

    except Exception:

        return str(v)





def _fmt_dt(v):

    if not v:

        return ""

    if isinstance(v, datetime):

        return v.astimezone(KST).strftime("%Y-%m-%d %H:%M")

    s = str(v).strip().replace("/", "-").replace(".", "-")

    if len(s) >= 16 and s[10] == " ":

        s = s[:16]

    return s





def render_msg(tpl: str, **kw) -> str:

    d = SafeDict(**kw)

    d["lhAmount"] = _fmt_amt(d.get("lhAmount"))

    d["lhStartDate"] = _fmt_dt(d.get("lhStartDate"))

    d["lhEndDate"] = _fmt_dt(d.get("lhEndDate"))



    msg = tpl

    for k, v in d.items():

        msg = msg.replace("#{{{}}}".format(k), str(v))

    return msg.strip()





def extract_loc(row: Dict[str, Any]) -> str:

    for k in ["참가지역1", "참가지역", "참가지역2", "참가지역3", "참가지역4"]:

        v = (row.get(k) or "").strip()

        if v:

            return v.split(",")[0].strip()



    dept = (row.get("공고부서") or "").strip()

    m = _re.search(r"([가-힣·]+)\s*지역본부", dept)

    if m:

        return m.group(1).replace("·", "").strip()

    return ""





def fetch_tpl_content(tpl_code: str) -> str:

    """Alligo에서 템플릿 본문을 그대로 가져와 반환(실패 시 빈문자열)."""

    try:

        params = {

            "apikey": os.getenv("ALLIGO_APIKEY"),

            "userid": os.getenv("ALLIGO_USERID"),

            "token": os.getenv("ALLIGO_TOKEN"),

            "senderkey": os.getenv("ALLIGO_SENDER"),

        }

        r = requests.post(

            "https://kakaoapi.aligo.in/akv10/template/list/",

            data=params,

            timeout=10,

        )

        if "application/json" in r.headers.get("content-type", "").lower():

            data = r.json()

            for it in (data.get("list") or []):

                if str(it.get("tpl_code")) == str(os.getenv("TEMPLATE_CODE", tpl_code)):

                    body = it.get("tpl_content", "")

                    logging.info(

                        "[TPL] fetched tpl_code=%s len=%s",

                        it.get("tpl_code"),

                        len(body),

                    )

                    return body

    except Exception as e:

        logging.warning("[TPL] fetch failed: %s", e)

    return ""





# ---------------------------------------------------------------------

# 수신자 엑셀 / LH CSV 로딩

# ---------------------------------------------------------------------





def load_receivers_from_excel(xlsx: str) -> List[str]:

    if not os.path.exists(xlsx):

        logging.warning("[RECV] excel not found: %s", xlsx)

        return []

    try:

        # pandas 엔진 이슈 회피: openpyxl로 직접 로딩
        import openpyxl
        _wb = openpyxl.load_workbook(xlsx, data_only=True)
        _ws = _wb.active
        _rows = list(_ws.values)
        _cols = [str(c).strip() if c is not None else '' for c in (_rows[0] if _rows else [])]
        df = pd.DataFrame(_rows[1:] if len(_rows) > 1 else [], columns=_cols).astype(str).fillna('')

    except Exception as e:

        logging.error("[RECV] read error: %s", e)

        return []



    receivers: List[str] = []

    for col in [c for c in df.columns if str(c).startswith("전화번호")]:

        for v in df[col].tolist():

            v = str(v).strip()

            if v and v not in receivers:

                receivers.append(v)

    logging.info("[RECV] loaded %d numbers", len(receivers))

    return receivers





def fetch_lh_notices() -> List[Dict[str, Any]]:


    """가장 최신 CSV 1건을 읽어 공고 리스트 반환"""

    encs = [os.getenv("LH_IN_ENCODING", "cp949"), "REDACTED_PRIVATE_VALUE", "utf-8"]



    files = list(_iter_csv_files(IN_CSV_DIR))
    if files:
        try:
            files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        except Exception:
            files = sorted(files, reverse=True)

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



    # --- 컬럼 매핑: '입찰공고번호'를 별도로 유지 ---

    colmap = {

        "공고번호": ["공고번호 ", "입찰공고번호"],

        "입찰공고번호": ["입찰공고번호", "공고번호", "공고번호 "],

        "업종유형": ["공사종류", "업종"],

        "입찰공고건명": ["공고명", "건명", "입찰공고명"],

        "기초금액": ["기초금액(원)", "추정가격"],

        "참가지역": ["지역", "공사위치", "발주지역"],

        "입찰서접수개시일시": ["입찰개시일시", "입찰서접수개시일시 "],

        "입찰서접수마감일시": ["입찰마감일시", "입찰서접수마감일시 "],

        "공고부서": ["담당부서", "발주부서"],

    }



    def pick(row, key):

        for name in [key] + colmap.get(key, []):

            if name in row.index:

                val = str(row.get(name, "")).strip()

                if val:

                    return val

        return ""



    rows: List[Dict[str, Any]] = []

    for _, r in df.iterrows():

        rec = {k: pick(r, k) for k in colmap.keys()}

        # 공고번호가 비어있으면 스킵

        if not rec["공고번호"] and not rec["입찰공고번호"]:

            continue

        rows.append(rec)



    logging.info("[IN-CSV] parsed %d rows from %s", len(rows), f)



    max_rows = int(os.getenv("LH_MAX_ROWS", "1"))

    return rows[:max_rows]





def save_notices_to_csv(rows: List[Dict[str, Any]]):

    """rows(list[dict])를 CSV로 저장(REDACTED_PRIVATE_VALUE)"""

    if not rows:

        logging.info("[CSV] no rows to save; skip")

        return None



    out_dir = os.getenv("OUT_CSV_DIR") or os.getenv("OUT_DIR") or "./exports"

    os.makedirs(out_dir, exist_ok=True)



    fn = datetime.now(KST).strftime("LH_%Y%m%d_%H%M%S.csv")

    out_path = os.path.join(out_dir, fn)



    norm: List[Dict[str, str]] = []

    for r in rows:

        x: Dict[str, str] = {}

        for k, v in (r or {}).items():

            s = "" if v is None else str(v)

            s = s.replace("\r\n", " ").replace("\n", " ").strip()

            x[str(k)] = s

        norm.append(x)



    df = pd.DataFrame(norm)



    prefer = [

        "공고번호",

        "입찰공고번호",

        "업종유형",

        "입찰공고건명",

        "기초금액",

        "참가지역",

        "입찰서접수개시일시",

        "입찰서접수마감일시",

        "공고부서",

    ]

    cols = [c for c in prefer if c in df.columns] + [

        c for c in df.columns if c not in prefer

    ]

    df = df.loc[:, cols]



    df.to_csv(out_path, index=False, encoding="REDACTED_PRIVATE_VALUE")

    logging.info("[CSV] saved %d rows -> %s", len(df), out_path)

    return out_path

# ---------------------------------------------------------------------

# Alligo Client

# ---------------------------------------------------------------------



from alligo_token_manager import ensure_alligo_token  # type: ignore

from alligo_client import AlligoClient  # type: ignore





class MainCrawling:

    def __init__(self):

        setup_logger()

        envfile = load_env()



        # --- CSV 경로/패턴 환경변수 재적용 ---

        global IN_CSV_DIR, CSV_PATTERNS

        env_dir = os.getenv("IN_CSV_DIR")

        if env_dir:

            IN_CSV_DIR = env_dir

        env_glob = os.getenv("IN_CSV_GLOB")

        if env_glob:

            # env에서 지정한 패턴을 가장 앞에 두고, 나머지 패턴은 뒤에 유지

            CSV_PATTERNS = [env_glob] + [p for p in CSV_PATTERNS if p != env_glob]

        logging.info("[IN-CSV] DIR=%s PATTERNS=%s", IN_CSV_DIR, CSV_PATTERNS)

        # ------------------------------------



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



        self.sender = os.getenv("SENDER_PHONE", "070-0000-0000")

        self.msgHead = os.getenv("MSG_HEAD", "REDACTED_PRIVATE_VALUE")



        # 수신자 로드

        recv_path = os.getenv(

            "RECEIVER_XLSX", "REDACTED_PRIVATE_VALUE"

        )

        logging.info("[RECV] path: %s", recv_path)

        self.receiverList = load_receivers_from_excel(recv_path)



        # 스케줄 옵션 (현재 systemd에서 RUN_ONCE=1로 돌려도 됨)

        self.scheduler = None

        if os.getenv("USE_SCHEDULER", "0") == "1" and BackgroundScheduler:

            self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")

            self.scheduler.add_job(

                self.execute_crawling,

                "cron",

                hour=int(os.getenv("CRON_HOUR", "7")),

                minute=int(os.getenv("CRON_MINUTE", "0")),

            )

            self.scheduler.start()

            logging.info("[SCHED] started")



    def send_notice(self, row: Dict[str, Any]):

        if not self.receiverList:

            logging.warning("[SEND] no receivers; skip")

            return



        def pick(*ks):

            for k in ks:

                v = row.get(k, "")

                if v:

                    return v

            return ""



        # --- 공고번호(입찰공고번호) 정리 ---

        # 1순위: 입찰공고번호 (예: "2503218 - 00")

        # 2순위: 공고번호

        # 3순위: bidNtceCode 등

        lhBidNo_raw = pick("입찰공고번호", "공고번호", "bidNtceCode")

        if lhBidNo_raw:

            # "2503218 - 00" → "2503218-00"

            lhNo = str(lhBidNo_raw).replace(" ", "")

        else:

            lhNo = ""



        lhType = pick("업종유형", "업종")

        lhNm = pick("입찰공고건명", "공고명", "공고건명")

        lhAmount = pick("기초금액", "예정가격", "추정가격")

        lhLoc = pick("참가지역1", "참가지역", "prtcptPsblRgnNm") or extract_loc(row)

        lhStartDate = pick("입찰서접수개시일시", "접수개시일시", "opengDt", "입찰개시일시")

        lhEndDate = pick("입찰서접수마감일시", "접수마감일시", "입찰마감일시")



        tpl_body = fetch_tpl_content(TEMPLATE_CODE) or LH_TEMPLATE

        message = render_msg(

            tpl_body,

            lhNo=lhNo,

            lhType=lhType,

            lhNm=lhNm,

            lhAmount=lhAmount,

            lhLoc=lhLoc,

            lhStartDate=lhStartDate,

            lhEndDate=lhEndDate,

        )



        # 이 bid_code 값이 DB의 bidNtceCode 에 저장됨

        # → "2503218-00" 형식으로 들어가도록 lhNo 사용

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



            csv_path = None

            if os.getenv("SAVE_TO_CSV", "0") == "1":

                csv_path = save_notices_to_csv(rows)



            if os.getenv("FTP_UPLOAD", "0") == "1" and csv_path:

                # 지금은 실제 FTP 업로드는 막아두고 로그만 남김

                logging.info("[FTP] FTP_UPLOAD=1 이지만 코드에서는 업로드를 생략했습니다.")

            logging.info("[RUN] done")



        except Exception as e:

            logging.exception("[RUN] error: %s", e)





# ---------------------------------------------------------------------

# main

# ---------------------------------------------------------------------



if __name__ == "__main__":

    app = MainCrawling()

    if os.getenv("RUN_ONCE", "1") == "1" or app.scheduler is None:

        app.execute_crawling()

    else:

        try:

            while True:

                time.sleep(60)

        except KeyboardInterrupt:

            pass
