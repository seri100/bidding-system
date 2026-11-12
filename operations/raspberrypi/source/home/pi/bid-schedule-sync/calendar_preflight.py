#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calendar bridge final preflight and recoverable update backup (no writes)."""

import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/pi/bid-schedule-sync")
import institution_calendar_bridge as bridge

PLAN = Path("/home/pi/bid-schedule-sync/staging_calendar_plan.json")
BACKUP_DIR = Path("/home/pi/bid-schedule-sync/backups")
REPORT = Path("/home/pi/bid-schedule-sync/calendar_preflight_report.json")


def main():
    payload = json.loads(PLAN.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    write_items = [item for item in items if item.get("action") in ("create", "update")]
    update_items = [item for item in items if item.get("action") == "update"]
    create_items = [item for item in items if item.get("action") == "create"]

    service = bridge.calendar_service(False)
    calendar_ids = sorted(set(item["calendar_id"] for item in write_items))
    calendars = []
    current_by_calendar = {}
    for calendar_id in calendar_ids:
        meta = service.calendars().get(calendarId=calendar_id).execute()
        calendars.append({
            "id": calendar_id,
            "summary": meta.get("summary", ""),
            "timeZone": meta.get("timeZone", ""),
        })
        current_by_calendar[calendar_id] = bridge.list_events(service, calendar_id)

    backups = []
    errors = []
    for item in update_items:
        event = service.events().get(
            calendarId=item["calendar_id"], eventId=item["event_id"]
        ).execute()
        if item["공고번호"] not in ((event.get("summary", "") or "") + "\n" + (event.get("description", "") or "")):
            errors.append("update event bid mismatch: %s" % item["공고번호"])
        backups.append({
            "calendar_id": item["calendar_id"],
            "calendar_name": next((x["summary"] for x in calendars if x["id"] == item["calendar_id"]), ""),
            "bid_no": item["공고번호"],
            "event_id": item["event_id"],
            "event": event,
        })

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / ("calendar_update_originals_%s.json" % stamp)
    backup_text = json.dumps({
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "purpose": "pre-apply recoverable backup of the 15 original Calendar events",
        "count": len(backups),
        "items": backups,
    }, ensure_ascii=False, indent=2)
    backup_path.write_text(backup_text, encoding="utf-8")
    os.chmod(str(backup_path), 0o600)

    keys = [(x["calendar_id"], x["공고번호"], x["입찰개시일시"]) for x in write_items]
    duplicates = [list(key) + [count] for key, count in Counter(keys).items() if count > 1]
    cancellations = [x["공고번호"] for x in write_items if "취소" in (x.get("공고명", "") + " " + x.get("협정확인상태", ""))]
    if len(create_items) != 8:
        errors.append("create count=%d" % len(create_items))
    if len(update_items) != 15:
        errors.append("update count=%d" % len(update_items))
    if len(backups) != 15:
        errors.append("backup count=%d" % len(backups))
    if duplicates:
        errors.append("duplicate keys present")
    if cancellations:
        errors.append("cancellations present")
    if any((item.get("duplicate_matches") or 0) != 0 for item in write_items):
        errors.append("existing duplicate matches present")

    report = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "calendar_write": False,
        "calendars": calendars,
        "create_count": len(create_items),
        "update_count": len(update_items),
        "exclude_count": len([x for x in items if x.get("action") == "exclude"]),
        "duplicate_keys": duplicates,
        "cancellation_bid_numbers": cancellations,
        "backup_path": str(backup_path),
        "backup_count": len(backups),
        "backup_sha256": hashlib.sha256(backup_text.encode("utf-8")).hexdigest(),
        "prohibited_actions": {
            "calendar_delete": 0,
            "message_send": 0,
            "service_change_or_run": 0,
            "timer_change": 0,
        },
        "errors": errors,
        "ready": not errors,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
