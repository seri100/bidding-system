

# ===================== [PATCH] SAVE_DIR normalize + atomic save + dedupe =====================

def _normalize_save_dir(path):

    """

    SAVE_DIR을 단일 경로로 강제:

      - /mnt/vol1/bid/gon_auto 로 고정

      - /mnt/vol1/bid/gon_auto 또는 /mnt/vol1/bid/bid/... 같은 실수 경로는 정규화

    """

    from pathlib import Path

    t = str(path)

    # 흔한 실수 케이스 정리

    t = t.replace("/mnt/vol1/bid/bid/", "/mnt/vol1/bid/")

    t = t.replace(r"\mnt\vol1\bid\bid\\", r"\mnt\vol1\bid\\")

    # /mnt/vol1/bid/gon_auto 로 들어오면 /mnt/vol1/bid/gon_auto 로 통일

    if t.rstrip("/") == "/mnt/vol1/bid/gon_auto":

        t = "/mnt/vol1/bid/gon_auto"

    # 무엇이 오든 최종은 고정

    return Path("/mnt/vol1/bid/gon_auto")



def _dedupe_bids(bids):

    if not bids:

        return bids

    out = []

    seen = set()

    for b in bids:

        bn = str(b.get("공고번호", "")).strip()

        bo = str(b.get("차수", "")).strip()

        key = (bn, bo)

        if bn and bo:

            if key in seen:

                continue

            seen.add(key)

        out.append(b)

    return out



def _stable_headers(bids):

    keys = []

    seen = set()

    for b in bids:

        for k in b.keys():

            if k not in seen:

                seen.add(k)

                keys.append(k)

    return keys



def _atomic_save_workbook(wb, dst_path: str):

    import os, tempfile

    d = os.path.dirname(dst_path) or "."

    os.makedirs(d, exist_ok=True)

    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".xlsx.part", dir=d)

    os.close(fd)

    try:

        wb.save(tmp)

        if os.path.getsize(tmp) <= 0:

            raise RuntimeError("saved temp xlsx is 0 bytes")

        os.replace(tmp, dst_path)

    finally:

        try:

            if os.path.exists(tmp):

                os.remove(tmp)

        except Exception:

            pass

# ===================== [PATCH] end ===========================================================



# ===================== [PATCH] atomic save + dedupe + stable headers =====================

def _dedupe_bids(bids):

    """

    공고번호+차수 기준 중복 제거.

    bids: list[dict]

    """

    if not bids:

        return bids

    out = []

    seen = set()

    for b in bids:

        bn = str(b.get("공고번호", "")).strip()

        bo = str(b.get("차수", "")).strip()

        key = (bn, bo)

        if bn and bo:

            if key in seen:

                continue

            seen.add(key)

        out.append(b)

    return out



def _stable_headers(bids):

    """

    첫 행 dict keys만 쓰면 실행/지역별로 컬럼이 흔들릴 수 있어 union으로 고정.

    """

    keys = []

    seen = set()

    for b in bids:

        for k in b.keys():

            if k not in seen:

                seen.add(k)

                keys.append(k)

    return keys



def _atomic_save_workbook(wb, dst_path: str):

    """

    임시파일(.part)로 저장 후 os.replace로 원자적 교체 → 0바이트/부분파일 방지

    """

    import os, tempfile

    d = os.path.dirname(dst_path) or "."

    os.makedirs(d, exist_ok=True)

    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".xlsx.part", dir=d)

    os.close(fd)

    try:

        wb.save(tmp)

        # 저장된 파일이 0바이트면 교체하지 않음

        if os.path.getsize(tmp) <= 0:

            raise RuntimeError("saved temp xlsx is 0 bytes")

        os.replace(tmp, dst_path)

    finally:

        try:

            if os.path.exists(tmp):

                os.remove(tmp)

        except Exception:

            pass

# ===================== [PATCH] end ========================================================


#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import requests

import datetime



# -----------------------------

# DEDUPE (공고번호+차수) - SMS 중복 방지

# -----------------------------

from pathlib import Path as _Path



BASE_SAVE_DIR = _Path("/mnt/vol1/bid/gon_auto")

STATE_DIR = BASE_SAVE_DIR / "state"

STATE_DIR.mkdir(parents=True, exist_ok=True)



SENT_KEYS_PATH = STATE_DIR / f"sent_keys_{datetime.datetime.now().strftime('%Y%m%d')}.txt"



