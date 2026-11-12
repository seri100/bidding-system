#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only verification of the 23 approved Calendar items."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/pi/bid-schedule-sync")
import institution_calendar_bridge as bridge

REPORT = Path("/home/pi/bid-schedule-sync/calendar_post_verify.json")


def field(description, name):
    match = re.search(r"(?:^|\n)%s[ \t]*[:：][ \t]*([^\n]*)" % re.escape(name), description or "")
    return match.group(1).strip() if match else ""


def main():
    plan = json.loads(Path("/home/pi/bid-schedule-sync/staging_calendar_plan.json").read_text(encoding="utf-8"))["items"]
    approved = [item for item in plan if item.get("공고번호") != "2026-02-000390-00"]
    service = bridge.calendar_service(False)
    calendars = {}
    for calendar_id in sorted(set(item["calendar_id"] for item in approved)):
        calendars[calendar_id] = bridge.list_events(service, calendar_id)
    results = []
    duplicate_count = 0
    cancellation_count = 0
    errors = []
    for item in approved:
        matches = []
        for event in calendars[item["calendar_id"]]:
            combined = "%s\n%s" % (event.get("summary", ""), event.get("description", ""))
            if item["공고번호"] in combined:
                matches.append(event)
        duplicate_count += max(0, len(matches) - 1)
        if len(matches) != 1:
            errors.append("%s match_count=%d" % (item["공고번호"], len(matches)))
            results.append({"공고번호": item["공고번호"], "ok": False, "match_count": len(matches)})
            continue
        event = matches[0]
        description = event.get("description", "") or ""
        start = event.get("start", {}).get("dateTime", "")[:19].replace("T", " ")
        checks = {
            "start": start == item["입찰개시일시"],
            "bid_end": field(description, "입찰마감일시") == item["입찰마감일시"],
            "agreement": field(description, "협정마감일시") == item["협정마감일시"],
            "agreement_status": field(description, "협정확인상태") == item["협정확인상태"],
        }
        if "취소" in ((event.get("summary", "") or "") + " " + description):
            cancellation_count += 1
        ok = all(checks.values())
        if not ok:
            errors.append("%s field mismatch %s" % (item["공고번호"], checks))
        results.append({"공고번호": item["공고번호"], "event_id": event.get("id", ""), "ok": ok, "checks": checks})
    report = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "approved_count": len(approved),
        "verified_count": sum(1 for item in results if item.get("ok")),
        "failed_count": sum(1 for item in results if not item.get("ok")),
        "duplicate_count": duplicate_count,
        "cancellation_count": cancellation_count,
        "errors": errors,
        "results": results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
