
# -*- coding: utf-8 -*-



"""

main_send.py — 2025 통합 리팩토링 + 조달청 공고수집 collect_bids_range 버전



[실운영 경로 매칭(확정)]

- 라즈베리: /mnt/vol1/bid/n_data  (또는 /mnt/vol1/bid/bid/n_data 환경도 자동 대응)

- PC:       Z:\VOL1\bid\bid\n_data



기능 요약:

- 조달청 입찰공고 API(공사)에서 0037/0038/0039/0040/6202 업종 기준 공고 조회

- nara_public_collect.collect_bids_range 사용

- last_run.txt 기반 "연속 구간" 조회 + GRACE_MINUTES(버퍼)로 시간 경계 누락 방지

- "--hours N" 을 명시하면 last_run.txt를 무시하고 최근 N시간 강제 조회

- bidNtceNo/bidNtceOrd 기준 중복 제거 + 발송 이력 CSV로 재발송 방지

- region_filter.classify_region / decide_receivers 로 대표지역·수신자 자동 결정

- raw/split/report 엑셀 + HTML 리포트 저장 및 backup/로테이트

- 알림톡 성공/실패 로그(data_gd/kakao_logs) 자동 저장 + 실패 시 3회 재시도

- (중요) fcntl 없는 Windows에서도 돌아가도록 락 처리 분기

"""



import os

import sys

import csv

import shutil

import traceback

import argparse

from datetime import datetime, timedelta

from pathlib import Path



import pandas as pd



from kakao_send_tb0485 import send_for_item as kakao_send_for_item

from nara_public_collect import collect_bids_range

from seri_n_data.region_filter import classify_region, decide_receivers





# ---------------------------------------------

# 파일락(리눅스/윈도우 분기)

# ---------------------------------------------

try:

    import fcntl  # Linux

except Exception:

    fcntl = None



try:

    import msvcrt  # Windows

except Exception:

    msvcrt = None





# ---------------------------------------------

# 경로/파일 설정 (실운영 기준)

# ---------------------------------------------

BASE_DIR = Path("/home/pi/n_data")  # 스크립트 위치(로컬)



def _resolve_nas_base() -> Path:

    """

    우선순위:

    1) 환경변수 N_DATA_BASE

    2) /mnt/vol1/bid/n_data

    3) /mnt/vol1/bid/bid/n_data

    """

    env = os.environ.get("N_DATA_BASE", "").strip()

    if env:

        return Path(env)



    candidates = [

        Path("/mnt/vol1/bid/n_data"),

        Path("/mnt/vol1/bid/bid/n_data"),

    ]

    for p in candidates:

        if p.exists():

            return p

    return candidates[0]



NAS_BASE = _resolve_nas_base()  # ✅ 데이터/이력/락 모두 여기만 사용



STATE_FILE    = NAS_BASE / "last_run.txt"

LAST_RUN_FILE = STATE_FILE



LOCK_FILE     = NAS_BASE / "main_send.lock"

API_KEY_FILE  = NAS_BASE / "bid_api_key.txt"



RAW_DIR       = NAS_BASE / "raw"

SPLIT_DIR     = NAS_BASE / "split"

REPORT_DIR    = NAS_BASE / "report"

LOG_DIR       = NAS_BASE / "logs"



HISTORY_FILE  = NAS_BASE / "split/history/send_history.csv"



DATA_GD_DIR   = NAS_BASE / "data_gd"

KAKAO_LOG_DIR = DATA_GD_DIR / "kakao_logs"



# 필요한 폴더 자동 생성

for d in (RAW_DIR, SPLIT_DIR, REPORT_DIR, LOG_DIR, HISTORY_FILE.parent, KAKAO_LOG_DIR):

    d.mkdir(parents=True, exist_ok=True)



RUN_LOG_FILE = LOG_DIR / "run_main_send.log"



# 업종코드 / 기간 / 버퍼

TARGET_INDS = ["0037", "0038", "0039", "0040", "6202"]

MAX_DAYS = 15

GRACE_MINUTES = 3

MIN_BUDGET = 30_000_000  # 3천만 이상만 수집





# ---------------------------------------------

# 유틸

# ---------------------------------------------

def log(msg: str) -> None:

    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    line = f"{ts} {msg}"

    print(line, flush=True)

    try:

        with open(RUN_LOG_FILE, "a", encoding="utf-8") as f:

            f.write(line + "\n")

    except Exception:

        pass





