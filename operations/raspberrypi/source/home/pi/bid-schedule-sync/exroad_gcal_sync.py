#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import json

import sys

from datetime import datetime

from pathlib import Path



sys.path.insert(

    0,

    "/home/pi/bid-schedule-sync"

)



import institution_calendar_bridge as bridge



LOG_DIR = Path(

    "/mnt/vol1/bid/exroad/logs"

)

LOG_DIR.mkdir(parents=True, exist_ok=True)



records = bridge.load_exroad()

plan = bridge.make_plan(

    records,

    apply_calendar=True

)



payload = {

    "generated_at": datetime.now().strftime(

        "%Y-%m-%d %H:%M:%S"

    ),

    "items": plan,

}



out = LOG_DIR / "exroad_gcal_latest.json"

out.write_text(

    json.dumps(

        payload,

        ensure_ascii=False,

        indent=2,

        default=str

    ),

    encoding="utf-8"

)



for item in plan:

    print(

        "[EXROAD_GCAL] bid_no=%s action=%s "

        "reason=%s start=%s end=%s"

        % (

            item.get("공고번호", ""),

            item.get("action", ""),

            item.get("reason", ""),

            item.get("입찰개시일시", ""),

            item.get("입찰마감일시", ""),

        )

    )

