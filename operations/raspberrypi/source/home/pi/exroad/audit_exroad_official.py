#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-notice EXROAD official-detail audit without sending or state marking."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/home/pi/exroad")
import exroad_notify as exroad


def main():
    target_file = sorted(exroad.TARGET_DIR.glob("exroad_target_*.xlsx"))[-1]
    rows = pd.read_excel(str(target_file)).fillna("").to_dict("records")
    wanted = [row for row in rows if str(row.get("bid_no", "")) == "202607203"]
    if len(wanted) != 1:
        raise RuntimeError("target count=%s" % len(wanted))
    row = wanted[0]
    driver = exroad.make_driver(headless=True)
    try:
        exroad.go_bid_list(driver, datetime.now() - timedelta(days=30), datetime.now())
        exroad.enrich_exroad_target_row(driver, row)
    except Exception as exc:
        error_payload = {"error": "%s: %s" % (type(exc).__name__, exc)}
        Path("/home/pi/exroad/audit_exroad_official_result.json").write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(error_payload, ensure_ascii=False))
        raise
    finally:
        driver.quit()
    safe = {
        key: row.get(key, "")
        for key in (
            "bid_no", "bid_name", "amount", "license", "close_time", "open_time",
            "bid_end_dt", "noti_id", "noti_cont_id", "joint_region", "joint_rate",
            "joint_method", "joint_member_min_rate", "document_path", "document_text_path",
        )
    }
    result_text = json.dumps(safe, ensure_ascii=False, default=str, indent=2)
    Path("/home/pi/exroad/audit_exroad_official_result.json").write_text(result_text, encoding="utf-8")
    print(result_text)


if __name__ == "__main__":
    main()