def ymdhm(dt: datetime) -> str:

    return dt.strftime("%Y%m%d%H%M")





def load_api_key() -> str:

    if not API_KEY_FILE.exists():

        raise RuntimeError("API 키 파일 없음: " + str(API_KEY_FILE))

    return API_KEY_FILE.read_text().strip()





def _parse_amount(v):

    """문자/숫자 금액 → int"""

    if v is None:

        return 0

    try:

        return int(str(v).replace(",", ""))

    except Exception:

        return 0





def build_detail_url(bid_no: str, bid_ord: str) -> str:

    """나라장터 상세조회 URL (대략적인 기본형)"""

    bid_no = (bid_no or "").strip()

    bid_ord = (bid_ord or "000").strip()

    if not bid_no:

        return ""

    return (

        "https://www.g2b.go.kr:8101/ep/result/serviceList.do"

        f"?bidno={bid_no}&bidseq={bid_ord}"

    )





def _append_csv_row(path: Path, fieldnames: list, row: dict):

    path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = path.exists()

    with open(path, "a", newline="", encoding="utf-8") as f:

        w = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:

            w.writeheader()

        w.writerow(row)





# ---------------------------------------------

# Excel / 리포트 / 로테이트

# ---------------------------------------------

def save_raw_excel(rows, timestamp: str):

    if not rows:

        return None

    filename = f"입찰공고_{timestamp}.xlsx"

    out_path = RAW_DIR / filename

    df = pd.DataFrame(rows)

    try:

        df.to_excel(out_path, index=False)

        log(f"[SAVE] raw: {out_path}")

    except Exception as e:

        log(f"[SAVE][ERR] raw 엑셀 저장 실패: {e}")

        return None

    return out_path





def save_split_by_region(rows, timestamp: str):

    if not rows:

        return []

    df = pd.DataFrame(rows)

    if "대표지역" not in df.columns:

        log("[SAVE][WARN] '대표지역' 컬럼 없음 → split 생략")

        return []

    results = []

    for region in df["대표지역"].dropna().unique():

        region_df = df[df["대표지역"] == region].copy()

        fname = f"입찰공고_{timestamp}_{region}.xlsx"

        out = SPLIT_DIR / fname

        try:

            region_df.to_excel(out, index=False)

            results.append(out)

            log(f"[SAVE] split for region={region} -> {out}")

        except Exception as e:

            log(f"[SAVE][ERR] split 저장 실패({region}): {e}")

    return results





def generate_html_report(rows, timestamp: str):

    df = pd.DataFrame(rows)

    out_html = REPORT_DIR / f"입찰리포트_{timestamp}.html"

    try:

        df.to_html(out_html, index=False)

        log(f"[REPORT] HTML 생성: {out_html}")

    except Exception as e:

        log(f"[REPORT][ERR] HTML 생성 실패: {e}")

    return out_html





def generate_excel_report(rows, timestamp: str):

    df = pd.DataFrame(rows)

    out_xlsx = REPORT_DIR / f"입찰리포트_{timestamp}.xlsx"

    try:

        df.to_excel(out_xlsx, index=False)

        log(f"[REPORT] EXCEL 생성: {out_xlsx}")

    except Exception as e:

        log(f"[REPORT][ERR] EXCEL 생성 실패: {e}")

    return out_xlsx





def update_report_index():

    index_file = REPORT_DIR / "입찰리포트_index.html"

    try:

        html_files = sorted(REPORT_DIR.glob("입찰리포트_*.html"))

        lines = ["<html><body><h2>입찰 리포트 Index</h2><ul>"]

        for f in html_files:

            name = f.name

            lines.append(f'<li><a href="{name}">{name}</a></li>')

        lines.append("</ul></body></html>")

        index_file.write_text("\n".join(lines), encoding="utf-8")

        log(f"[REPORT] index HTML 갱신: {index_file}")

    except Exception as e:

        log(f"[REPORT][ERR] index 생성 실패: {e}")





def save_split_excels(rows, prtcpt_map, timestamp: str):

    # prtcpt_map 은 확장용 — 지금은 region 기준 split

    return save_split_by_region(rows, timestamp)





