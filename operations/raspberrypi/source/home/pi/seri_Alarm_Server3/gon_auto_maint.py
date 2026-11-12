
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import os

import time

import datetime

from pathlib import Path

import traceback

import requests



BASE_DIR = Path("/home/pi/seri_Alarm_Server3")

TARGET_DIR = Path("/mnt/vol1/gon_auto")

LOG_DIR = TARGET_DIR / "logs"

SUMMARY_FILE = LOG_DIR / "log_summary.txt"

LAST_ERR_FILE = LOG_DIR / "maint_last_error.txt"   # 중복문자 방지 저장소



ADMIN_PHONE = "REDACTED_PRIVATE_VALUE"



LOG_FILE_PATH = None





def write_log(msg):

    global LOG_FILE_PATH

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{ts}] {msg}"

    print(line)

    if LOG_FILE_PATH:

        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:

            f.write(line + "\n")





def write_summary(success, detail=""):

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(SUMMARY_FILE, "a", encoding="utf-8") as f:

        if success:

            f.write(f"[{ts}] SUCCESS\n{detail}\n\n")

        else:

            f.write(f"[{ts}] FAIL\n{detail}\n\n")





def send_sms(api_key, user_id, sender, receiver, message):

    url = "https://apis.aligo.in/send/"

    payload = {

        "key": api_key,

        "user_id": user_id,

        "sender": sender,

        "receiver": receiver,

        "msg": message,

        "msg_type": "SMS",

        "title": "유지보수 오류",

    }

    try:

        r = requests.post(url, data=payload, timeout=10)

        j = r.json()

        write_log(f"[SMS] result={j}")

    except Exception as e:

        write_log(f"[SMS-ERROR] {e}")





def should_send_error_sms(msg: str) -> bool:

    if LAST_ERR_FILE.exists():

        last = LAST_ERR_FILE.read_text(encoding="utf-8").strip()

        if last == msg.strip():

            return False

    return True





def save_last_error(msg: str):

    LAST_ERR_FILE.write_text(msg.strip(), encoding="utf-8")





def load_aligo_settings(filepath=BASE_DIR / "aligo_settings.txt"):

    """

    aligo_settings.txt 예)

      api_key=xxxx

      user_id=xxxx

      sender=010xxxxxxxx

    """

    settings = {}

    try:

        with filepath.open("r", encoding="utf-8") as f:

            for line in f:

                if "=" in line:

                    k, v = line.strip().split("=", 1)

                    settings[k.strip()] = v.strip()

    except FileNotFoundError:

        write_log(f"[WARN] 알리고 설정 파일 없음: {filepath}")

    except Exception as e:

        write_log(f"[WARN] 알리고 설정 로드 실패: {e}")



    return settings.get("api_key"), settings.get("user_id"), settings.get("sender")





def _safe_stat(p: Path):

    """파일이 없거나 접근 불가면 None 반환"""

    try:

        return p.stat()

    except FileNotFoundError:

        return None

    except Exception as e:

        write_log(f"[WARN] stat 실패: {p} ({e})")

        return None





def _safe_unlink(p: Path) -> bool:

    """삭제 성공 True, 이미 없으면 False(정상), 그 외 False"""

    try:

        p.unlink()

        return True

    except FileNotFoundError:

        return False

    except Exception as e:

        write_log(f"[WARN] 삭제 실패: {p} ({e})")

        return False





def clean_old_files():

    removed_excels = 0

    removed_logs = 0

    now = time.time()



    # ✅ 엑셀 3일 초과 삭제

    for f in TARGET_DIR.glob("입찰공고_*.xlsx"):

        st = _safe_stat(f)

        if not st:

            continue

        if now - st.st_mtime > 3 * 86400:

            if _safe_unlink(f):

                removed_excels += 1



    # ✅ 로그 7일 초과 삭제

    for f in LOG_DIR.glob("log_*.txt"):

        st = _safe_stat(f)

        if not st:

            continue

        if now - st.st_mtime > 7 * 86400:

            if _safe_unlink(f):

                removed_logs += 1



    return removed_excels, removed_logs





if __name__ == "__main__":

    run_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")



    LOG_DIR.mkdir(parents=True, exist_ok=True)

    LOG_FILE_PATH = LOG_DIR / f"maint_{run_ts}.txt"



    write_log("==== gon_auto_maint.py START ====")



    try:

        exc_del, log_del = clean_old_files()



        detail = f"deleted_excels={exc_del}\ndeleted_logs={log_del}"

        write_summary(True, detail)



        write_log(detail)

        write_log("==== gon_auto_maint.py END (SUCCESS) ====")



    except Exception:

        err_msg = traceback.format_exc()

        write_log("[ERROR] 유지보수 실패\n" + err_msg)

        write_summary(False, err_msg)



        if should_send_error_sms(err_msg):

            api_key, user_id, sender = load_aligo_settings()

            if api_key and user_id and sender:

                send_sms(

                    api_key, user_id, sender,

                    ADMIN_PHONE, "[gon_auto 유지보수 ERROR] 오류 발생(로그참조)"

                )

                save_last_error(err_msg)

            else:

                write_log("[WARN] 알리고 설정 불완전 → 문자 발송 불가")



        write_log("==== gon_auto_maint.py END (FAIL) ====")