def _make_bid_key(bid: dict) -> str:

    # 공고번호/차수 후보 키들(파일/데이터 구조가 달라도 최대한 잡기)

    no = (bid.get("공고번호") or bid.get("bidNtceNo") or bid.get("bid_no") or bid.get("bidNtceNoNm") or "").strip()

    ordv = (bid.get("차수") or bid.get("bidNtceOrd") or bid.get("bid_ord") or "").strip()

    return f"{no}-{ordv}"



def _load_sent_keys() -> set:

    try:

        if SENT_KEYS_PATH.exists():

            return set(x.strip() for x in SENT_KEYS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip())

    except Exception:

        pass

    return set()



def _append_sent_keys(keys):

    try:

        with SENT_KEYS_PATH.open("a", encoding="utf-8") as f:

            for k in keys:

                f.write(k + "\n")

    except Exception as e:

        write_log(f"[WARN] sent_keys 기록 실패: {e}")

import json

import openpyxl

from pathlib import Path



# ---------------------------------------------------------

# 경로 설정

# ---------------------------------------------------------

BASE_DIR = Path("/home/pi/seri_Alarm_Server3")

SAVE_DIR = Path("/mnt/vol1/bid/gon_auto")



ADMIN_PHONE = "REDACTED_PRIVATE_VALUE"   # 관리자 알림 번호

LOG_FILE_PATH = None          # 실행 시 동적 설정

STATE_FILE = BASE_DIR / "gd_2512_state.txt"   # 연속 0건 체크용


# -------------------- [ALERT COOLDOWN] --------------------

ALERT_COOLDOWN_SEC = 6 * 3600  # 6 hours

ALERT_STATE_FILE = Path("/mnt/vol1/bid/gon_auto/state/gd_2512_alert_state.txt")



def _alert_allowed_now() -> bool:

    try:

        ALERT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        if ALERT_STATE_FILE.exists():

            last = int((ALERT_STATE_FILE.read_text(encoding="utf-8").strip() or "0"))

        else:

            last = 0

        now = int(time.time())

        if now - last < ALERT_COOLDOWN_SEC:

            return False

        ALERT_STATE_FILE.write_text(str(now), encoding="utf-8")

        return True

    except Exception:

        # 상태파일 문제로 알림이 완전히 막히면 더 위험하니, 예외 시에는 허용

        return True

# ----------------------------------------------------------






# =========================================================

# 로깅 함수

# =========================================================

def write_log(msg: str):

    """로그 파일 + 화면 모두 출력"""

    global LOG_FILE_PATH

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{ts}] {msg}"

    try:


        print(line)


    except BrokenPipeError:


        return
    if LOG_FILE_PATH:

        try:

            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:

                f.write(line + "\n")

        except Exception:

            pass





# =========================================================

# 설정 로드

# =========================================================

def load_api_key(filepath=BASE_DIR / "bid_api_key.txt"):

    with filepath.open("r", encoding="utf-8") as f:

        return f.read().strip()





def load_region_keywords_from_excel(filepath=BASE_DIR / "settings.xlsx"):

    wb = openpyxl.load_workbook(filepath, data_only=True)

    ws = wb.active

    raw = ws["G3"].value or ""

    return [s.strip() for s in str(raw).split(",") if s.strip()]





def load_sms_targets(filepath=BASE_DIR / "companys.xlsx"):

    wb = openpyxl.load_workbook(filepath, data_only=True)

    ws = wb.active

    targets = []

    for row in ws.iter_rows(min_row=2, values_only=True):

        region, company, phone = row[:3]

        if region and phone:

            targets.append({

                "지역": str(region).strip(),

                "업체명": str(company or "").strip(),

                "전화번호": str(phone).strip(),

            })

    return targets





def load_aligo_settings(filepath=BASE_DIR / "aligo_settings.txt"):

    settings = {}

    with filepath.open("r", encoding="utf-8") as f:

        for line in f:

            if "=" in line:

                k, v = line.strip().split("=", 1)

                settings[k.strip()] = v.strip()

    return settings.get("api_key"), settings.get("user_id"), settings.get("sender")





# =========================================================

# Slack (선택적)

# =========================================================