def save_report_files(rows, timestamp: str):

    html = generate_html_report(rows, timestamp)

    xlsx = generate_excel_report(rows, timestamp)

    update_report_index()

    return [html, xlsx]





def backup_and_rotate_excels():

    """

    1일 지난 데이터는 backup/ 하위로 이동

    15일 지난 backup/* 파일은 삭제

    """

    today = datetime.now().date()

    backup_threshold = today - timedelta(days=1)

    delete_threshold = today - timedelta(days=15)



    targets = [RAW_DIR, SPLIT_DIR, REPORT_DIR]



    for base in targets:

        if not base.exists():

            continue



        backup_dir = base / "backup"

        backup_dir.mkdir(exist_ok=True)



        # 1일 지난 파일은 backup_dir 로 이동

        for f in base.glob("*"):

            if not f.is_file():

                continue

            if f.parent == backup_dir:

                continue

            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()

            if mtime <= backup_threshold:

                dest = backup_dir / f.name

                try:

                    shutil.move(str(f), str(dest))

                    log(f"[ROTATE] backup 이동: {f} -> {dest}")

                except Exception as e:

                    log(f"[ROTATE][ERR] backup 이동 실패: {f} ({e})")



        # backup_dir 안에서 15일 지난 파일은 삭제

        for f in backup_dir.glob("*"):

            if not f.is_file():

                continue

            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()

            if mtime <= delete_threshold:

                try:

                    f.unlink()

                    log(f"[ROTATE] 오래된 backup 삭제: {f}")

                except Exception as e:

                    log(f"[ROTATE][ERR] backup 삭제 실패: {f} ({e})")
# ---------------------------------------------

# 상태(last_run) + 히스토리

# ---------------------------------------------

def load_last_run_ts():

    if not LAST_RUN_FILE.exists():

        log("[STATE] last_run.txt 없음")

        return None

    try:

        text = LAST_RUN_FILE.read_text().strip()

        if not text:

            raise ValueError("빈 last_run.txt")

        dt = datetime.strptime(text, "%Y%m%d%H%M")

        log(f"[STATE] last_run.txt 로드: {text}")

        return dt

    except Exception as e:

        log(f"[STATE][ERR] last_run.txt 파싱 실패: {e}")

        return None





def save_last_run_ts(dt):

    """

    dt: datetime 또는 'YYYYMMDDHHMM' 문자열

    """

    try:

        if isinstance(dt, str):

            ts = dt

        else:

            ts = dt.strftime("%Y%m%d%H%M")

        with open(STATE_FILE, "w", encoding="utf-8") as f:

            f.write(ts)

        log(f"[STATE] last_run.txt 저장: {ts}")

    except Exception as e:

        log(f"[STATE][ERR] last_run.txt 저장 실패: {e}")





def load_send_history(keep_days: int = 30):

    """

    발송 이력 CSV를 읽어 최근 keep_days일 이내 공고만 유지.

    key = "bid_no-bid_ord"

    """

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not HISTORY_FILE.exists():

        return set(), []



    rows = []

    try:

        with open(HISTORY_FILE, newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for r in reader:

                rows.append(r)

    except Exception as e:

        log(f"[HISTORY][ERR] load_send_history 실패: {e}")

        return set(), []



    today = datetime.now().date()

    filtered = []

    for r in rows:

        s = r.get("sent_date") or r.get("sent_dt") or ""

        if not s:

            filtered.append(r)

            continue

        try:

            d = datetime.strptime(s, "%Y%m%d").date()

        except Exception:

            filtered.append(r)

            continue

        if (today - d).days <= keep_days:

            filtered.append(r)



    keys = set()

    for r in filtered:

        bid_no = str(r.get("bid_no") or "").strip()

        bid_ord = str(r.get("bid_ord") or "").strip()

        if bid_no:

            keys.add(f"{bid_no}-{bid_ord}")



    return keys, filtered





def save_send_history(rows: list):

    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    tmp = HISTORY_FILE.with_suffix(".tmp")

    fieldnames = ["bid_no", "bid_ord", "sent_date", "sent_ts"]

    try:

        with open(tmp, "w", newline="", encoding="utf-8") as f:

            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()

            for r in rows:

                writer.writerow(

                    {

                        "bid_no": r.get("bid_no", ""),

                        "bid_ord": r.get("bid_ord", ""),

                        "sent_date": r.get("sent_date", ""),

                        "sent_ts": r.get("sent_ts", ""),

                    }

                )

        tmp.replace(HISTORY_FILE)

        log(f"[HISTORY] save_send_history OK -> {HISTORY_FILE}")

    except Exception as e:

        log(f"[HISTORY][ERR] save_send_history 실패: {e}")





# ---------------------------------------------

# 락

# ---------------------------------------------

def acquire_lock():

    try:

        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)



        # Linux

        if fcntl is not None:

            try:

                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                return fd

            except OSError:

                log("[LOCK] 이미 다른 main_send 실행 중 → 이번 실행은 건너뜀")

                os.close(fd)

                return None



        # Windows

        if msvcrt is not None:

            try:

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

                return fd

            except OSError:

                log("[LOCK] 이미 다른 main_send 실행 중 → 이번 실행은 건너뜀")

                os.close(fd)

                return None



        log("[LOCK][WARN] 파일락 모듈 없음 → 락 없이 진행")

        return fd



    except Exception as e:

        log(f"[LOCK][ERR] 락 파일 열기 실패: {e}")

        return None





