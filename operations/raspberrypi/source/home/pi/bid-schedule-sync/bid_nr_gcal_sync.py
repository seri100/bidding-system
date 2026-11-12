#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import json
import os
import re
import sys
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path


BRIDGE_DIR = Path("/home/pi/bid-schedule-sync")
BRIDGE_FILE = BRIDGE_DIR / "institution_calendar_bridge.py"

RUNTIME_DIR = Path("/home/pi/bid-nr/runtime")
PRIVATE_PLAN = RUNTIME_DIR / "nr_gcal_staging_plan.json"

LOG_FILE = Path("/home/pi/bid-nr/logs/gcal_sync.log")

PRICE_LIMIT_WON = 1_000_000_000

BID_NO_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{6}-\d{2}\b"
)

VALID_BID_NO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{6}-\d{2}$"
)

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)


def log(message):
    line = "[%s] %s" % (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        message,
    )

    print(line, flush=True)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def clean(value):
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in ("none", "nan", "null"):
        return ""

    return text


def parse_datetime(value):
    text = clean(value)

    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass

    return None


def parse_amount(value):
    text = clean(value)
    digits = re.sub(r"[^\d]", "", text)

    if not digits:
        return None

    try:
        return int(digits)
    except Exception:
        return None


def http_status(error):
    response = getattr(error, "resp", None)
    status = getattr(response, "status", None)

    if status is not None:
        return status

    return getattr(error, "status_code", None)


def event_time_token(part):
    if not isinstance(part, dict):
        return ""

    value = clean(
        part.get("dateTime")
        or part.get("date")
    )

    # Google 응답은 +09:00이 포함될 수 있고,
    # 브리지 본문에는 로컬시각만 들어갈 수 있으므로
    # 초 단위 로컬시각까지만 비교한다.
    if "T" in value and len(value) >= 19:
        return value[:19]

    return value


def validate_item(item, bridge):
    agency = clean(item.get("기관"))

    if agency != "국가철도공단":
        return False, "국가철도공단 공고가 아님"

    action = clean(item.get("action")).lower()
    bid_no = clean(item.get("공고번호"))

    if action == "exclude":
        reason = clean(item.get("reason")) or "브리지 제외 판정"
        return False, "브리지 제외: %s" % reason

    if action not in ("create", "update"):
        return False, "처리 대상 작업이 아님: %s" % (
            action or "미확인"
        )

    if not VALID_BID_NO_RE.fullmatch(bid_no):
        return False, "공고번호 형식 이상: %s" % bid_no

    title = clean(item.get("공고명"))

    if not title:
        return False, "공고명 없음"

    if len(title) > 300:
        return False, "공고명이 비정상적으로 김: %d자" % len(title)

    # 공고명 안에 현재 공고번호와 다른 NR 공고번호가 섞이면
    # 여러 행이 합쳐진 오염 데이터로 본다.
    title_bid_numbers = set(BID_NO_RE.findall(title))
    foreign_bid_numbers = sorted(
        number
        for number in title_bid_numbers
        if number != bid_no
    )

    if foreign_bid_numbers:
        return False, (
            "공고명에 다른 공고번호 혼입: %s"
            % ",".join(foreign_bid_numbers)
        )

    start_text = clean(item.get("입찰개시일시"))
    end_text = clean(item.get("입찰마감일시"))

    start_dt = parse_datetime(start_text)
    end_dt = parse_datetime(end_text)

    if start_dt is None:
        return False, "입찰개시일시 미확인 또는 형식 오류"

    if end_dt is None:
        return False, "입찰마감일시 미확인 또는 형식 오류"

    if end_dt <= start_dt:
        return False, "입찰마감일시가 개시일시보다 빠름"

    status = clean(item.get("협정확인상태"))

    if "실패" in status:
        return False, "공식 원문 확인 실패"

    try:
        duplicate_matches = int(
            item.get("duplicate_matches") or 0
        )
    except Exception:
        duplicate_matches = 0

    if duplicate_matches > 0:
        return False, (
            "캘린더 중복 후보 존재: %d건"
            % duplicate_matches
        )

    calendar_id = clean(item.get("calendar_id"))
    expected_calendar_id = clean(
        getattr(bridge, "MAIN_CALENDAR", "")
    )

    if calendar_id != expected_calendar_id:
        return False, (
            "허용되지 않은 캘린더: %s"
            % calendar_id
        )

    if action == "update" and not clean(item.get("event_id")):
        return False, "갱신 대상 event_id 없음"

    region = clean(item.get("지역"))
    amount = parse_amount(item.get("기초금액"))

    is_gyeongbuk = (
        "경상북도" in region
        or "경북" in region
    )

    if is_gyeongbuk:
        if amount is None:
            return False, (
                "경북지역 + 금액 미확인 자동 동기화 제외"
            )

        if amount < PRICE_LIMIT_WON:
            return False, (
                "경북지역 + 10억원 미만 자동 동기화 제외: "
                "%s원" % format(amount, ",")
            )

    return True, "안전검증 통과"


