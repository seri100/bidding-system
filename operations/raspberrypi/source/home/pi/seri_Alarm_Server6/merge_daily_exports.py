
#!/usr/bin/env python3

import os

import pandas as pd

from datetime import datetime

from glob import glob



BASE = "REDACTED_PRIVATE_VALUE/exports"

DAILY = os.path.join(BASE, "daily")



today = datetime.now()

ymd = today.strftime("%Y%m%d")



# 평일 / 주말 구분

is_weekend = today.weekday() >= 5   # 5=토, 6=일

subdir = "we" if is_weekend else "wd"

OUT_DIR = os.path.join(DAILY, subdir)



os.makedirs(OUT_DIR, exist_ok=True)



out_file = os.path.join(OUT_DIR, f"LH_{ymd}.csv")



files = sorted(glob(os.path.join(BASE, "LH_*.csv")))

if not files:

    print("[INFO] no source exports to merge")

    raise SystemExit(0)



dfs = []

for f in files:

    try:

        dfs.append(pd.read_csv(f, dtype=str, encoding="REDACTED_PRIVATE_VALUE"))

    except Exception as e:

        print(f"[WARN] skip {f}: {e}")



if not dfs:

    print("[INFO] nothing to merge")

    raise SystemExit(0)



df = pd.concat(dfs, ignore_index=True).drop_duplicates()



df.to_csv(out_file, index=False, encoding="REDACTED_PRIVATE_VALUE")

print(f"[OK] merged -> {out_file} ({len(df)} rows)")