# ---------------------------------------------

# 수집 → 정규화 → 지역/수신자

# ---------------------------------------------

def normalize_rows(api_rows):

    normalized = []

    for raw in api_rows:

        ind_code = str(raw.get("indstrytyCd") or "").strip()

        ind_name = str(raw.get("indstrytyNm") or "").strip()

        row = {

            "공고업종코드": ind_code,

            "공고업종명": ind_name,

            "공고번호": raw.get("bidNtceNo", ""),

            "차수": raw.get("bidNtceOrd", ""),

            "공고명": raw.get("bidNtceNm", ""),

            "입찰마감일시": raw.get("bidClseDt", ""),

            "게시일시": raw.get("bidNtceDt", ""),

            "추정금액": _parse_amount(

                raw.get("bdgtAmt")

                or raw.get("presmptPrce")

                or raw.get("indutyVAT")

                or raw.get("VAT")

            ),

            "대표지역": "",

            "수신번호": "",

            "알림대상": "",

            "원문": raw,

        }

        normalized.append(row)

    return normalized





def apply_region_classification(rows):

    for row in rows:

        raw = row.get("원문") or {}

        region_text = " ".join(

            [

                str(raw.get("jntcontrctDutyRgnNm1") or ""),

                str(raw.get("jntcontrctDutyRgnNm2") or ""),

                str(raw.get("jntcontrctDutyRgnNm3") or ""),

                str(raw.get("prtcptPsblRgnNm") or ""),

                str(raw.get("prtcptLmtRgnNm") or ""),

                str(raw.get("dlvrRgnNm") or ""),

                str(raw.get("bidNtceNm") or row.get("공고명") or ""),

            ]

        )

        rep = classify_region(region_text)

        row["대표지역"] = rep or ""





def apply_receivers(rows):

    for row in rows:

        receivers = decide_receivers(row) or []

        row["수신번호"] = ",".join(receivers) if receivers else ""

        row["알림대상"] = "Y" if receivers else "N"





def filter_rows(rows):

    out = []

    for row in rows:

        raw = row.get("원문") or {}

        bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "").strip()

        if not bid_no:

            continue



        ind = str(

            row.get("공고업종코드")

            or raw.get("indstrytyCd")

            or raw.get("indstrytyNm")

            or ""

        ).strip()

        if ind and ind not in TARGET_INDS:

            continue



        out.append(row)

    return out





def dedupe_by_bid(rows):

    seen = set()

    out = []

    for row in rows:

        raw = row.get("원문") or {}

        bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "").strip()

        bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "").strip()

        key = f"{bid_no}-{bid_ord}"

        if not bid_no:

            out.append(row)

            continue

        if key in seen:

            continue

        seen.add(key)

        out.append(row)

    return out





def _fetch_prtcpt_region_map_for_rows(rows):

    # 확장용 스텁

    return {}





