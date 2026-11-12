
#!/usr/bin/env python3

import argparse

import json

import os

import re

import socket

import sys

import time

from datetime import datetime



BASE_DIR = "/home/pi/n_data"

STATE_DIR = os.path.join(BASE_DIR, "state")

STATE_FILE = os.path.join(STATE_DIR, "error_alert_state.json")



OPERATOR = "REDACTED_PRIVATE_VALUE"

SENDER = "REDACTED_PRIVATE_VALUE"

DEDUP_SECONDS = 6 * 60 * 60





def sanitize(value):

    text = str(value or "").replace("\r", " ").replace("\n", " ")

    text = re.sub(

        r"(?i)(apikey|api_key|token|authorization|password|passwd|secret)"

        r"\s*[:=]\s*['\"]?[^,\s'\"]+",

        r"\1=***",

        text,

    )

    text = re.sub(r"\s+", " ", text).strip()

    return text[:180]





def load_state():

    try:

        with open(STATE_FILE, "r", encoding="utf-8") as f:

            data = json.load(f)

            return data if isinstance(data, dict) else {}

    except Exception:

        return {}





def save_state(state):

    os.makedirs(STATE_DIR, exist_ok=True)

    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:

        json.dump(state, f, ensure_ascii=False, indent=2)

    os.replace(temp_file, STATE_FILE)





def add_issue(issues, category, detail):

    if category not in issues:

        issues[category] = sanitize(detail)





def analyze_log(text, return_code, nas_ok):

    issues = {}



    if not nas_ok:

        add_issue(issues, "NAS", "/mnt/vol1 마운트 또는 쓰기 상태 이상")



    if return_code != 0:

        add_issue(

            issues,

            "프로그램 종료",

            "main_send.py 종료코드=%s" % return_code,

        )



    if "[MAIN] END" not in text:

        add_issue(issues, "비정상 종료", "[MAIN] END 로그 없음")



    lines = text.splitlines()



    http_pattern = re.compile(

        r"Read timed out|ConnectTimeout|ConnectionError|"

        r"Max retries exceeded|RemoteDisconnected|"

        r"Temporary failure in name resolution|"

        r"Name or service not known|Connection reset|"

        r"Connection refused|HTTPError|"

        r"\bHTTP\s*(?:status\s*)?[45][0-9]{2}\b",

        re.I,

    )



    collect_pattern = re.compile(

        r"\[(?:API|FETCH|COLLECT|REQUEST|HTTP)\]"

        r".*(?:ERROR|ERR|FAIL|FAILED)"

        r"|API.*(?:조회|수집).*(?:실패|오류)"

        r"|수집.*(?:실패|오류)",

        re.I,

    )



    storage_pattern = re.compile(

        r"Permission denied|Read-only file system|"

        r"No space left on device|Input/output error|"

        r"Stale file handle|Transport endpoint is not connected",

        re.I,

    )



    # BASIS_RETRY_RECOVERED_V1
    basis_refresh_ok = False
    if return_code == 0 and nas_ok and "[MAIN] END" in text:
        for summary_line in lines:
            if "[BASIS_REFRESH][SUMMARY]" in summary_line:
                try:
                    summary = json.loads(summary_line[summary_line.index("{"):])
                    basis_refresh_ok = summary.get("errors") == 0
                except (ValueError, TypeError):
                    basis_refresh_ok = False

    recovered_requests = set(re.findall(
        r"(?m)\[API\]\[RECOVERED\] request_id=([a-f0-9]{32})\b", text
    ))
    for line in lines:
        if "[API][RETRY]" in line:
            request_match = re.search(r"\brequest_id=([a-f0-9]{32})\s*$", line)
            if request_match and request_match.group(1) in recovered_requests:
                continue
        if (
            basis_refresh_ok
            and "[API][RETRY]" in line
            and "REDACTED_LONG_LITERAL" in line
        ):
            continue


        if http_pattern.search(line):

            add_issue(issues, "HTTP 접속", line)



        if collect_pattern.search(line):

            add_issue(issues, "수집", line)



        if "[SEND][ERR]" in line:

            add_issue(issues, "알림톡", line)



        if "[SEND] RES" in line:

            code_match = re.search(

                r"['\"]?code['\"]?\s*[:=]\s*['\"]?(-?\d+)",

                line,

                re.I,

            )

            if code_match and code_match.group(1) != "0":

                add_issue(issues, "알림톡", line)

            elif re.search(r":\s*(False|None)\s*$", line, re.I):

                add_issue(issues, "알림톡", line)



        if "[GCAL][ERROR]" in line or "[GCAL][ERR]" in line:

            add_issue(issues, "Google Calendar", line)



        if storage_pattern.search(line):

            add_issue(issues, "저장장치", line)



        if re.search(r"\[(?:SAVE|EXCEL|NAS)\].*(?:ERROR|ERR|FAIL)", line, re.I):

            add_issue(issues, "저장", line)



        if "[FATAL]" in line:

            add_issue(issues, "치명적 오류", line)



        if re.search(r"\[ERROR\]", line, re.I):

            if not re.search(r"SMS_ERROR|ALERT", line, re.I):

                add_issue(issues, "기타 오류", line)



    return issues





