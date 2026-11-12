# -*- coding: utf-8 -*-

import sys
import os
import glob
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

from seri_n_data.lockutil import acquire_lock
from seri_n_data.config import TARGET_INDS
from seri_n_data.utils import log
from seri_n_data.fetcher import fetch_ind, filter_rows
from seri_n_data.excel_export import save_excel, backup_old_excels
from seri_n_data.reporter import make_report
from seri_n_data.sender import send_all


# ------------------------------------------------------------
# SPLIT EXCEL 디렉터리
# ------------------------------------------------------------
SPLIT_DIR = Path("/mnt/vol1/n_data/split")


# ------------------------------------------------------------
# SPLIT EXCEL 기반 알림톡 발송
# ------------------------------------------------------------
def send_from_split_excels(bgn_dt: str, end_dt: str):
    """
    이번 실행에서 생성된 지역/업종별 split 엑셀들을 다시 읽어서,
    '알림대상' == 'Y' 이고 '수신번호'가 있는 행만 골라 send_all()로 넘겨 알림톡 발송.

    - 파일명 패턴: 입찰공고_{지역}_{업종코드}_{YYYYMMDD}_{HHMM}.xlsx
    - end_dt(YYYYMMDDHHMM)의 날짜/시간을 이용해 이번 실행분만 선택
    """
    date_str = end_dt[:8]   # YYYYMMDD
    time_str = end_dt[8:12] # HHMM

    pattern = str(SPLIT_DIR / f"입찰공고_*_{date_str}_{time_str}.xlsx")
    files = sorted(glob.glob(pattern))

    if not files:
        log(f"[ALIMTALK][SPLIT] split 엑셀 파일 없음: pattern={pattern}")
        return

    log(f"[ALIMTALK][SPLIT] 대상 split 엑셀 수: {len(files)}")
    all_df_list = []

    for f in files:
        try:
            df = pd.read_excel(f)
        except Exception as e:
            log(f"[ALIMTALK][SPLIT][ERR] 엑셀 읽기 실패: {f} ({e})")
            continue

        # -------- 필수 컬럼 보정 --------
        # 알림대상 없으면 모두 Y로 간주
        if "알림대상" not in df.columns:
            df["알림대상"] = "Y"

        # 수신번호 없으면 이 파일은 발송 의미가 없음
        if "수신번호" not in df.columns:
            log(f"[ALIMTALK][SPLIT] '수신번호' 컬럼 없음, 스킵: {os.path.basename(f)}")
            continue

        # -------- 수신번호 정제 --------
        # NaN → "" 처리, 문자열화 후 공백 제거
        df["수신번호"] = df["수신번호"].astype(str).fillna("").str.strip()

        # 알림대상 == 'Y' 이고, 수신번호가 비어있지 않은 행만 남김
        df = df[(df["알림대상"] == "Y") & (df["수신번호"] != "")]
        if df.empty:
            log(f"[ALIMTALK][SPLIT] 알림대상=Y & 수신번호 있는 행이 없음: {os.path.basename(f)}")
            continue

        df["출처파일"] = os.path.basename(f)
        all_df_list.append(df)

        log(
            f"[ALIMTALK][SPLIT] 사용: {os.path.basename(f)} "
            f"(행 수={len(df)}, 컬럼={list(df.columns)})"
        )

    if not all_df_list:
        log("[ALIMTALK][SPLIT] 최종적으로 보낼 행이 하나도 없음 (알림대상/수신번호 조건 불만족)")
        return

    merged_df = pd.concat(all_df_list, ignore_index=True)

    # -------- 중복 제거 대비: 필수 컬럼 보정 --------
    for col in ["공고번호", "차수", "수신번호"]:
        if col not in merged_df.columns:
            merged_df[col] = ""

    before = len(merged_df)
    # 공고번호 + 차수 + 수신번호 기준 중복 제거 → 같은 사람에게 같은 공고 2번 이상 안 감
    merged_df.drop_duplicates(subset=["공고번호", "차수", "수신번호"], inplace=True)
    after = len(merged_df)

    log(
        f"[ALIMTALK][SPLIT] 병합 후 행 수={after} "
        f"(중복 제거 전={before}, 제거된={before - after})"
    )

    # sender.send_all 은 list[dict] 기반이므로 records 로 변환
    rows_for_send = merged_df.to_dict(orient="records")

    log(f"[ALIMTALK][SPLIT] send_all 호출, rows 개수 = {len(rows_for_send)}")
    if rows_for_send:
        send_all(rows_for_send)
    else:
        log("[ALIMTALK][SPLIT] 보낼 rows가 0개라 send_all 생략")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    # 예전 루트 엑셀 백업 (현재 영향 거의 없음)
    backup_old_excels()

    import argparse

    p = argparse.ArgumentParser()
    # 조회 기간(시간/일) — 둘 다 0이면 기본 24시간
    p.add_argument("--hours", type=float, default=0.0,
                   help="조회 기간(시간 단위, 예: 1.5)")
    p.add_argument("--days", type=float, default=0.0,
                   help="조회 기간(일 단위, 예: 0.05)")
    p.add_argument("--ind", action="append")
    p.add_argument("--no-send", action="store_true")
    a = p.parse_args()

    # ---- 기간 계산 ----
    # days(일)을 시간으로 환산해서 합산
    total_hours = (a.hours or 0.0) + (a.days or 0.0) * 24.0

    # 아무 것도 안 주면 기존처럼 "최근 1일(24시간)"
    if total_hours <= 0:
        total_hours = 24.0

    end = datetime.now()
    begin = end - timedelta(hours=total_hours)

    bgn_dt = begin.strftime("%Y%m%d%H%M")
    end_dt = end.strftime("%Y%m%d%H%M")

    inds = a.ind or TARGET_INDS

    all_rows = []
    for ind in inds:
        log(f"[FETCH] ind={ind} from {bgn_dt} to {end_dt}")
        part = fetch_ind(ind, bgn_dt, end_dt)
        all_rows.extend(part)

    # 1) 업종 필터
    rows = filter_rows(all_rows)

    # 2) 엑셀 저장 (raw + split 생성)
    excel_path = save_excel(rows)

    # 3) 리포트 생성
    if excel_path:
        try:
            make_report(
                excel_path=excel_path,
                bgn_dt_str=bgn_dt,
                end_dt_str=end_dt,
            )
        except Exception as e:
            log(f"[REPORT][ERR] make_report() 실패: {e}")
    else:
        log("[REPORT] excel_path 없음 — make_report 스킵")

    # 4) no-send 옵션이면 여기까지
    if a.no_send:
        log("[NO-SEND] finish")
        return

    # 5) 알림톡 발송: split 엑셀 기준으로 발송
    send_from_split_excels(bgn_dt, end_dt)

    log("[DONE] main_send finished.")


if __name__ == "__main__":
    lock_fd = acquire_lock()

    if lock_fd is None:
        sys.exit(0)

    try:
        main()
    finally:
        try:
            os.close(lock_fd)
        except Exception:
            pass