def collect_data(bgn_dt_str: str, end_dt_str: str):

    start_dt = datetime.strptime(bgn_dt_str, "%Y%m%d%H%M")

    end_dt = datetime.strptime(end_dt_str, "%Y%m%d%H%M")

    api_key = load_api_key()



    log(

        f"[NARA] collect_bids_range 기간 {bgn_dt_str} ~ {end_dt_str}, "

        f"inds={TARGET_INDS}, min_budget={MIN_BUDGET}"

    )

    api_rows = collect_bids_range(

        api_key=api_key,

        indstry_codes=TARGET_INDS,

        start_dt=start_dt,

        end_dt=end_dt,

        min_budget=MIN_BUDGET,

    )



    if not api_rows:

        log("[NARA] collect_bids_range 결과 0건")

        return []



    log(f"[NARA] collect_bids_range 원시 건수 = {len(api_rows)}")



    rows = normalize_rows(api_rows)

    apply_region_classification(rows)

    apply_receivers(rows)

    rows = dedupe_by_bid(rows)



    log(f"[COLLECT] normalized+dedupe rows = {len(rows)}")

    return rows





# ---------------------------------------------

# Kakao TB_0485 필드/메시지 빌드

# ---------------------------------------------

def build_tb0485_fields(row: dict) -> dict:

    raw = row.get("원문") or {}



    def _g(*names, default=""):

        for name in names:

            if isinstance(raw, dict) and raw.get(name):

                return raw.get(name)

            if row.get(name):

                return row.get(name)

        return default



    bid_no = _g("bidNtceNo", "공고번호")

    bid_ord = _g("bidNtceOrd", "차수", default="000")



    amt_raw = _g("presmptPrce", "bdgtAmt", "추정금액", default=0)

    try:

        s = str(amt_raw).replace(",", "").strip()

        amount = int(s) if s else 0

    except Exception:

        amount = 0



    detail_url = (

        _g("bidNtceDtlUrl", "detail_url", "URL", default="")

        or build_detail_url(bid_no, bid_ord)

    )



    fields = {

        "bid_name": _g("bidNtceNm", "공고명"),

        "bid_no": bid_no,

        "bid_ord": bid_ord,

        "close_time": _g("bidClseDt", "입찰마감일시"),

        "region": _g("대표지역", "지역", default=""),

        "amount": amount,

        "org_name": _g("dminsttNm", "ntceInsttNm", "발주기관", default=""),

        "detail_url": detail_url,

    }

    return fields





# ---------------------------------------------

# Alligo TB_0485 발송 래퍼 + 재시도/로그

# ---------------------------------------------

def send_tb0485_one(phone: str, fields: dict, dry_run: bool = False) -> dict:

    bid_no = fields.get("bid_no", "")

    bid_ord = fields.get("bid_ord", "")

    bid_name = fields.get("bid_name", "")

    key = f"{bid_no}-{bid_ord}" if bid_no else ""



    log(f"[SEND] TRY TB0485 {key} / {bid_name} -> {phone}, dry_run={dry_run}")



    if dry_run:

        return {"sent": False, "dry_run": True}



    try:

        res = None

        try:

            res = kakao_send_for_item(phone, fields, dry_run=False)

        except TypeError:

            res = kakao_send_for_item(fields, phone, dry_run=False)



        log(f"[SEND] RES TB0485 {key} -> {phone}: {res}")

        ok = False
        if isinstance(res, dict):
            # {'ok': True} / {'ok': 'true'} / {'ok': '1'} 모두 성공 처리
            if str(res.get("ok", "")).strip().lower() in ("true", "1", "y", "yes"):
                ok = True
            elif res.get("sent") is True:
                ok = True
            else:
                code = str(res.get("code") or res.get("result_code") or "").strip()
                if code in ("0", "1"):
                    ok = True
                else:
                    sc = res.get("success_cnt")
                    if sc is not None and str(sc) not in ("0", "0.0", "", "None"):
                        ok = True
        elif res is True or str(res).upper() in ("OK", "SUCCESS"):
            ok = True





        return {"sent": ok, "raw": res}



    except Exception as e:

        log(f"[SEND][ERR-INNER] TB0485 {key} -> {phone}: {e}")

        return {"sent": False, "error": str(e)}





