
# -*- coding: utf-8 -*-



import os

import re

import shutil

from datetime import datetime, timedelta

from pathlib import Path



import pandas as pd





def _today_yyyymmdd() -> str:

    return datetime.now().strftime("%Y%m%d")





def _safe_mkdir(p: Path):

    p.mkdir(parents=True, exist_ok=True)





def _cleanup_old_raw_dirs(base: Path, keep_days: int = 30):

    """

    raw_YYYYMMDD 폴더 중 keep_days(기본 30일) 초과분 자동 삭제

    """

    cutoff = datetime.now().date() - timedelta(days=keep_days)

    pat = re.compile(r"^raw_(\d{8})$")



    for d in base.iterdir():

        if not d.is_dir():

            continue

        m = pat.match(d.name)

        if not m:

            continue

        try:

            dt = datetime.strptime(m.group(1), "%Y%m%d").date()

        except Exception:

            continue



        if dt <= cutoff:

            try:

                shutil.rmtree(d)

                print(f"[OK] cleanup old raw dir removed: {d}")

            except Exception as e:

                print(f"[WARN] cleanup failed for {d}: {e}")





def _list_today_raw_files(base: Path, ymd: str):

    pat = re.compile(rf"^LH_{ymd}_[0-9]{{6}}\.xlsx$", re.IGNORECASE)

    return sorted([x for x in base.glob(f"LH_{ymd}_*.xlsx") if pat.match(x.name)])





def _read_one(xlsx: Path) -> pd.DataFrame:

    try:

        df = pd.read_excel(xlsx, sheet_name=0)

    except Exception:

        df = pd.read_excel(xlsx, sheet_name=0, engine="openpyxl")



    return df.dropna(how="all")





def main():

    base = Path(

        os.environ.get("LH_BASE_DIR", "REDACTED_PRIVATE_VALUE")

    ).resolve()



    ymd = os.environ.get("LH_MERGE_DATE", _today_yyyymmdd())

    keep_days = int(os.environ.get("LH_RAW_KEEP_DAYS", "30"))



    merge_dir = base / "merge"

    raw_dir = base / f"raw_{ymd}"

    _safe_mkdir(merge_dir)

    _safe_mkdir(raw_dir)



    files = _list_today_raw_files(base, ymd)

    if not files:

        print(f"[INFO] no raw files for {ymd}")

        _cleanup_old_raw_dirs(base, keep_days)

        return 0



    dfs = []

    for f in files:

        try:

            df = _read_one(f)

            df["__src_file"] = f.name

            dfs.append(df)

        except Exception as e:

            print(f"[WARN] failed to read {f}: {e}")



    if not dfs:

        print("[WARN] no readable files")

        return 0



    all_df = pd.concat(dfs, ignore_index=True)



    key_col = None

    for c in ["공고번호", "공고번호 "]:

        if c in all_df.columns:

            key_col = c

            break



    if key_col:

        before = len(all_df)

        all_df = all_df.drop_duplicates(subset=[key_col], keep="last")

        print(f"[OK] dedup by '{key_col}': {before} -> {len(all_df)}")

    else:

        print("[WARN] '공고번호' column not found. skip dedup.")



    # ✅ merge는 무조건 하루 1개 (덮어쓰기)

    out = merge_dir / f"LH_MERGED_{ymd}.xlsx"


    # ✅ 운영자용 고정 파일명 (윈도우/엑셀 호환을 위해 "복

    # ✅ TODAY 파일은 항상 overwrite

    try:

        import shutil

        shutil.copy2(str(out), str(today_out_root))

        shutil.copy2(str(out), str(today_out_merge))

        print(f"[OK] today saved(overwrite): {today_out_root}")

        print(f"[OK] today saved(overwrite): {today_out_merge}")

    except Exception as e:

        print(f"[WARN] failed to write TODAY files: {e}")

# 사 overwrite" 방식)

    today_out_root = base / "LH_TODAY.xlsx"

    today_out_merge = merge_dir / "LH_TODAY.xlsx"


    all_df.to_excel(out, index=False)

    print(f"[OK] merged saved (overwrite): {out}")



    # ✅ raw 이동

    for f in files:

        dst = raw_dir / f.name

        if not dst.exists():

            shutil.move(str(f), str(dst))



    print(f"[OK] raw moved to: {raw_dir}")



    # ✅ 30일 초과 raw 자동 삭제

    _cleanup_old_raw_dirs(base, keep_days)



    return 0





if __name__ == "__main__":

    raise SystemExit(main())