def generate_private_plan(bridge):
    if not callable(getattr(bridge, "main", None)):
        raise RuntimeError(
            "institution_calendar_bridge.main()을 찾지 못했습니다."
        )

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    if PRIVATE_PLAN.exists():
        PRIVATE_PLAN.unlink()

    original_plan_file = getattr(
        bridge,
        "PLAN_FILE",
        None,
    )
    original_argv = list(sys.argv)

    output_buffer = io.StringIO()
    exit_code = 0

    try:
        # 공용 staging_calendar_plan.json을 덮어쓰지 않도록
        # NR 전용 계획파일로 교체한다.
        bridge.PLAN_FILE = PRIVATE_PLAN
        sys.argv = [
            str(BRIDGE_FILE),
            "--no-send",
        ]

        with redirect_stdout(output_buffer),\
                redirect_stderr(output_buffer):
            try:
                result = bridge.main()

                if isinstance(result, int):
                    exit_code = result
            except SystemExit as exc:
                code = exc.code

                if code in (None, 0):
                    exit_code = 0
                else:
                    try:
                        exit_code = int(code)
                    except Exception:
                        exit_code = 1

    finally:
        sys.argv = original_argv

        if original_plan_file is not None:
            bridge.PLAN_FILE = original_plan_file

    output_lines = output_buffer.getvalue().splitlines()

    if output_lines:
        log(
            "[BRIDGE] 출력 %d줄, 마지막 부분 기록"
            % len(output_lines)
        )

        for line in output_lines[-30:]:
            log("[BRIDGE] %s" % line)

    if exit_code != 0:
        raise RuntimeError(
            "브리지 계획 생성 실패: exit=%d"
            % exit_code
        )

    if not PRIVATE_PLAN.is_file():
        raise RuntimeError(
            "NR 전용 계획파일이 생성되지 않았습니다: %s"
            % PRIVATE_PLAN
        )

    payload = json.loads(
        PRIVATE_PLAN.read_text(encoding="utf-8")
    )

    if payload.get("calendar_write") is not False:
        raise RuntimeError(
            "계획 생성 단계에서 calendar_write=False가 아닙니다."
        )

    return payload


def safe_update_times(service, item, desired_body):
    calendar_id = clean(item.get("calendar_id"))
    event_id = clean(item.get("event_id"))
    bid_no = clean(item.get("공고번호"))

    try:
        current = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

    except Exception as error:
        if http_status(error) == 404:
            created = service.events().insert(
                calendarId=calendar_id,
                body=desired_body,
                sendUpdates="none",
            ).execute()

            log(
                "[CREATE][FALLBACK_404][OK] %s event=%s"
                % (
                    bid_no,
                    clean(created.get("id")),
                )
            )

            return "created"

        raise

    current_start = event_time_token(
        current.get("start")
    )
    current_end = event_time_token(
        current.get("end")
    )

    desired_start = event_time_token(
        desired_body.get("start")
    )
    desired_end = event_time_token(
        desired_body.get("end")
    )

    if (
        current_start == desired_start
        and current_end == desired_end
    ):
        log(
            "[UPDATE][NO_TIME_CHANGE] %s "
            "기존 제목·설명·수기메모 보존"
            % bid_no
        )

        return "no_change"

    # 기존 제목, 설명, 색상, 수기 협정 메모를 보존하고
    # 일정 시각만 안전하게 변경한다.
    patch_body = {
        "start": desired_body["start"],
        "end": desired_body["end"],
    }

    updated = service.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body=patch_body,
        sendUpdates="none",
    ).execute()

    log(
        "[UPDATE][TIME_ONLY][OK] %s event=%s "
        "%s~%s -> %s~%s"
        % (
            bid_no,
            clean(updated.get("id")) or event_id,
            current_start,
            current_end,
            desired_start,
            desired_end,
        )
    )

    return "updated"


