# -*- coding: utf-8 -*-
# __LH_PENDING_QUEUE_V2__

from datetime import datetime
from pathlib import Path
import json
import os


BASE_DIR = Path(__file__).resolve().parent

PENDING_FILE = (
    BASE_DIR / "lh_pending_alimtalk.json"
)

SENT_AUDIT_FILE = (
    BASE_DIR / "lh_alimtalk_sent_audit.json"
)


def _bid_no(row):
    return str(
        (row or {}).get("공고번호")
        or (row or {}).get("bidNtceNo")
        or (row or {}).get("bid_no")
        or ""
    ).strip()


def _load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8",
                errors="strict",
            )
        )

    except Exception as exc:
        print(
            "[LH_RETRY][WARN] JSON read failed "
            "file={} type={}".format(
                path,
                type(exc).__name__,
            )
        )

        return default


def _atomic_write(path, value):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = path.with_name(
        "." + path.name + ".tmp"
    )

    temp.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        str(temp),
        str(path),
    )


def load_pending_rows():
    data = _load_json(
        PENDING_FILE,
        [],
    )

    if not isinstance(data, list):
        return []

    result = []
    seen = set()

    for row in data:
        if not isinstance(row, dict):
            continue

        bid_no = _bid_no(row)

        if not bid_no or bid_no in seen:
            continue

        seen.add(bid_no)
        result.append(row)

    return result


def load_sent_audit():
    data = _load_json(
        SENT_AUDIT_FILE,
        {},
    )

    if not isinstance(data, dict):
        return {}

    return data


def is_already_sent(bid_no):
    bid_no = str(bid_no or "").strip()

    if not bid_no:
        return False

    return bid_no in load_sent_audit()


def _save_pending_map(pending):
    _atomic_write(
        PENDING_FILE,
        list(pending.values()),
    )


def _send_exception_alert(
    notifier,
    bid_no,
    exc,
):
    callback = getattr(
        notifier,
        "_notify_failure",
        None,
    )

    if not callable(callback):
        return

    try:
        callback(
            "LH AlimTalk EXCEPTION "
            "bid={} type={}".format(
                bid_no,
                type(exc).__name__,
            )
        )

    except Exception:
        pass


def process_alimtalk_rows(
    notifier,
    rows,
    log=print,
):
    pending = {
        _bid_no(row): row
        for row in load_pending_rows()
        if _bid_no(row)
    }

    audit = load_sent_audit()

    sent_rows = []
    failed_rows = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue

        bid_no = _bid_no(row)

        if not bid_no:
            log(
                "[LH_RETRY] skip row without bid number"
            )
            continue

        if bid_no in audit:
            pending.pop(
                bid_no,
                None,
            )

            _save_pending_map(pending)

            log(
                "[LH_RETRY] already accepted; "
                "skip duplicate bid={}".format(
                    bid_no
                )
            )

            continue

        try:
            sent_count = notifier.send_notices(
                [row]
            )

        except Exception as exc:
            log(
                "[LH_RETRY] send exception "
                "bid={} type={} message={}".format(
                    bid_no,
                    type(exc).__name__,
                    exc,
                )
            )

            _send_exception_alert(
                notifier,
                bid_no,
                exc,
            )

            sent_count = 0

        if sent_count == 1:
            audit[bid_no] = {
                "sent_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "title": str(
                    row.get("입찰공고건명")
                    or ""
                ),
            }

            # 성공 기록을 먼저 남겨 재실행 중복을 막는다.
            _atomic_write(
                SENT_AUDIT_FILE,
                audit,
            )

            pending.pop(
                bid_no,
                None,
            )

            _save_pending_map(pending)

            sent_rows.append(row)

            log(
                "[LH_RETRY] send accepted "
                "bid={}".format(bid_no)
            )

        else:
            pending[bid_no] = row

            # 실패 직후 바로 저장한다.
            _save_pending_map(pending)

            failed_rows.append(row)

            log(
                "[LH_RETRY] queued for next retry "
                "bid={}".format(bid_no)
            )

    log(
        "[LH_RETRY] result sent={} failed={} "
        "pending_total={}".format(
            len(sent_rows),
            len(failed_rows),
            len(pending),
        )
    )

    return sent_rows, failed_rows


def retry_pending_alimtalk(
    notifier,
    log=print,
):
    rows = load_pending_rows()

    if not rows:
        return [], []

    log(
        "[LH_RETRY] pending retry start "
        "count={}".format(len(rows))
    )

    return process_alimtalk_rows(
        notifier,
        rows,
        log=log,
    )
