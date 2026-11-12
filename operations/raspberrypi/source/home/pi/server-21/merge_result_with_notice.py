

# -*- coding: utf-8 -*-
"""
개찰결과 + (미리 수집된) 공고 엑셀을 병합해서
불필요 열 삭제 / 중복키 정리 / 낙찰자선정기준 복원 / 컬럼 재정렬 후
최종 엑셀을 자동 저장하는 스크립트.

1) DIR_RESULT 에서 가장 최신 개찰결과 xlsx 1개 선택
2) DIR_NOTICE 에서 가장 최신 공고 xlsx 1개 선택
3) 공고번호/공고차수 기준으로 merge
4) 정리 후 OUT_DIR 에 "개찰공고_최종정리_YYYYMMDD_HHMMSS.xlsx" 저장
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


# --------------------------------------------------
# 설정: 경로만 환경에 맞게 바꾸면 됨
# --------------------------------------------------
DIR_RESULT = Path("/mnt/vol1/입찰/pd_data/나라장터공고/결과")  # 개찰결과 저장 폴더 (실제 경로)

DIR_NOTICE = Path("/mnt/vol1/bid/server-21/notice")            # 공고 저장 폴더(임시로 그대로)

OUT_DIR    = Path("/mnt/vol1/bid/server-21/merge_out")         # 병합/정리 결과 폴더



# --------------------------------------------------
# 공통 유틸
# --------------------------------------------------
def _get_latest_excel(dir_path: Path, desc: str) -> Path:
    """지정 폴더에서 가장 마지막에 수정된 xlsx 파일 1개를 고른다."""
    if not dir_path.exists():
        raise FileNotFoundError(f"[ERR] {desc} 폴더가 없습니다: {dir_path}")

    files = sorted(dir_path.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"[ERR] {desc} 폴더에 xlsx 파일이 없습니다: {dir_path}")

    latest = files[0]
    print(f"[INFO] {desc} 파일 선택: {latest.name}")
    return latest


def _ensure_key_columns(df: pd.DataFrame, src_name: str) -> pd.DataFrame:
    """
    공고번호/공고차수 컬럼을 강제로 맞춰준다.
    - bidNtceNo, bidNtceOrd 만 있어도 공고번호/공고차수로 복사해서 사용.
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
            raise KeyError(f"[ERR] {src_name}에 '공고차수' 또는 'bidNtceOrd' 컬럼이 없습니다.")

    # 문자열로 정규화
    df["공고번호"] = df["공고번호"].astype(str).str.strip()
    df["공고차수"] = df["공고차수"].astype(str).str.strip()

    return df


def _load_result_df() -> pd.DataFrame:
    """개찰결과 엑셀(최신 1개)을 읽어와서 공고번호/공고차수 컬럼을 정리한다."""
    latest = _get_latest_excel(DIR_RESULT, "개찰결과")
    df = pd.read_excel(latest)
    print(f"[INFO] 개찰결과 컬럼: {list(df.columns)}")
    df = _ensure_key_columns(df, "개찰결과")
    return df


def _load_notice_df() -> pd.DataFrame:
    """공고 엑셀(최신 1개)을 읽어와서 공고번호/공고차수 컬럼을 정리한다."""
    latest = _get_latest_excel(DIR_NOTICE, "공고")
    df = pd.read_excel(latest)
    print(f"[INFO] 공고 컬럼: {list(df.columns)}")
    df = _ensure_key_columns(df, "공고")
    return df


# --------------------------------------------------
# 1. 불필요 열 삭제
# --------------------------------------------------
def _drop_unnecessary_columns(df: pd.DataFrame) -> pd.DataFrame:
    drop_cols = [
        "원문",
        "debug",
        "raw_json",
        "json",
    ]
    existing = [c for c in drop_cols if c in df.columns]
    if existing:
        print(f"[CLEAN] 불필요 열 삭제: {existing}")
        df = df.drop(columns=existing)
    return df