def main():
    log("===== bid-nr Google Calendar 안전 동기화 시작 =====")

    if not BRIDGE_FILE.is_file():
        log("[ERROR] 브리지 파일 없음: %s" % BRIDGE_FILE)
        return 1

    sys.path.insert(0, str(BRIDGE_DIR))

    try:
        import institution_calendar_bridge as bridge
    except Exception as error:
        log("[ERROR] 브리지 import 실패: %s" % error)
        return 1

    try:
        payload = generate_private_plan(bridge)
    except Exception as error:
        log("[ERROR] 계획 생성 실패: %s" % error)
        return 1

    all_items = payload.get("items") or []

    nr_items = [
        item
        for item in all_items
        if clean(item.get("기관")) == "국가철도공단"
    ]

    action_counts = Counter(
        clean(item.get("action")).lower() or "미확인"
        for item in nr_items
    )

    log(
        "[PLAN] 전체=%d NR=%d actions=%s"
        % (
            len(all_items),
            len(nr_items),
            dict(action_counts),
        )
    )

    approved = []
    skipped = 0

    for item in nr_items:
        ok, reason = validate_item(item, bridge)

        bid_no = clean(item.get("공고번호"))
        action = clean(item.get("action")).lower()

        if not ok:
            skipped += 1
            log(
                "[SKIP] %s action=%s reason=%s"
                % (
                    bid_no or "공고번호없음",
                    action or "미확인",
                    reason,
                )
            )
            continue

        approved.append(item)

    if not approved:
        log(
            "[SUMMARY] 처리대상=0 skipped=%d failed=0"
            % skipped
        )
        log("===== bid-nr Google Calendar 안전 동기화 종료 =====")
        return 0

    try:
        service = bridge.calendar_service(True)
    except Exception as error:
        log("[ERROR] Google Calendar 쓰기 서비스 생성 실패: %s" % error)
        return 1

    created_count = 0
    updated_count = 0
    no_change_count = 0
    failed_count = 0

    for item in approved:
        bid_no = clean(item.get("공고번호"))
        action = clean(item.get("action")).lower()
        calendar_id = clean(item.get("calendar_id"))

        try:
            desired_body = bridge.event_body(item)

            if action == "create":
                response = service.events().insert(
                    calendarId=calendar_id,
                    body=desired_body,
                    sendUpdates="none",
                ).execute()

                created_count += 1

                log(
                    "[CREATE][OK] %s event=%s"
                    % (
                        bid_no,
                        clean(response.get("id")),
                    )
                )

            elif action == "update":
                result = safe_update_times(
                    service,
                    item,
                    desired_body,
                )

                if result == "created":
                    created_count += 1
                elif result == "updated":
                    updated_count += 1
                else:
                    no_change_count += 1

        except Exception as error:
            failed_count += 1

            log(
                "[ERROR] %s action=%s error=%s"
                % (
                    bid_no,
                    action,
                    error,
                )
            )

    log(
        "[SUMMARY] approved=%d created=%d "
        "time_updated=%d no_time_change=%d "
        "skipped=%d failed=%d"
        % (
            len(approved),
            created_count,
            updated_count,
            no_change_count,
            skipped,
            failed_count,
        )
    )

    log("===== bid-nr Google Calendar 안전 동기화 종료 =====")

    return 1 if failed_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
