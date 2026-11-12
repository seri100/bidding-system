
#sudo tee /home/pi/n_data/seri_n_data/excel_export.py > /dev/null << 'EOF'
# -*- coding: utf-8 -*-

"""
엑셀 저장/분할 + history 관리
"""

import os
import re
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .config import (
    OUTDIR,
    DIR_RAW,
    DIR_SPLIT,
    RETENTION_SPLIT_HISTORY_DAYS,
)

from .utils import log, _norm, sanitize_for_excel
from .region_filter import (
    extract_region_tags,
    get_skip_reason,
    is_target_row,
    classify_region,
    _to_amount,
)

# ------------------------------------------------------
# 대표지역 → 수신번호 매핑
# ------------------------------------------------------

REGION_RECEIVER_MAP: Dict[str, List[str]] = {
    # 대구 → REDACTED_PHONE
    "대구": ["REDACTED_PRIVATE_VALUE"],
    # 경북은 일단 대구와 동일하게 처리 (원하면 나중에 분리 가능)
    "경북": ["REDACTED_PRIVATE_VALUE"],
    # 충북 → REDACTED_PHONE, REDACTED_PHONE
    "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],
    # 세종 → REDACTED_PHONE
    "세종": ["REDACTED_PRIVATE_VALUE"],  # 사용자가 "세종은 REDACTED_PHONE"이라 언급
}

# 전국은 위 모든 지역 번호를 합친 집합으로 구성
ALL_NUMS = []
for nums in REGION_RECEIVER_MAP.values():
    for n in nums:
        if n not in ALL_NUMS:
            ALL_NUMS.append(n)
REGION_RECEIVER_MAP["전국"] = ALL_NUMS

# ------------------------------------------------------
# 예전 루트 엑셀 백업
# ------------------------------------------------------

def backup_old_excels(base_dir: Path = OUTDIR, keep_days: int = 1) -> None:
    try:
        today = datetime.now().date()
        cutoff = today - timedelta(days=keep_days)
        backup_root = base_dir / "backup"
        backup_root.mkdir(exist_ok=True)

        for f in base_dir.glob("*.xlsx"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
            if mtime <= cutoff:
                dstdir = backup_root / mtime.strftime("%Y%m%d")
                dstdir.mkdir(parents=True, exist_ok=True)
                dst = dstdir / f.name
                log(f"[BACKUP] move {f} -> {dst}")
                f.replace(dst)
    except Exception as e:
        log(f"[WARN] backup_old_excels: {e}")

# ------------------------------------------------------
# history 정리
# ------------------------------------------------------

def cleanup_split_history() -> None:
    history_root = DIR_SPLIT / "history"
    if not history_root.exists():
        return

    today = datetime.now().date()
    try:
        for sub in history_root.iterdir():
            if not sub.is_dir():
                continue

            try:
                d = datetime.strptime(sub.name, "%Y%m%d").date()
            except Exception:
                continue

            diff = (today - d).days
            if diff > RETENTION_SPLIT_HISTORY_DAYS:
                log(f"[HISTORY][CLEAN] remove old history dir: {sub} ({diff} days old)")
                try:
                    shutil.rmtree(sub)
                except Exception as e:
                    log(f"[HISTORY][WARN] failed to remove {sub}: {e}")
    except Exception as e:
        log(f"[HISTORY][WARN] cleanup_split_history error: {e}")

# ------------------------------------------------------
# 추정금액 파싱
# ------------------------------------------------------

def _parse_estimate(r: Dict[str, Any], raw: Dict[str, Any]) -> (str, int):
    # r 안에 이미 들어있으면 우선 사용
    cand = [
        r.get("추정금액"),
        raw.get("asignBdgtAmt"),
        raw.get("presmptPrce"),
        raw.get("cntrctAmt"),
    ]
    val_int = 0
    for v in cand:
        val_int = _to_amount(v)
        if val_int > 0:
            break

    if val_int > 0:
        est_str = f"{val_int:,d}"
    else:
        est_str = ""
    return est_str, val_int

# ------------------------------------------------------
# row 변환
# ------------------------------------------------------

def _build_row_dict(r: Dict[str, Any]) -> Dict[str, Any]:
    raw = r.get("원문") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}

    # 공동도급/수요지역/게시일시
    region_display = _norm(r.get("공동도급지역"))
    if not region_display:
        region_display = _norm(raw.get("jntcontrctDutyRgnNm1"))
        if not region_display:
            region_display = _norm(raw.get("cnstrtsiteRgnNm"))

    demand_region = _norm(r.get("수요지역"))
    if not demand_region:
        demand_region = _norm(raw.get("cnstrtsiteRgnNm"))

    bid_notice_dt = _norm(raw.get("bidNtceDt") or r.get("게시일시"))

    # 추정금액
    est_str, est_val = _parse_estimate(r, raw)
    jnt_str = r.get("공동도급비율", "")

    # 대표지역 계산
    rep_region = classify_region(region_display, est_val, bool(region_display))

    # 지역태그 계산 (대표지역/공동도급/수요지역 순으로 우선)
    tag_source = (
        r.get("대표지역")
        or rep_region
        or region_display
        or demand_region
        or ""
    )
    tag = extract_region_tags(tag_source)

    skip_reason = get_skip_reason(tag)

    base: Dict[str, Any] = {
        "공고업종코드": r.get("공고업종코드", ""),
        "공고번호": r.get("공고번호", ""),
        "차수": r.get("차수", ""),
        "공고명": r.get("공고명", ""),
        "입찰마감일시": r.get("입찰마감일시", ""),
        "공동도급지역": region_display,
        "수요지역": demand_region,
        "게시일시": bid_notice_dt,
    }

    # 알림대상 / SKIP이유
    if is_target_row(r):
        base["알림대상"] = "Y"
        base["SKIP이유"] = ""
    else:
        base["알림대상"] = "N"
        base["SKIP이유"] = skip_reason

    # 수신번호: 대표지역 기준으로 매핑
    receivers: List[str] = []
    if base["알림대상"] == "Y":
        if rep_region in REGION_RECEIVER_MAP:
            receivers = REGION_RECEIVER_MAP[rep_region]
        else:
            receivers = []
    base["수신번호"] = ",".join(receivers)

    base["지역태그"] = tag
    base["추정금액"] = est_str
    base["추정금액_원"] = est_val
    base["공동도급비율"] = jnt_str
    base["대표지역"] = rep_region
    base["원문"] = json.dumps(raw, ensure_ascii=False)

    # 엑셀에서 싫어하는 문자 제거
    for k, v in list(base.items()):
        base[k] = sanitize_for_excel(v)

    return base

