
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import json

import re

from datetime import datetime, timedelta

from pathlib import Path



import pandas as pd





# -------- 안전한 출력 함수 --------

def safe_print(*args, **kwargs):

    """

    파일명에 깨진 유니코드가 있어도 에러 안 나게 출력.

    """

    try:

        print(*args, **kwargs)

    except UnicodeEncodeError:

        try:

            msg = " ".join(str(a) for a in args)

            fallback = msg.encode("utf-8", "backslashreplace").decode("ascii", "replace")

            print(fallback)

        except Exception:

            print("[ENCODING ERROR IN PRINT]")





# ===== 설정 부분 =====

BASE_DIR = Path("/mnt/vol1/n_data/raw")   # 엑셀 파일이 있는 디렉터리

BACKUP_DIR = BASE_DIR / "backup"          # 백업 폴더

REP_COL = "대표지역"                      # 대표지역 열 이름



FIX_DAYS = 2            # 최근 며칠간의 파일에 대해 '기타' 재분류 (오늘 + 어제)

DELETE_AFTER_DAYS = 10  # 며칠 지난 파일 삭제





# ===== 지역 추정 로직 =====

REGION_MAP = {

    "서울특별시": ["서울"],

    "부산광역시": ["부산"],

    "대구광역시": ["대구"],

    "인천광역시": ["인천"],

    "광주광역시": ["광주"],

    "대전광역시": ["대전"],

    "울산광역시": ["울산"],

    "세종특별자치시": ["세종"],

    "경기도": ["경기"],

    "강원특별자치도": ["강원특별자치도", "강원도", "강원"],

    "충청북도": ["충북", "충청북도"],

    "충청남도": ["충남", "충청남도"],

    "전라북도": ["전북", "전라북도", "전북특별자치도"],

    "전라남도": ["전남", "전라남도"],

    "경상북도": ["경북", "경상북도"],

    "경상남도": ["경남", "경상남도"],

    "제주특별자치도": ["제주"],

}



TEXT_COL_CANDIDATES = [

    "참가제한지역",

    "참가지역",

    "수요기관",

    "공고기관",

    "주소",

    "공고명",

]





def _parse_date_time_from_name(path: Path):

    """

    파일명에서 (날짜, 시간) 추출.

    예: XXXXX_20251205_0906.xlsx → (date(2025-12-05), "0906")

    """

    try:

        m = re.search(r"(20\d{6})_(\d{4})", path.name)

    except Exception:

        return None, None



    if not m:

        # 날짜만이라도 추출 시도

        m2 = re.search(r"(20\d{6})", path.name)

        if not m2:

            return None, None

        try:

            d = datetime.strptime(m2.group(1), "%Y%m%d").date()

            return d, ""

        except ValueError:

            return None, None



    date_str, time_str = m.group(1), m.group(2)

    try:

        d = datetime.strptime(date_str, "%Y%m%d").date()

    except ValueError:

        return None, None

    return d, time_str





def _get_file_date_from_name(path: Path):

    d, _ = _parse_date_time_from_name(path)

    return d





def infer_region_from_row(row) -> str:

    """

    대표지역이 '기타'인 경우, 다른 컬럼/원문에서 지역을 추정.

    """

    cur = str(row.get(REP_COL) or "").strip()

    if cur and cur != "기타":

        return cur



    # 1) 텍스트 컬럼에서 검색

    texts = []

    for col in TEXT_COL_CANDIDATES:

        if col in row:

            val = row.get(col)

            if pd.notna(val):

                texts.append(str(val))

    joined_text = " ".join(texts)



    for region, keywords in REGION_MAP.items():

        for kw in keywords:

            if kw and kw in joined_text:

                return region



    # 2) '원문' JSON 안에서 검색

    raw_val = row.get("원문")

    if isinstance(raw_val, str) and raw_val.strip():

        try:

            raw_json = json.loads(raw_val)

            if isinstance(raw_json, dict):

                raw_text = " ".join(

                    str(v) for v in raw_json.values() if v is not None

                )

            else:

                raw_text = str(raw_json)

        except Exception:

            raw_text = str(raw_val)



        for region, keywords in REGION_MAP.items():

            for kw in keywords:

                if kw and kw in raw_text:

                    return region



    return "기타"





