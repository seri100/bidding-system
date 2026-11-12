
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



from pathlib import Path

import datetime as dt

import os

import sys

import traceback

import pandas as pd



BASE_DIR_DEFAULT = "/mnt/vol1/bid/n_data"



INCLUDE_DIRS = [

    "raw/backup", "split/backup", "report/backup",

    "raw", "split", "report",

]



BID_COL_PAIRS = [

    ("공고번호", "차수"),

    ("bid_no", "bid_ord"),

    ("bidNtceNo", "bidNtceOrd"),

]



def log(msg):

    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)



def detect_category(path: Path):

    p = str(path).lower()

    if "/raw/" in p:

        return "RAW"

    if "/split/" in p:

        return "SPLIT"

    if "/report/" in p:

        return "REPORT"

    return None



def find_bid_cols(df):

    cols = set(df.columns)

    for a, b in BID_COL_PAIRS:

        if a in cols and b in cols:

            return a, b

    return None, None



def dedupe(df):

    a, b = find_bid_cols(df)

    if not a:

        return df, "SKIP(no bid cols)"



    df = df.copy()

    df["_bid_key"] = df[a].astype(str) + "-" + df[b].astype(str)



    if "_src_mtime" in df.columns:

        df = df.sort_values(["_bid_key", "_src_mtime"])

        df = df.drop_duplicates("_bid_key", keep="last")

    else:

        df = df.drop_duplicates("_bid_key", keep="last")



    return df, f"OK({a}+{b})"



def main():

    base_dir = os.environ.get("N_DATA_BASE", BASE_DIR_DEFAULT)

    base = Path(base_dir)



    today = dt.date.today()

    start = dt.datetime.combine(today, dt.time.min)

    end = start + dt.timedelta(days=1)



    out_dir = base / "report/daily_merge"

    out_dir.mkdir(parents=True, exist_ok=True)



    out_xlsx = out_dir / f"daily_merged_{today:%Y%m%d}.xlsx"

    done = out_dir / f".daily_merged_{today:%Y%m%d}.done"



    if done.exists():

        log("SKIP: already merged today")

        return 0



    buckets = {"RAW": [], "SPLIT": [], "REPORT": []}

    file_count = {"RAW": 0, "SPLIT": 0, "REPORT": 0}



    for sub in INCLUDE_DIRS:

        d = base / sub

        if not d.exists():

            continue



        for f in d.rglob("*.xlsx"):

            if f.name.startswith("~$"):

                continue



            try:

                mt = dt.datetime.fromtimestamp(f.stat().st_mtime)

            except Exception:

                continue



            if not (start <= mt < end):

                continue



            cat = detect_category(f)

            if not cat:

                continue



            try:

                xls = pd.ExcelFile(f)

                file_count[cat] += 1

                for sh in xls.sheet_names[:10]:

                    try:

                        df = pd.read_excel(f, sheet_name=sh, dtype=str)

                        if df.empty:

                            continue

                        df["_src_file"] = str(f)

                        df["_src_sheet"] = sh

                        df["_src_mtime"] = mt.strftime("%Y-%m-%d %H:%M:%S")

                        buckets[cat].append(df)

                    except Exception:

                        continue

            except Exception:

                continue



    merged = {}

    summary_rows = []



    for cat in ["RAW", "SPLIT", "REPORT"]:

        if not buckets[cat]:

            merged[cat] = pd.DataFrame()

            summary_rows.append({

                "sheet": cat,

                "files": 0,

                "rows": 0,

                "dedupe": "NO DATA"

            })

            continue



        big = pd.concat(buckets[cat], ignore_index=True)

        big2, note = dedupe(big)

        merged[cat] = big2

        summary_rows.append({

            "sheet": cat,

            "files": file_count[cat],

            "rows": len(big2),

            "dedupe": note

        })



    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:

        merged["RAW"].to_excel(w, index=False, sheet_name="RAW")

        merged["SPLIT"].to_excel(w, index=False, sheet_name="SPLIT")

        merged["REPORT"].to_excel(w, index=False, sheet_name="REPORT")



        summary_df = pd.DataFrame(summary_rows)

        summary_df.to_excel(w, index=False, sheet_name="SUMMARY")



    done.write_text(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")

    log(f"DONE: {out_xlsx}")

    return 0



if __name__ == "__main__":

    try:

        sys.exit(main())

    except Exception as e:

        log(f"ERROR: {e}")

        traceback.print_exc()

        sys.exit(2)