# ------------------------------------------------------
# 엑셀 저장 (통합 + 지역/업종 split)
# ------------------------------------------------------

def save_excel(rows: List[Dict[str, Any]]) -> Optional[str]:
    if not rows:
        return None

    now = datetime.now()
    now_str = now.strftime("%Y%m%d_%H%M")

    # -------- 통합 엑셀 --------
    main_path = DIR_RAW / f"입찰공고_{now_str}.xlsx"
    df = pd.DataFrame([_build_row_dict(r) for r in rows])

    cols = [
        "공고업종코드", "공고번호", "차수", "공고명",
        "입찰마감일시", "공동도급지역", "수요지역", "게시일시",
        "알림대상", "SKIP이유", "지역태그", "수신번호",
        "추정금액", "추정금액_원", "공동도급비율", "대표지역", "원문",
    ]
    df = df.reindex(columns=cols)

    main_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(main_path, index=False)
    log(f"[SAVE] {main_path}")

    # -------- 지역/업종 분할 엑셀 --------
    DIR_SPLIT.mkdir(parents=True, exist_ok=True)

    if "지역태그" in df.columns and "공고업종코드" in df.columns:
        grouped = df.groupby(["지역태그", "공고업종코드"], dropna=False)

        history_root = DIR_SPLIT / "history"
        today_dir = history_root / now.strftime("%Y%m%d")
        today_dir.mkdir(parents=True, exist_ok=True)

        for (tag_str, ind_code), g in grouped:
            if not isinstance(tag_str, str) or not tag_str.strip():
                continue

            first_tag = tag_str.split(",")[0].strip() or "미지정지역"
            safe_region = re.sub(r"[^0-9A-Za-z가-힣]+", "_", first_tag).strip("_") or "미지정지역"
            safe_ind = re.sub(r"[^0-9A-Za-z]+", "_", str(ind_code)).strip("_") or "미지정업종"

            split_name = f"입찰공고_{safe_region}_{safe_ind}_{now_str}.xlsx"
            split_path = DIR_SPLIT / split_name

            pattern = f"입찰공고_{safe_region}_{safe_ind}_*.xlsx"
            for old in DIR_SPLIT.glob(pattern):
                try:
                    dst = today_dir / old.name
                    log(f"[HISTORY] move {old} -> {dst}")
                    old.replace(dst)
                except Exception as e:
                    log(f"[HISTORY][WARN] move failed {old} -> {dst}: {e}")

            g.to_excel(split_path, index=False)
            log(f"[SAVE][SPLIT] {split_path}")

    # -------- history 7일 정리 --------
    cleanup_split_history()

    return str(main_path)
#EOF
