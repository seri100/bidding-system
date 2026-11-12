
# -*- coding: utf-8 -*-

import sys

from datetime import datetime

from pathlib import Path

import pandas as pd



# get_notice_daily.py 결과(co_일일_...)

DIR_NOTICE = Path("/mnt/vol1/result/nara")



# 250916_gd.py 결과(입찰공고_지역분류_...)

DIR_GD = Path("/mnt/vol1/gon_auto")



# ✅ PC에서 Z:\VOL1\bid\result\nara 에 보이도록 하는 저장 경로

#    라즈베리에서는 /mnt/vol1/bid/result/nara 이어야 함

OUT_DIR = Path("/mnt/vol1/bid/result/nara")





def _get_latest_excel(dir_path, desc, pattern="*.xlsx"):

    if not dir_path.exists():

        raise FileNotFoundError(f"[ERR] {desc} 폴더 없음: {dir_path}")

    files = sorted(dir_path.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)

    if not files:

        raise FileNotFoundError(f"[ERR] {desc} 파일 없음: {dir_path}")

    print(f"[INFO] {desc} 파일 선택: {files[0]}")

    return files[0]





def _ensure_key(df, src):

    df = df.copy()

    if "공고번호" not in df.columns:

        if "bidNtceNo" in df.columns:

            df["공고번호"] = df["bidNtceNo"]

        else:

            raise KeyError(f"[ERR] {src}: 공고번호 없음")



    if "공고차수" not in df.columns:

        if "bidNtceOrd" in df.columns:

            df["공고차수"] = df["bidNtceOrd"]

        elif "차수" in df.columns:

            df["공고차수"] = df["차수"]

        else:

            df["공고차수"] = 0



    df["공고번호"] = df["공고번호"].astype(str).str.strip()

    df["공고차수"] = df["공고차수"].astype(str).str.strip()

    return df





def _pick(df, cols):

    for c in cols:

        if c in df.columns:

            return c

    return ""





def load_notice():

    p = _get_latest_excel(DIR_NOTICE, "get_notice_daily 결과", "co_*.xlsx")

    df = pd.read_excel(p)

    print(f"[INFO] notice 컬럼: {list(df.columns)}")

    return _ensure_key(df, "notice")





def load_gd():

    p = _get_latest_excel(DIR_GD, "gd 결과", "입찰공고_지역분류_*.xlsx")

    df = pd.read_excel(p)

    print(f"[INFO] gd 컬럼: {list(df.columns)}")

    return _ensure_key(df, "gd")





def merge(notice, gd):

    gong = _pick(gd, ["공종", "공종명", "공종코드", "업종명", "indstrytyNm"])

    rgn = _pick(gd, ["참가가능지역", "참가지역", "참가가능지역명", "prtcptLmtRgnNm"])



    print(f"[INFO] 공종열: {gong or '없음'}")

    print(f"[INFO] 참가가능지역열: {rgn or '없음'}")



    use_cols = ["공고번호", "공고차수"]

    if gong: use_cols.append(gong)

    if rgn: use_cols.append(rgn)



    gd2 = gd[[c for c in use_cols if c in gd.columns]].drop_duplicates(

        subset=["공고번호", "공고차수"]

    )



    merged = pd.merge(notice, gd2, on=["공고번호", "공고차수"], how="left")



    merged["공종"] = merged.get(gong, None)

    merged["참가가능지역"] = merged.get(rgn, None)



    return merged





def save(df):

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    name = f"notice_gd_공종_참가가능지역_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    path = OUT_DIR / name

    df.to_excel(path, index=False)

    print(f"[SAVE] 저장: {path}")

    return path





def main():

    print("[MAIN] 시작: notice + gd 병합")

    n = load_notice()

    g = load_gd()

    print(f"[MAIN] notice: {len(n)}행 / gd: {len(g)}행")

    m = merge(n, g)

    print(f"[MAIN] 병합 후: {len(m)}행")

    save(m)

    print("[MAIN] 완료")





if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print(f"[FATAL] {e}")

        sys.exit(1)