def send_sms(message):

    import requests

    from alligo import Alligo



    account = Alligo()



    msg_type = "SMS" if len(message.encode("utf-8")) <= 90 else "LMS"



    data = {

        "key": account.apikey,

        "user_id": account.id,

        "sender": SENDER,

        "receiver": OPERATOR,

        "msg": message,

        "msg_type": msg_type,

    }



    if msg_type == "LMS":

        data["title"] = "n_data 장애 알림"



    response = requests.post(

        "https://apis.aligo.in/send/",

        data=data,

        timeout=15,

    )



    print("[ALERT][SMS_HTTP]", response.status_code)

    print("[ALERT][SMS_RESP]", sanitize(response.text))



    response.raise_for_status()



    try:

        payload = response.json()

    except Exception:

        payload = {}



    result_code = str(payload.get("result_code", "")).strip()

    if result_code and result_code != "1":

        raise RuntimeError(

            "SMS API 실패 result_code=%s" % result_code

        )







# G2B_MAINTENANCE_NOTICE_V1

def append_g2b_maintenance_notice(message, log_text, current=None):

    from datetime import datetime, timezone, timedelta

    kst = timezone(timedelta(hours=9))

    current = current or datetime.now(kst)

    start = datetime(2026, 10, 30, 19, 0, tzinfo=kst)

    end = datetime(2026, 11, 2, 0, 0, tzinfo=kst)



    if not start <= current < end:

        return message



    failed = any(

        "BidPublicInfoService/" in line

        and (

            "[API][ERR]" in line

            or "API collection incomplete" in line

        )

        for line in str(log_text or "").splitlines()

    )

    if not failed:

        return message



    return message + (

        "\n나라장터 점검 중"

        "\n기간: 2026-10-30 19:00 ~ 2026-11-02 00:00 (한국시간)"

    )





# G2B_RECOVERY_NOTICE_V1

def notify_g2b_recovery(text, return_code, nas_ok, dry_run=False,

                        current=None):

    from datetime import datetime, timezone, timedelta

    kst = timezone(timedelta(hours=9))

    end = datetime(2026, 11, 2, 0, 0, tzinfo=kst)

    current = current or datetime.now(kst)



    if current < end:

        return False



    # 과거 정상 로그를 오인하지 않도록 마지막 실행만 검사

    starts = list(re.finditer(

        r"(?m)^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] START\b",

        text or ""

    ))

    if not starts:

        return False



    latest = starts[-1]

    started = datetime.strptime(

        latest.group(1), "%Y-%m-%d %H:%M:%S"

    ).replace(tzinfo=kst)

    run = text[latest.start():]



    if started < end or started > current:

        return False



    if return_code != 0 or not nas_ok:

        return False



    if not re.search(r"(?m)^\[[^\n]+\] \[MAIN\] END\s*$", run):

        return False

    if not re.search(r"END \(RET=0 NAS_OK=1\)", run):

        return False



    # API 조회 완료 증거도 확인

    required = ("PPSSrch", "Cnstwk", "PrtcptPsblRgn")

    if not all(

        re.search(r"\[COLLECT\] " + name + r" rows=\d+", run)

        for name in required

    ):

        return False

    if "[FATAL]" in run or "[API][ERR]" in run:

        return False



    key = "REDACTED_PRIVATE_VALUE"

    state = load_state()

    if state.get(key):

        return False



    message = (

        "[n_data 정상 재개]\n"

        "시각: %s\n"

        "장비: %s\n"

        "나라장터 점검 종료 후 수집 정상 재개\n"

        "확인: API 3종 조회 완료, 프로그램 정상 종료\n"

        "실행 시작: %s\n"

        "※ 캘린더 개별 등록 결과는 별도 확인"

    ) % (

        current.strftime("%Y-%m-%d %H:%M"),

        socket.gethostname(),

        latest.group(1),

    )



    if dry_run:

        print("[RECOVERY][DRY_RUN]\n" + message)

        return True



    send_sms(message)

    state[key] = current.isoformat()

    save_state(state)

    print("[RECOVERY][SENT] 나라장터 수집 정상 재개")

    return True