def send_tb0485_retry_and_log(phone: str, fields: dict, key: str, title: str, max_retry: int = 3) -> dict:

    """

    - TB_0485 발송을 max_retry 만큼 재시도

    - 성공/실패를 data_gd/kakao_logs 에 CSV로 누적 기록

    """

    day = datetime.now().strftime("%Y%m%d")

    ok_path = KAKAO_LOG_DIR / f"alimtalk_success_{day}.csv"

    fail_path = KAKAO_LOG_DIR / f"alimtalk_fail_{day}.csv"

    log_fields = ["ts", "key", "phone", "title", "try_no", "sent", "error", "raw"]



    last_res = None

    for i in range(1, max_retry + 1):

        res = send_tb0485_one(phone, fields, dry_run=False)

        last_res = res



        sent = bool(isinstance(res, dict) and res.get("sent") is True)

        err = ""

        raw = ""

        try:

            if isinstance(res, dict):

                err = str(res.get("error") or "")

                raw = str(res.get("raw") or "")

            else:

                raw = str(res)

        except Exception:

            pass



        row = {

            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "key": key,

            "phone": phone,

            "title": title,

            "try_no": i,

            "sent": "Y" if sent else "N",

            "error": err,

            "raw": raw[:500],

        }



        if sent:

            _append_csv_row(ok_path, log_fields, row)

            return {"sent": True, "try_no": i, "raw": res}



        _append_csv_row(fail_path, log_fields, row)



    return {"sent": False, "try_no": max_retry, "raw": last_res}
# ---------------------------------------------

# Argument 파서

# ---------------------------------------------

def parse_args():

    p = argparse.ArgumentParser()

    p.add_argument("--hours", type=int, default=1, help="기본 조회 시간(시간 단위, 기본 1시간)")

    p.add_argument("--no-send", action="store_true", help="알림톡 전송 없이 조회/저장만 수행")

    return p.parse_args()





def _user_explicitly_set_hours() -> bool:

    for arg in sys.argv[1:]:

        if arg.startswith("--hours"):

            return True

    return False





# ---------------------------------------------

# 메인

# ---------------------------------------------

