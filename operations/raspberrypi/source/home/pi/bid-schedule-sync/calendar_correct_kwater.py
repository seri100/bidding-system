#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch only the two already-approved K-water events with corrected official fields."""
import json
import sys
from pathlib import Path
sys.path.insert(0, "/home/pi/bid-schedule-sync")
import institution_calendar_bridge as bridge

WANTED = {"B3202602725", "B3202602722"}

def main():
    plan = json.loads(Path("/home/pi/bid-schedule-sync/staging_calendar_plan.json").read_text(encoding="utf-8"))["items"]
    items = [x for x in plan if x.get("공고번호") in WANTED]
    if len(items) != 2 or any(x.get("action") != "update" for x in items):
        raise RuntimeError("K-water correction precondition failed")
    service = bridge.calendar_service(True)
    results = []
    for item in items:
        response = service.events().patch(calendarId=item["calendar_id"], eventId=item["event_id"], body=bridge.event_body(item), sendUpdates="none").execute()
        results.append({"공고번호": item["공고번호"], "event_id": response.get("id", ""), "ok": True})
    print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    main()