def notify_slack(message: str):

    """옵션: slack_settings.txt 에 webhook_url 있으면 Slack 알림"""

    settings_path = BASE_DIR / "slack_settings.txt"

    if not settings_path.exists():

        return



    webhook_url = None

    try:

        for line in settings_path.read_text(encoding="utf-8").splitlines():

            if "=" in line:

                k, v = line.strip().split("=", 1)

                if k == "webhook_url":

                    webhook_url = v.strip()

                    break

    except Exception:

        return



    if not webhook_url:

        return



    try:

        requests.post(webhook_url, json={"text": message}, timeout=5)

    except Exception as e:

        write_log(f"[SLACK][ERR] {e}")





# =========================================================

# 공공데이터 API

# =========================================================

def req_url(uri, params, api_key, timeout=30):

    full_url = uri + "?ServiceKey=" + api_key

    try:

        for _ in range(5):

            r = requests.get(full_url, params=params, timeout=timeout)

            data = r.json()

            code = data.get("response", {}).get("header", {}).get("resultCode")

            if code == "00":

                return data

        write_log(f"[WARN] API 코드!=00 → {uri}")

    except Exception as e:

        write_log(f"[ERROR] API 요청 실패: {e}")

    return None





# =========================================================

# 지역 문자용 메시지 생성

# =========================================================

def build_region_message(region: str, bids: list) -> str:

    """한 지역의 공고 수 + 대표 공고명 3개를 포함한 문자 생성"""

    count = len(bids)

    lines = [f"[{region}] {count}건의 입찰공고가 등록되었습니다."]



    for idx, bid in enumerate(bids[:3], start=1):

        title = str(bid.get("공고명", "")).strip()

        if len(title) > 30:

            title = title[:30] + "..."

        lines.append(f"{idx}) {title}")



    return "\n".join(lines)





# =========================================================

# 연속 0건 감지

# =========================================================

def update_zero_state(total_count: int) -> int:

    """연속 0건 상태 업데이트"""

    prev = 0

    try:

        if STATE_FILE.exists():

            prev = int(STATE_FILE.read_text().strip() or "0")

    except Exception:

        prev = 0



    now_val = prev + 1 if total_count == 0 else 0



    try:

        STATE_FILE.write_text(str(now_val), encoding="utf-8")

    except Exception:

        pass



    return now_val





# =========================================================

# 공고 수집 (전체 페이지)

# =========================================================

def collect_bids(api_key, codes, min_budget, region_keywords, hours=24):

    now = datetime.datetime.now()

    endtime = now.strftime("%Y%m%d%H%M")

    begintime = (now - datetime.timedelta(hours=hours)).strftime("%Y%m%d%H%M")



    write_log(f"수집 기간: {begintime} ~ {endtime}")



    URI11 = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"

    URI16 = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"



    region_bids = {r: [] for r in region_keywords}

    total_count = 0



    for code in codes:

        write_log(f"업종코드 {code} 조회 시작")

        page = 1



        while True:

            params = {

                "pageNo": page,

                "numOfRows": 999,

                "type": "json",

                "inqryDiv": "1",

                "inqryBgnDt": begintime,

                "inqryEndDt": endtime,

                "indstrytyCd": code,

            }



            result = req_url(URI11, params, api_key)

            if not result:

                write_log(f"[WARN] 업종코드 {code} page {page}: 응답 없음 → 중단")

                break



            body = result.get("response", {}).get("body", {})

            items = body.get("items", [])



            if isinstance(items, dict):

                items = [items]



            if not items:

                write_log(f"업종코드 {code} page {page}: 0건 → 종료")

                break



            write_log(f"업종코드 {code} page {page}: {len(items)}건")



            for item in items:

                if item.get("bidNtceNo", "").startswith("T"):

                    continue

                if "취소" in str(item.get("ntceKindNm", "")):

                    continue



                amt_raw = item.get("bdgtAmt") or "0"

                try:

                    amt = int(str(amt_raw).replace(",", ""))

                except Exception:

                    amt = 0



                if amt < min_budget:

                    continue



                bid = {

                    "공고명": item.get("bidNtceNm", ""),

                    "입찰공고일시": item.get("bidNtceDt", ""),

                    "입찰마감일시": item.get("bidClseDt", ""),

                    "공동도급지역1": item.get("jntcontrctDutyRgnNm1", ""),

                    "공동도급지역2": item.get("jntcontrctDutyRgnNm2", ""),

                    "공동도급지역3": item.get("jntcontrctDutyRgnNm3", ""),

                    "공동도급비율": item.get("rgnDutyJntcontrctRt", ""),

                    "공고번호": item.get("bidNtceNo", ""),

                    "차수": item.get("bidNtceOrd", ""),

                    "공종코드": code,

                    "추정금액": amt,

                }



                matched = False



                # 참가가능지역 API 대상

                if item.get("rgnDutyJntcontrctYn") != "Y":

                    params16 = {

                        "numOfRows": 10,

                        "pageNo": 1,

                        "type": "json",

                        "inqryDiv": "2",

                        "bidNtceNo": bid["공고번호"],

                        "bidNtceOrd": bid["차수"],

                    }

                    r16 = req_url(URI16, params16, api_key)

                    if r16:

                        arr = r16.get("response", {}).get("body", {}).get("items", [])

                        if isinstance(arr, dict):

                            arr = [arr]

                        if arr:

                            region_str = arr[0].get("prtcptPsblRgnNm", "")

                            for region in region_keywords:

                                if region in region_str:

                                    b = bid.copy()

                                    b["참가가능지역"] = region_str

                                    region_bids[region].append(b)

                                    matched = True



                else:  # 지역의무 공동도급

                    for region in region_keywords:

                        if any(

                            region in str(item.get(f"jntcontrctDutyRgnNm{i}", ""))

                            for i in range(1, 4)

                        ):

                            b = bid.copy()

                            b["참가가능지역"] = region

                            region_bids[region].append(b)

                            matched = True



                if matched:

                    total_count += 1



            if len(items) < 999:

                break

            page += 1



    write_log(f"필터링 후 총 건수 = {total_count}")

    for r, lst in region_bids.items():

        write_log(f"  - {r}: {len(lst)}건")



    return region_bids, total_count





