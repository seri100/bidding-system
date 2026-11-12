#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resume only the six approved Calendar items remaining after a partial apply."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/pi/bid-schedule-sync")
import institution_calendar_bridge as bridge

REMAINING = {
    "2026-01-000133-00": "update",
    "2026-01-000121-00": "update",
    "2026-01-000123-00": "create",
    "202607203": "create",
    "B3202602725": "create",
    "B3202602722": "create",
}
RESULT = Path("/home/pi/bid-schedule-sync/calendar_resume_result.json")


def main():
    plan = json.loads(Path("/home/pi/bid-schedule-sync/staging_calendar_plan.json").read_text(encoding="utf-8"))["items"]
    selected = [item for item in plan if item.get("공고번호") in REMAINING]
    errors = []
    if len(selected) != 6:
        errors.append("selected count=%d" % len(selected))
    for item in selected:
        expected = REMAINING[item["공고번호"]]
        if item.get("action") != expected:
            errors.append("%s action=%s expected=%s" % (item["공고번호"], item.get("action"), expected))
    if errors:
        raise RuntimeError("; ".join(errors))

    service = bridge.calendar_service(True)
    results = []
    for item in selected:
        try:
            body = bridge.event_body(item)
            if item["action"] == "update":
                response = service.events().patch(
                    calendarId=item["calendar_id"], eventId=item["event_id"],
                    body=body, sendUpdates="none"
                ).execute()
            else:
                response = service.events().insert(
                    calendarId=item["calendar_id"], body=body, sendUpdates="none"
                ).execute()
            results.append({"공고번호": item["공고번호"], "action": item["action"], "ok": True, "event_id": response.get("id", "")})
        except Exception as exc:
            results.append({"공고번호": item["공고번호"], "action": item["action"], "ok": False, "error": "%s: %s" % (type(exc).__name__, exc)})
    payload = {"completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "results": results}
    RESULT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if any(not item["ok"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