def fix_regions_in_file(path: Path):

    """

    엑셀 파일에서

    1) 대표지역이 '기타'인 행 재분류

    2) 대표지역이 '대구경북'인 행을 '대구광역시'와 '경상북도' 두 줄로 분리

    """

    safe_print(f"[FILE] 처리 시작: {path}")

    try:

        df = pd.read_excel(path, dtype=str)

    except Exception as e:

        safe_print(f"[WARN] 엑셀 읽기 실패: {path} ({e})")

        return



    if REP_COL not in df.columns:

        safe_print(f"[INFO] {path}: '{REP_COL}' 열 없음 → 건너뜀")

        return



    # 문자열 정리

    df[REP_COL] = df[REP_COL].astype(str).fillna("")



    # ---------- 1단계: '기타' 재분류 ----------

    before_etc = (df[REP_COL] == "기타").sum()

    if before_etc > 0:

        safe_print(f"[INFO] {path}: '기타' {before_etc}건 재분류 시도")

        df[REP_COL] = df.apply(infer_region_from_row, axis=1)

        after_etc = (df[REP_COL] == "기타").sum()

        changed_etc = before_etc - after_etc

        safe_print(

            f"[OK] {path}: '기타' {before_etc}건 → 재분류 {changed_etc}건, 남은 '기타' {after_etc}건"

        )

    else:

        safe_print(f"[INFO] {path}: '기타' 없음 → 재분류 생략")



    # ---------- 2단계: '대구경북' 분리 ----------

    df[REP_COL] = df[REP_COL].astype(str).fillna("")

    mask_dg_gb = df[REP_COL].str.contains("대구경북")



    split_count = int(mask_dg_gb.sum())

    if split_count > 0:

        safe_print(f"[INFO] {path}: '대구경북' {split_count}건 분리 작업")



        # 분리 대상 행

        target = df[mask_dg_gb].copy()



        # 대구용 / 경북용 복제

        daegu_rows = target.copy()

        daegu_rows[REP_COL] = "대구광역시"



        gyeongbuk_rows = target.copy()

        gyeongbuk_rows[REP_COL] = "경상북도"



        # 나머지 행

        others = df[~mask_dg_gb].copy()



        # 합치기: others + 대구 + 경북

        df_new = pd.concat([others, daegu_rows, gyeongbuk_rows], ignore_index=True)



        safe_print(

            f"[SPLIT] {path}: '대구경북' {split_count}건 → "

            f"'대구광역시' {split_count}건 + '경상북도' {split_count}건 (총 {split_count * 2}행 추가)"

        )

    else:

        df_new = df

        safe_print(f"[INFO] {path}: '대구경북' 값 없음 → 분리 작업 생략")



    # ---------- 저장 ----------

    try:

        df_new.to_excel(path, index=False)

        safe_print(f"[SAVE] {path}: 변경사항 저장 완료 (행수: {len(df_new)})")

    except Exception as e:

        safe_print(f"[ERROR] {path} 저장 실패: {e}")





def archive_and_cleanup():

    """

    어제 파일은 백업으로 이동, 10일 지난 파일은 삭제.

    """

    today = datetime.now().date()

    yesterday = today - timedelta(days=1)

    cutoff = today - timedelta(days=DELETE_AFTER_DAYS)



    BACKUP_DIR.mkdir(parents=True, exist_ok=True)



    for path in BASE_DIR.glob("*.xlsx"):

        if path.is_dir():

            continue



        file_date = _get_file_date_from_name(path)

        if not file_date:

            continue



        # 1) 오래된 파일 삭제

        if file_date <= cutoff:

            try:

                path.unlink()

                safe_print(f"[DEL] {path} (파일 날짜: {file_date}) 10일 경과 → 삭제")

            except Exception as e:

                safe_print(f"[ERROR] {path} 삭제 실패: {e}")

            continue



        # 2) 어제 파일 백업 이동

        if file_date == yesterday:

            target = BACKUP_DIR / path.name

            try:

                path.rename(target)

                safe_print(f"[BACKUP] {path} → {target}")

            except Exception as e:

                safe_print(f"[ERROR] {path} 백업 이동 실패: {e}")





def pick_latest_files_by_date(from_date, to_date):

    """

    from_date ~ to_date 범위 안에서,

    각 날짜별로 '마지막 시간의 파일 1개'만 선택.

    """

    candidates = {}



    for path in BASE_DIR.glob("*.xlsx"):

        if path.is_dir():

            continue



        file_date, time_str = _parse_date_time_from_name(path)

        if not file_date:

            continue



        if not (from_date <= file_date <= to_date):

            continue



        # dict에 날짜별로 "가장 늦은 시간" 파일만 유지

        key = file_date

        prev = candidates.get(key)

        if prev is None:

            candidates[key] = (path, time_str)

        else:

            _, prev_time = prev

            if time_str >= prev_time:

                candidates[key] = (path, time_str)



    return [p for (p, _) in candidates.values()]





def fix_regions_recent_files():

    """

    오늘 기준 최근 FIX_DAYS일 안의 파일들 중,

    각 날짜의 '마지막 파일 1개'만 대표지역 재분류 + '대구경북' 분리.

    """

    today = datetime.now().date()

    from_date = today - timedelta(days=FIX_DAYS - 1)



    safe_print(f"[DEBUG] 최근 {FIX_DAYS}일 기준: {from_date} ~ {today}")



    targets = pick_latest_files_by_date(from_date, today)



    if not targets:

        safe_print("[INFO] 대상 파일 없음 (오늘/어제 파일 미존재)")

        return



    safe_print(f"[INFO] 날짜별 마지막 파일 {len(targets)}개만 처리:")

    for p in targets:

        safe_print(f"  - {p}")



    for path in targets:

        fix_regions_in_file(path)





def main():

    safe_print("===== fix_region_and_rotate START =====")

    safe_print(f"[CONF] BASE_DIR = {BASE_DIR}")

    safe_print(f"[CONF] BACKUP_DIR = {BACKUP_DIR}")

    safe_print(f"[CONF] FIX_DAYS = {FIX_DAYS}, DELETE_AFTER_DAYS = {DELETE_AFTER_DAYS}")



    if not BASE_DIR.exists():

        safe_print(f"[ERROR] BASE_DIR 존재하지 않음: {BASE_DIR}")

        return



    safe_print("===== 대표지역 '기타' 재분류 및 '대구경북' 분리 시작 =====")

    fix_regions_recent_files()

    safe_print("===== 백업/삭제 정리 시작 =====")

    archive_and_cleanup()

    safe_print("===== fix_region_and_rotate END =====")





if __name__ == "__main__":

    main()