# =========================================================

# 저장

# =========================================================

def save_by_region(region_bids, save_dir: Path):

    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    save_dir.mkdir(parents=True, exist_ok=True)



    wb = openpyxl.Workbook()

    default_ws = wb.active

    has_data = False



    file_path = save_dir / f"입찰공고_지역분류_{now}.xlsx"



    for region, bids in region_bids.items():

        bids = _dedupe_bids(bids)
        bids = _dedupe_bids(bids)
        if not bids:

            continue



        has_data = True

        ws = wb.create_sheet(title=region)

        headers = _stable_headers(bids)

        ws.append(headers)

        for bid in bids:

            ws.append([bid.get(k, "") for k in headers])



    if has_data:

        wb.remove(default_ws)

        _atomic_save_workbook(wb, str(file_path))

        write_log(f"저장 완료: {file_path}")

    else:

        write_log("저장할 내용 없음")





# =========================================================

# 문자 발송 (알리고)

# =========================================================

def send_sms(api_key: str, user_id: str, sender: str, receiver: str, message: str):

    url = "https://apis.aligo.in/send/"

    payload = {

        "key": api_key,

        "user_id": user_id,

        "sender": sender,

        "receiver": receiver,

        "msg": message,

        "msg_type": "SMS",

    }

    try:

        r = requests.post(url, data=payload, timeout=10)

        j = r.json()

        write_log(

            f"문자 결과: {receiver} code={j.get('result_code')} msg={j.get('message')}"

        )

    except Exception as e:

        write_log(f"[ERROR] 문자 실패 {receiver}: {e}")





# =========================================================

# 개선된 오류 문자 함수

# =========================================================

def notify_fatal_error(detail: str):

    """관리자에게 요약된 오류 문자 + Slack(있을 때)

    - 0건/필터링0건/이번실행0건/수집0건 관련은 SMS 완전 금지(운영 WARN)

    """

    # cooldown: 치명 오류용(0건은 여기서 이미 return 되므로 의미 없음)

    try:

        if not _alert_allowed_now():

            try:

                write_log("[ALERT][SKIP] cooldown active -> skip admin alert")

            except Exception:

                pass

            return

    except Exception:

        pass



    try:

        api_key, user_id, sender = load_aligo_settings()



        if not api_key or not user_id or not sender:

            write_log("[ALERT] 알리고 설정 불완전 → 문자 불가")

            return



        text = str(detail)



        # --- ZERO_SMS_BLOCK_GUARD: 0건 관련 SMS 완전 금지 ---

        zero_hit = (

            "0건" in text

            or "필터링 후 총 건수 = 0" in text

            or "이번 실행 0건" in text

            or "수집 0건" in text

        )

        if zero_hit:

            try:

                write_log(f"[ALERT][SKIP] 0건 WARN -> SMS 완전 금지 (detail={text[:160]})")

            except Exception:

                pass

            return

        # ------------------------------------------------------



        # 에러 유형 분류(치명 오류만)

        if "bid_api_key.txt" in text:

            summary = "API 키 파일 없음"

        elif "SAVE_DIR" in text or "접근 불가" in text:

            summary = "NAS(gon_auto) 접근 불가"

        elif "No such file or directory" in text:

            summary = "필요 파일 누락"

        else:

            summary = "예외 발생"



        msg = f"[gd_2512 ERROR] {summary}"



        write_log(f"[ALERT] 관리자 문자 발송 → {ADMIN_PHONE}")

        send_sms(api_key, user_id, sender, ADMIN_PHONE, msg)



        # Slack 선택적

        notify_slack(msg)



    except Exception as e:

        try:

            write_log(f"[ALERT] 오류 문자 발송 실패: {e}")

        except Exception:

            pass