# --------------------------------------------------
# 2. 중복열 정리 (*_결과 / *_공고)
# --------------------------------------------------
def _cleanup_duplicated_columns(df: pd.DataFrame) -> pd.DataFrame:
    merge_pairs = [
        ("공고명_결과", "공고명_공고", "공고명"),
        ("공고번호_결과", "공고번호_공고", "공고번호"),
        ("공고차수_결과", "공고차수_공고", "공고차수"),
        ("기초금액_결과", "기초금액_공고", "기초금액"),
        ("추정금액_결과", "추정금액_공고", "추정금액"),
        ("공종명_결과", "공종명_공고", "공종명"),
        ("참가지역_결과", "참가지역_공고", "참가지역"),
        ("낙찰자선정기준_결과", "낙찰자선정기준_공고", "낙찰자선정기준"),
    ]

    for col_a, col_b, col_final in merge_pairs:
        cols_have = [c for c in (col_a, col_b) if c in df.columns]
        if not cols_have:
            continue

        if col_final not in df.columns:
            if (col_a in df.columns) and (col_b in df.columns):
                df[col_final] = df[col_a].combine_first(df[col_b])
            elif col_a in df.columns:
                df[col_final] = df[col_a]
            else:
                df[col_final] = df[col_b]

        # 원본 열들 삭제
        for c in (col_a, col_b):
            if c in df.columns and c != col_final:
                df = df.drop(columns=[c])

    return df


# --------------------------------------------------
# 3. 낙찰자선정기준 복원
# --------------------------------------------------
def _restore_bidwin_rule(df: pd.DataFrame) -> pd.DataFrame:
    candidates = [
        "낙찰자선정기준",
        "bidwinrSlctnAplBssCntnts",
        "낙찰자선정방법",
        "낙찰방법",
        "낙찰자선정방식",
    ]

    if "낙찰자선정기준" not in df.columns:
        df["낙찰자선정기준"] = None

    for col in candidates:
        if col in df.columns:
            df["낙찰자선정기준"] = df["낙찰자선정기준"].fillna(df[col])

    return df


# --------------------------------------------------
# 4. 중복키 정리 (공고번호 + 공고차수)
# --------------------------------------------------
def _drop_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    key_cols = [k for k in ["공고번호", "공고차수"] if k in df.columns]
    if len(key_cols) < 2:
        print("[WARN] 공고번호/공고차수 키가 부족하여 중복 제거를 건너뜁니다.")
        return df

    sort_cols = []
    ascending = []

    if "개찰일시" in df.columns:
        sort_cols.append("개찰일시")
        ascending.append(False)

    for amt_col in ["기초금액", "추정금액", "투찰금액"]:
        if amt_col in df.columns:
            sort_cols.append(amt_col)
            ascending.append(False)

    if not sort_cols:
        print("[INFO] 정렬 기준이 없어 단순 첫 행 유지 기준으로 중복 제거합니다.")
        return df.drop_duplicates(subset=key_cols, keep="first")

    df_sorted = df.sort_values(sort_cols, ascending=ascending)
    df_dedup = df_sorted.drop_duplicates(subset=key_cols, keep="first")
    print(f"[CLEAN] 중복키 제거: {len(df)} → {len(df_dedup)} 행")
    return df_dedup


# --------------------------------------------------
# 5. 컬럼 재정렬
# --------------------------------------------------
def _reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "공고번호",
        "공고차수",
        "공고명",
        "공종명",
        "도급(지역)",
        "참가지역",
        "낙찰자",
        "낙찰금액",
        "기초금액",
        "추정금액",
        "투찰률",
        "개찰일시",
        "수요기관명",
        "발주처명",
        "낙찰자선정기준",
    ]
    existing_pref = [c for c in preferred if c in df.columns]
    others = [c for c in df.columns if c not in existing_pref]
    return df[existing_pref + others]


# --------------------------------------------------
# 6. 전체 정리 + 저장
# --------------------------------------------------
def clean_and_save(
    merged: pd.DataFrame,
    out_dir: Path = OUT_DIR,
    prefix: str = "개찰공고_최종정리",
) -> Path:
    df = merged.copy()

    df = _drop_unnecessary_columns(df)
    df = _cleanup_duplicated_columns(df)
    df = _restore_bidwin_rule(df)
    df = _drop_duplicate_keys(df)
    df = _reorder_columns(df)

    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{prefix}_{now}.xlsx"
    out_path = out_dir / file_name

    df.to_excel(out_path, index=False)
    print(f"[SAVE] 병합/정리 결과 저장: {out_path}")
    return out_path


# --------------------------------------------------
# 7. main
# --------------------------------------------------
def main():
    print("[MAIN] 개찰결과 + 공고 병합 시작 (이미 수집된 공고 활용)")

    result_df = _load_result_df()
    notice_df = _load_notice_df()

    print(f"[MAIN] 개찰결과 행수: {len(result_df)}")
    print(f"[MAIN] 공고 행수: {len(notice_df)}")

    merged = pd.merge(
        result_df,
        notice_df,
        on=["공고번호", "공고차수"],
        how="left",
        suffixes=("_결과", "_공고"),
    )

    print(f"[MAIN] 병합 후 행수: {len(merged)}")

    clean_and_save(merged)

    print("[MAIN] 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] 오류 발생: {e}")
        sys.exit(1)