def main():

    args = parse_args()

    now = datetime.now()

    now_ts = ymdhm(now)



    log("[MAIN] === main_send.py START ===")

    log(f"[CONF] NAS_BASE={NAS_BASE}")



    lock_fd = acquire_lock()

    if not lock_fd:

        log("[LOCK] 이미 실행 중인 main_send.py 가 있어서 종료합니다.")

        return



    success = False

    try:

        backup_and_rotate_excels()



        explicit_hours = _user_explicitly_set_hours()

        last_run = load_last_run_ts()



        if explicit_hours:

            hours = max(1, int(args.hours))

            start_dt = now - timedelta(hours=hours)

            log(f"[MAIN] --hours={hours} 명시 → 최근 {hours}시간 강제 조회 (last_run 무시)")

        else:

            last_dt = last_run if isinstance(last_run, datetime) else None

            today = now.date()

            first_run_today = (last_dt is None) or (last_dt.date() < today)



            if first_run_today and 6 <= now.hour <= 9:

                start_dt = datetime.combine(today - timedelta(days=1), datetime.min.time())

                log("[MAIN] 오늘 첫 실행(아침) → 전날 00:00부터 조회 (A안)")

            elif last_dt is not None:

                start_dt = last_dt - timedelta(minutes=GRACE_MINUTES)

                log(f"[MAIN] last_run 기반 조회 시작: {ymdhm(start_dt)} (버퍼 {GRACE_MINUTES}분 포함)")

            else:

                hours = args.hours if args.hours is not None else 1

                start_dt = now - timedelta(hours=hours)

                log(f"[MAIN] last_run 없음/이상 → --hours={hours} 기준 조회 적용")



        end_dt = now



        max_span = timedelta(days=MAX_DAYS)

        if end_dt - start_dt > max_span:

            adj = end_dt - max_span

            log(f"[MAIN][WARN] 조회기간이 {MAX_DAYS}일 초과 → {ymdhm(adj)}부터로 조정")

            start_dt = adj



        bgn_dt_str = ymdhm(start_dt)

        end_dt_str = ymdhm(end_dt)

        log(f"[MAIN] 조회기간 {bgn_dt_str} ~ {end_dt_str}")



        rows = collect_data(bgn_dt_str, end_dt_str)

        log(f"[FETCH] total collected rows = {len(rows)}")



        if not rows:

            log("[COLLECT] 조회 결과 없음 (rows=0)")

            save_last_run_ts(now_ts)

            success = True

            return



        rows = filter_rows(rows)

        log(f"[FILTER] 업종/기본 필터 후 rows = {len(rows)}")



        if not rows:

            log("[FILTER] 필터 후 남은 공고 없음.")

            save_last_run_ts(now_ts)

            success = True

            return



        # ✅ history 로드(저장물/발송 대상에서 “발송 완료건” 제외)

        history_keys, history_rows = load_send_history()

        before = len(rows)

        filtered_rows = []

        for r in rows:

            raw = r.get("원문") or {}

            bid_no = str(raw.get("bidNtceNo") or r.get("공고번호") or "").strip()

            bid_ord = str(raw.get("bidNtceOrd") or r.get("차수") or "000").strip()

            key = f"{bid_no}-{bid_ord}" if bid_no else ""

            if key and key in history_keys:

                continue

            filtered_rows.append(r)

        rows = filtered_rows

        log(f"[FILTER] history 기준 저장/발송 대상 제외: {before} -> {len(rows)}")



        if not rows:

            log("[FILTER] history 제외 후 남은 공고 없음.")

            save_last_run_ts(now_ts)

            success = True

            return



        prtcpt_map = {}

        try:

            prtcpt_map = _fetch_prtcpt_region_map_for_rows(rows)

        except Exception as e:

            log(f"[PRTCPT][ERR] 참가가능지역 조회 실패: {e}")



        save_raw_excel(rows, now_ts)

        save_split_excels(rows, prtcpt_map, now_ts)

        save_report_files(rows, now_ts)



        # -------------------------------------------------

        # 발송 / 중복 방지

        # -------------------------------------------------

        new_history = []

        send_cnt = 0

        skip_history = 0



        for row in rows:

            raw = row.get("원문") or {}



            bid_no = str(raw.get("bidNtceNo") or row.get("공고번호") or "").strip()

            bid_ord = str(raw.get("bidNtceOrd") or row.get("차수") or "000").strip()

            if not bid_no:

                continue



            key = f"{bid_no}-{bid_ord}"

            title = str(raw.get("bidNtceNm") or row.get("공고명") or "").strip()



            # (이 시점의 rows는 history 제외가 되었지만, 실행 중 중복 방지를 위해 한번 더 방어)

            if key in history_keys:

                skip_history += 1

                log(f"[SEND][SKIP][HISTORY] {key} / {title}")

                continue



            # ✅ apply_receivers 결과(수신번호)를 그대로 사용

            recv_csv = (row.get("수신번호") or "").strip()

            recv_list = [x.strip() for x in recv_csv.split(",") if x.strip()]



            if not recv_list:

                log(f"[SEND][SKIP][NORECV] {key} / {title}")

                continue



            fields = build_tb0485_fields(row)



            if args.no_send:

                log(f"[SAFE] DRY RUN TB0485: key={key}, receivers={recv_list}")

                continue



            ok_any = False

            ok_phones = []



            for phone in recv_list:

                try:

                    res = send_tb0485_retry_and_log(

                        phone=phone,

                        fields=fields,

                        key=key,

                        title=title,

                        max_retry=3,

                    )

                    ok = bool(isinstance(res, dict) and res.get("sent") is True)

                except Exception as e:

                    ok = False

                    log(f"[SEND][ERR] {key} -> {phone}: {e}")



                if ok:

                    ok_any = True

                    ok_phones.append(phone)

                    send_cnt += 1  # ✅ 성공한 수신자 기준 카운트



            if ok_any:

                history_keys.add(key)  # ✅ 같은 실행 내 중복 방지

                new_history.append(

                    {

                        "bid_no": bid_no,

                        "bid_ord": bid_ord,

                        "sent_date": now.strftime("%Y%m%d"),

                        "sent_ts": now_ts,

                    }

                )

                log(f"[SEND][OK] {key} / {title} -> {ok_phones}")

            else:

                log(f"[SEND][FAIL] {key} / {title} -> {recv_list}")



        if not args.no_send and new_history:

            save_send_history(history_rows + new_history)



        log(

            f"[SEND] 성공(수신자 기준)={send_cnt}, "

            f"history 신규={len(new_history)}, "

            f"history로 skip={skip_history}"

        )

        # -------------------------------------------------



        save_last_run_ts(now_ts)

        success = True



    except Exception as e:

        log(f"[FATAL] main() exception: {e}")

        log(traceback.format_exc())

    finally:

        if lock_fd:

            try:

                os.close(lock_fd)

            except Exception:

                pass

        log(f"[MAIN] === main_send.py END (success={success}) ===")





if __name__ == "__main__":

    main()