# =========================================================

# SAVE_DIR 체크

# =========================================================

def check_save_dir(path: Path) -> bool:

    try:

        path.mkdir(parents=True, exist_ok=True)

        t = path / ".gd_test"

        t.write_text("ok", encoding="utf-8")

        t.unlink()

        return True

    except Exception as e:

        write_log(f"[WARN] SAVE_DIR 접근 실패: {e}")

        return False





# =========================================================

# 메인 실행

# =========================================================

if __name__ == "__main__":

    run_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")



    # 1) SAVE_DIR 점검

    if not check_save_dir(SAVE_DIR):

        local = BASE_DIR / "logs_gd2512_local"

        local.mkdir(parents=True, exist_ok=True)

        LOG_FILE_PATH = str(local / f"log_{run_ts}.txt")



        write_log("==== gd_2512.py START (SAVE_DIR 오류) ====")
        SAVE_DIR = _normalize_save_dir(SAVE_DIR)
        write_log(f"SAVE_DIR={SAVE_DIR}")

        notify_fatal_error("SAVE_DIR 접근 불가")

        write_log("==== gd_2512.py END ====")

        raise SystemExit(1)



    # 정상 로그 설정

    log_dir = SAVE_DIR / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)

    LOG_FILE_PATH = str(log_dir / f"log_{run_ts}.txt")



    write_log("==== gd_2512.py START ====")

    write_log(f"BASE_DIR={BASE_DIR}")




    try:

        API_KEY = load_api_key()

        REGION_KEYWORDS = load_region_keywords_from_excel()

        SMS_TARGETS = load_sms_targets()

        ALIGO_API_KEY, ALIGO_USER_ID, ALIGO_SENDER = load_aligo_settings()



        write_log(f"지역 키워드: {REGION_KEYWORDS}")

        write_log(f"SMS 대상 수: {len(SMS_TARGETS)}")



        CODES = ["6202", "0040", "0037", "0038", "0039"]

        MIN_BUDGET = 30_000_000



        # ---- 공고 수집 ----

        region_bids, total_count = collect_bids(

            API_KEY, CODES, MIN_BUDGET, REGION_KEYWORDS

        )



        # ---- 연속 0건 감지 ----

        zero_run = update_zero_state(total_count)

        if total_count == 0:

            write_log(f"[WARN] 이번 실행 0건 (연속 {zero_run}회)")

            if zero_run >= 2:

                write_log("[WARN] 2회 연속 수집 0건 (SMS 미발송)");
        # NOTE: 0건은 운영 WARN로만 처리(문자 폭탄 방지)


        else:

            write_log(f"[INFO] 이번 실행 총 건수: {total_count}")



        # ---- 저장 ----



        save_by_region(region_bids, SAVE_DIR)
        # ---- 지역 문자 발송 ----

        for t in SMS_TARGETS:

            region = t["지역"]

            phone = t["전화번호"]

            bids = region_bids.get(region, [])

            if not bids:

                continue



            msg = build_region_message(region, bids)

            write_log(f"문자 대상: {phone}")

            send_sms(ALIGO_API_KEY, ALIGO_USER_ID, ALIGO_SENDER, phone, msg)



        write_log("==== gd_2512.py END (정상 종료) ====")



    except Exception as e:

        write_log(f"[FATAL] gd_2512 예외 발생: {e}")

        notify_fatal_error(str(e))

        write_log("==== gd_2512.py END (예외 종료) ====")


