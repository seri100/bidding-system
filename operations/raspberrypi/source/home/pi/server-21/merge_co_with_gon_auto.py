# -*- coding: utf-8 -*-
"""
co_일일_입찰요약(개찰요약) + 입찰공고_지역분류(gon_auto)를 병합해서
개찰요약에 '공종' 열과 '참가가능지역' 열을 추가한 최종 엑셀을 만든다.

- 개찰요약:  /mnt/vol1/result/nara       (co_일일_입찰요약_*.xlsx 중 가장 최신)
- 공고/지역: /mnt/vol1/gon_auto           (입찰공고_지역분류_*.xlsx 중 가장 최신)
- 키: 공고번호 + 공고차수 (없으면 bidNtceNo/bidNtceOrd 등에서 생성)
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd


# --------------------------------------------------
# 경로 설정 (환경에 맞게 여기만 바꾸면 됨)
# --------------------------------------------------
# Windows: Z:\VOL1\bid\result\nara  -> Raspberry Pi: /mnt/vol1/result/nara
DIR_CO = Path("/mnt/vol1/result/nara")      # co_일일_입찰요약_*.xlsx 폴더

# Windows: Z:\VOL1\bid\gon_auto     -> Raspberry Pi: /mnt/vol1/gon_auto
DIR_GON = Path("/mnt/vol1/gon_auto")        # 입찰공고_지역분류_*.xlsx 폴더

# 최종 결과 저장 폴더
OUT_DIR = Path("/mnt/vol1/server-21/merge_out")


# --------------------------------------------------
# 공통 유틸
# --------------------------------------------------
def _get_latest_excel(dir_path: Path, desc: str, pattern: str = "*.xlsx") -> Path:
    """지정 폴더에서 가장 마지막에 수정된 xlsx 파일 1개를 고른다."""
    if not dir_path.exists():
        raise FileNotFoundError(f"[ERR] {desc} 폴더가 없습니다: {dir_path}")

    files = sorted(
        dir_path.glob(pattern),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError(
            f"[ERR] {desc} 폴더에 xlsx 파일이 없습니다 (pattern={pattern}): {dir_path}"
        )

    latest = files[0]
    print(f"[INFO] {desc} 파일 선택: {latest}")
    return latest


def _ensure_key_columns(df: pd.DataFrame, src_name: str) -> pd.DataFrame:
    """
    공고번호/공고차수 컬럼을 강제로 맞춰준다.
    - bidNtceNo, bidNtceOrd 만 있어도 공고번호/공고차수로 복사해서 사용.
    - 공고차수가 없으면 0으로 채움.
    - 문자열로 통일.
    """
    df = df.copy()

    # 공고번호
    if "공고번호" not in df.columns:
        if "bidNtceNo" in df.columns:
            df["공고번호"] = df["bidNtceNo"]
        else:
            raise KeyError(f"[ERR] {src_name}에 '공고번호' 또는 'bidNtceNo' 컬럼이 없습니다.")

    # 공고차수
    if "공고차수" not in df.columns:
        if "bidNtceOrd" in df.columns:
            df["공고차수"] = df["bidNtceOrd"]
        else:
            # 없으면 0으로 생성 (대부분 0 또는 1차만 있을 때)
            df["공고차수"] = 0

    df["공고번호"] = df["공고번호"].astype(str).str.strip()
    df["공고차수"] = df["공고차수"].astype(str).str.strip()

    return df


def _pick_first_existing(df: pd.DataFrame, candidates: List[str]) -> str:
    """주어진 후보 컬럼들 중 DataFrame에 존재하는 첫 번째 컬럼명을 반환. 없으면 빈 문자열."""
    for c in candidates:
        if c in df.columns:
            return c
    return ""


# --------------------------------------------------
# 1) 개찰요약(co_일일_입찰요약) 로딩
# --------------------------------------------------
def load_co_df() -> pd.DataFrame:
    """
    /mnt/vol1/result/nara 에서 가장 최신 co_일일_입찰요약_*.xlsx 파일을 읽어서
    공고번호/공고차수 키를 정리한다.
    """
    latest = _get_latest_excel(DIR_CO, "개찰요약(co_일일_입찰요약)", "co_*.xlsx")
    df = pd.read_excel(latest)
    print(f"[INFO] 개찰요약 컬럼: {list(df.columns)}")
    df = _ensure_key_columns(df, "개찰요약")
    return df


# --------------------------------------------------
# 2) gon_auto(입찰공고_지역분류) 로딩
# --------------------------------------------------
def load_gon_df() -> pd.DataFrame:
    """
    /mnt/vol1/gon_auto 에서 가장 최신 입찰공고_지역분류_*.xlsx 파일을 읽어서
    공고번호/공고차수 + 공종/참가가능지역 정보를 가져온다.
    """
    latest = _get_latest_excel(DIR_GON, "지역분류(gon_auto)", "입찰공고_지역분류_*.xlsx")
    df = pd.read_excel(latest)
    print(f"[INFO] gon_auto 컬럼: {list(df.columns)}")
    df = _ensure_key_columns(df, "gon_auto")
    return df


# --------------------------------------------------
# 3) 병합 및 공종/참가가능지역 열 추가
# --------------------------------------------------
def merge_and_add_columns(co_df: pd.DataFrame, gon_df: pd.DataFrame) -> pd.DataFrame:
    """
    co_df(개찰요약)에 gon_df(지역분류)의 공종열, 참가가능지역열을 붙인다.
    - 키: 공고번호 + 공고차수
    - 공종 후보 컬럼: ['공종명', '공종', '업종명', 'indstrytyNm']
    - 참가가능지역 후보: ['참가가능지역', '참가지역', '참가가능지역명', 'prtcptLmtRgnNm']
    """
    # 공종/참가가능지역 컬럼 찾기
    gongjong_col = _pick_first_existing(
        gon_df, ["공종명", "공종", "업종명", "indstrytyNm"]
    )
    rgn_col = _pick_first_existing(
        gon_df, ["참가가능지역", "참가지역", "참가가능지역명", "prtcptLmtRgnNm"]
    )

    print(f"[INFO] 공종열 후보 선택: '{gongjong_col or '없음'}'")
    print(f"[INFO] 참가가능지역열 후보 선택: '{rgn_col or '없음'}'")

    # 병합에 쓸 최소 컬럼만 서브셋
    merge_cols = ["공고번호", "공고차수"]
    if gongjong_col:
        merge_cols.append(gongjong_col)
    if rgn_col:
        merge_cols.append(rgn_col)

    gon_sub = gon_df[merge_cols].copy()

    merged = pd.merge(
        co_df,
        gon_sub,
        on=["공고번호", "공고차수"],
        how="left",
    )

    # 최종 표시용 컬럼 이름을 '공종', '참가가능지역'으로 통일
    if gongjong_col:
        merged["공종"] = merged[gongjong_col]
    else:
        merged["공종"] = None

    if rgn_col:
        merged["참가가능지역"] = merged[rgn_col]
    else:
        merged["참가가능지역"] = None

    return merged


# --------------------------------------------------
# 4) 최종 저장
# --------------------------------------------------
def save_result(df: pd.DataFrame) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"co_일일_입찰요약_지역정보포함_{now}.xlsx"
    out_path = OUT_DIR / file_name
    df.to_excel(out_path, index=False)
    print(f"[SAVE] 최종 결과 저장: {out_path}")
    return out_path


# --------------------------------------------------
# 5) main
# --------------------------------------------------
def main():
    print("[MAIN] co_일일_입찰요약 + gon_auto(지역분류) 병합 시작")

    co_df = load_co_df()
    gon_df = load_gon_df()

    print(f"[MAIN] 개찰요약 행수: {len(co_df)}")
    print(f"[MAIN] gon_auto 행수: {len(gon_df)}")

    merged = merge_and_add_columns(co_df, gon_df)

    print(f"[MAIN] 병합 후 행수: {len(merged)}")

    save_result(merged)

    print("[MAIN] 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] 오류 발생: {e}")
        sys.exit(1)
