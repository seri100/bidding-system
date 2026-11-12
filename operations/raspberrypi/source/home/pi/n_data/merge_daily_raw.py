
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import glob

import os

import re

from datetime import datetime

import pandas as pd



BASE_DIR = "/mnt/vol1/bid/n_data/raw"

OUT_DIR  = "/mnt/vol1/bid/n_data/raw"



# 오늘 날짜 기준 (YYYYMMDD)

TODAY = datetime.now().strftime("%Y%m%d")



pattern = os.path.join(BASE_DIR, f"입찰공고_{TODAY}*.xlsx")

files = sorted(glob.glob(pattern))



if not files:

    print(f"[SKIP] {TODAY} 파일 없음")

    raise SystemExit(0)



dfs = []

for f in files:

    if "병합" in f:

        continue

    try:

        df = pd.read_excel(f, dtype=str)

        df["__source_file"] = os.path.basename(f)

        dfs.append(df)

    except Exception as e:

        print(f"[ERR] read fail: {f} -> {e}")



if not dfs:

    print("[ERR] 병합 대상 없음")

    raise SystemExit(1)



merged = pd.concat(dfs, ignore_index=True).fillna("")



# ✅ 중복 제거 기준

key_cols = [c for c in ["공고번호", "차수"] if c in merged.columns]

if key_cols:

    merged = merged.drop_duplicates(subset=key_cols)



out_file = os.path.join(OUT_DIR, f"입찰공고_{TODAY}_병합.xlsx")

merged.to_excel(out_file, index=False)



print(f"[OK] merged rows={len(merged)} -> {out_file}")