def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--log", default="")

    parser.add_argument("--return-code", type=int, default=0)

    parser.add_argument("--nas-ok", type=int, default=1)

    parser.add_argument("--dry-run", action="store_true")

    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()



    if args.test:

        issues = {

            "시험": "n_data 장애문자 기능 설치 시험입니다."

        }

    else:

        try:

            with open(

                args.log,

                "r",

                encoding="utf-8",

                errors="replace",

            ) as f:

                text = f.read()

        except Exception as exc:

            text = ""

            args.return_code = args.return_code or 1

            issues = {

                "감시로그": "실행 로그 읽기 실패: %s" % exc

            }

        else:

            issues = analyze_log(

                text,

                args.return_code,

                bool(args.nas_ok),

            )



    if not args.test:
        notify_g2b_recovery(
            locals().get("text", ""), args.return_code,
            bool(args.nas_ok), args.dry_run
        )

    collection_failed = False
    failure_detail = ""
    if not args.test:
        run_text = locals().get("text", "")
        collection_failed = args.return_code != 0 and "[COLLECTION][COMPLETE]" not in run_text and (
            "[MAIN] period " in run_text or "[COLLECTION][BACKFILL]" in run_text
        )
        if collection_failed:
            fatal = next((line for line in reversed(run_text.splitlines()) if "[FATAL]" in line), "")
            failed = next((line for line in reversed(run_text.splitlines())
                           if "[API][REQUEST_FAILED]" in line), "")
            failure_detail = sanitize(failed if "API collection incomplete" in fatal and failed else fatal)
        elif (args.return_code == 0 and args.nas_ok
              and "[COLLECTION][COMPLETE]" in run_text and "[MAIN] END" in run_text):
            recovery_state = load_state()
            if recovery_state.get("collection_outage_alerted"):
                recovery_message = "[n_data 정상 재개]\n나라장터 공고 수집 정상 완료\n시각: %s" % datetime.now().strftime("%Y-%m-%d %H:%M")
                if args.dry_run:
                    print("[RECOVERY][DRY_RUN]", recovery_message)
                else:
                    send_sms(recovery_message)
                    recovery_state.pop("collection_outage_alerted", None)
                    save_state(recovery_state)
                    print("[RECOVERY][SENT] collection restored")

    if not issues:

        print("[ALERT] 이상 없음")

        return 0



    categories = sorted(issues.keys())

    fingerprint = "|".join(categories)

    now = int(time.time())



    state = load_state()

    last_sent = int(

        state.get("sent", {}).get(fingerprint, 0) or 0

    )



    if not args.test and now - last_sent < DEDUP_SECONDS:

        remain = DEDUP_SECONDS - (now - last_sent)

        print(

            "[ALERT][DEDUP_SKIP] categories=%s remain=%ss"

            % (fingerprint, remain)

        )

        return 0



    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")

    category_text = ", ".join(categories)

    first_detail = failure_detail or issues[categories[0]]



    message = (

        "[n_data 장애]\n"

        "시각: %s\n"

        "장비: %s\n"

        "구분: %s\n"

        "내용: %s"

        % (

            now_text,

            socket.gethostname(),

            category_text,

            first_detail,

        )

    )



    if not args.test:
        message = append_g2b_maintenance_notice(
            message, locals().get("text", "")
        )

    if args.dry_run:

        print("[ALERT][DRY_RUN]")

        print(message)

        return 0



    send_sms(message)



    state.setdefault("sent", {})[fingerprint] = now

    state["last_message"] = message

    state["last_sent_at"] = now_text
    if collection_failed:
        state["collection_outage_alerted"] = True

    save_state(state)



    print("[ALERT][SENT] categories=%s" % fingerprint)

    return 0





if __name__ == "__main__":

    try:

        sys.exit(main())

    except Exception as exc:

        print("[ALERT][ERROR]", sanitize(exc))

        sys.exit(2)

