#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_water.py — K-water 전자조달 자동 수집/저장

목표
- 한국수자원공사 전자조달시스템 입찰공고를 수집한다.
- n_data와 동일한 기준(업종, 금액, 전국/지역, 수신자, 중복/이력, raw/split/report 저장)을 적용한다.
- 기본 저장 경로는 Windows 기준 Z:\\VOL1\\bid\\bid\\bid-water 이다.

주의
- K-water 전자조달은 WebSquare 기반 동적 화면이므로 Playwright 브라우저 수집을 사용한다.
- 사이트 화면/버튼 id가 바뀌는 경우에도 최대한 동작하도록 텍스트/표/링크/상세화면을 여러 방식으로 파싱한다.
- 알림톡 발송은 포함하지 않는다. 대신 n_data와 같은 수신번호/알림대상 산정 결과를 생성 파일에 저장한다.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import shlex
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except Exception as e:  # pragma: no cover
    print("[FATAL] pandas가 필요합니다. pip install -r requirements.txt 실행 후 다시 실행하세요.", file=sys.stderr)
    raise

try:
    import fcntl  # type: ignore  # Linux/macOS
except Exception:  # pragma: no cover
    fcntl = None

try:
    import msvcrt  # type: ignore  # Windows
except Exception:  # pragma: no cover
    msvcrt = None

KST_FMT = "%Y%m%d%H%M"
DISPLAY_DT_FMT = "%Y-%m-%d %H:%M"

KWATER_URL = "https://ebid.kwater.or.kr/wq/index.do?w2xPath=%2fui%2findex.xml"
# K-water WebSquare 화면은 메뉴 클릭형 메인 URL 외에 view 파라미터 직접 진입이 되는 경우가 있다.
# Buster/Chromium headless 환경에서 메뉴 클릭 후 목록 iframe을 못 읽는 경우를 대비한 후보 URL.
KWATER_LIST_CANDIDATE_URLS = [
    KWATER_URL,
    "https://ebid.kwater.or.kr/wq/index.do?view=%2Fbidpblanc%2Fbidpblancsttus%2FBIDBD32000001.xml&w2xPath=%2Fui%2Findex.xml",
    "https://ebid.kwater.or.kr/wq/index.do?view=BIDBD32000001&w2xPath=%2Fui%2Findex.xml",
]
KWATER_DETAIL_URL = (
    "https://ebid.kwater.or.kr/wq/index.do?tndrPbanno={bid_no}"
    "&view=%2Fbidpblanc%2Fbidpblancsttus%2FBIDBD32000002.xml"
    "&w2xPath=%2Fui%2Findex.xml"
)

DEFAULT_WINDOWS_BASE = r"REDACTED_PRIVATE_VALUE"
DEFAULT_LINUX_BASE = "REDACTED_PRIVATE_VALUE"

TARGET_INDS = {"0037", "0038", "0039", "0040", "6202"}
MIN_BUDGET = int(os.environ.get("BID_WATER_MIN_BUDGET", "30000000") or "30000000")
NATION_THRESHOLD = int(os.environ.get("BID_WATER_NATION_THRESHOLD", "1000000000") or "1000000000")
MAX_DAYS = int(os.environ.get("BID_WATER_MAX_DAYS", "15") or "15")
GRACE_MINUTES = int(os.environ.get("BID_WATER_GRACE_MINUTES", "3") or "3")
DEFAULT_MAX_DETAILS = int(os.environ.get("BID_WATER_MAX_DETAILS", "80") or "80")

NATION_COMMON = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]
NATION_0037 = ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]
LOCAL_COMMON = {
    "세종": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],
    "충북": ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"],
    "대구": ["REDACTED_PRIVATE_VALUE"],
    "경북": ["REDACTED_PRIVATE_VALUE"],
}

OUT_COLUMNS = [
    "공고업종코드",
    "공고업종명",
    "공고번호",
    "차수",
    "공고명",
    "수요기관",
    "계약방법",
    "제한방법",
    "낙찰방법세부기준",
    "기초금액",
    "추정가격",
    "발주금액",
    "시작일시",
    "입찰마감일시",
    "게시일",
    "대표지역",
    "지역제한",
    "공동도급지역",
    "공동도급지역_추가",
    "공동도급비율",
    "알림대상",
    "수신번호",
    "알림톡상태",
    "첨부파일폴더",
    "첨부파일수",
    "첨부저장상태",
    "첨부파일목록",
    "상세링크",
    "원문요약",
]


def _now() -> datetime:
    return datetime.now()


def ymdhm(dt: datetime) -> str:
    return dt.strftime(KST_FMT)


def parse_ymdhm(value: str) -> datetime:
    value = str(value or "").strip()
    if not re.fullmatch(r"\d{12}", value):
        raise ValueError(f"날짜는 YYYYMMDDHHMM 12자리여야 합니다: {value!r}")
    return datetime.strptime(value, KST_FMT)


def parse_any_datetime(value: Any) -> Optional[datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    s = s.replace(".", "-").replace("/", "-")
    s = re.sub(r"\s+", " ", s)
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%y-%m-%d %H:%M:%S",
        "%y-%m-%d %H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y-%m-%d",
        "%y-%m-%d",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(s[: len(datetime.now().strftime(fmt))] if "%" in fmt else s, fmt)
        except Exception:
            continue
    m = re.search(r"(20\d{2}|\d{2})[-.\/]?(\d{1,2})[-.\/]?(\d{1,2})\s+(\d{1,2}):(\d{2})", s)
    if m:
        yy = int(m.group(1))
        if yy < 100:
            yy += 2000
        return datetime(yy, int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
    return None


def fmt_dt(value: Any) -> str:
    dt = value if isinstance(value, datetime) else parse_any_datetime(value)
    return dt.strftime(DISPLAY_DT_FMT) if dt else str(value or "").strip()


def amount_to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return 0
    s = str(value).strip()
    if not s or s.lower() in {"none", "nan", "null", "-"}:
        return 0
    # K-water 발주계획 등에서 백만원 단위가 보일 경우 '백만원' 문구가 있으면 원 단위로 환산
    is_million = "백만원" in s
    s2 = re.sub(r"[^0-9\-]", "", s)
    if not s2 or s2 == "-":
        return 0
    try:
        n = int(s2)
        return n * 1_000_000 if is_million else n
    except Exception:
        return 0


def fmt_amount(value: Any) -> str:
    n = amount_to_int(value)
    if n == 0:
        s = str(value or "").strip()
        return s if s and s not in {"0", "0원"} else ""
    return f"{n:,}"


def norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def norm_region(value: Any) -> str:
    s = norm_text(value)
    s = (
        s.replace("특별자치시", "")
        .replace("특별자치도", "")
        .replace("광역시", "")
        .replace("특별시", "")
        .replace("도", "")
        .strip()
    )
    mapping = {
        "충청북": "충북",
        "충북": "충북",
        "경상북": "경북",
        "경북": "경북",
        "대구": "대구",
        "세종": "세종",
    }
    for src, dst in mapping.items():
        if src in s:
            return dst
    return s


def safe_filename(value: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", str(value or "").strip())
    s = re.sub(r"\s+", "_", s)
    return s[:120] or "NA"


@dataclass
class Paths:
    base: Path
    raw: Path
    raw_download: Path
    split: Path
    report: Path
    logs: Path
    state: Path
    debug: Path
    history_file: Path
    last_run_file: Path
    lock_file: Path
    run_log_file: Path


def default_base() -> Path:
    env = os.environ.get("BID_WATER_BASE", "").strip()
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(DEFAULT_WINDOWS_BASE)
    return Path(DEFAULT_LINUX_BASE)


def build_paths(base: Path) -> Paths:
    p = Paths(
        base=base,
        raw=base / "raw",
        raw_download=base / "raw_download",
        split=base / "split",
        report=base / "report",
        logs=base / "logs",
        state=base / "state",
        debug=base / "debug",
        history_file=base / "state" / "history.csv",
        last_run_file=base / "state" / "last_run.txt",
        lock_file=base / "state" / "main_water.lock",
        run_log_file=base / "logs" / "run_main_water.log",
    )
    for d in [p.raw, p.raw_download, p.split, p.report, p.logs, p.state, p.debug]:
        d.mkdir(parents=True, exist_ok=True)
    return p


PATHS: Optional[Paths] = None


def log(msg: str) -> None:
    line = f"[{_now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    if PATHS:
        try:
            with PATHS.run_log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


class SingleInstanceLock:
    def __init__(self, path: Path):
        self.path = path
        self.fp = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fp = self.path.open("a+", encoding="utf-8")
        self.fp.seek(0, os.SEEK_END)
        self.fp.write(f"pid={os.getpid()} start={_now().isoformat()}\n")
        self.fp.flush()
        if os.name == "nt" and msvcrt is not None:
            try:
                msvcrt.locking(self.fp.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError(f"이미 실행 중입니다: {self.path}")
        elif fcntl is not None:
            try:
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RuntimeError(f"이미 실행 중입니다: {self.path}")
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.fp:
                if os.name == "nt" and msvcrt is not None:
                    try:
                        self.fp.seek(0)
                        msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                elif fcntl is not None:
                    try:
                        fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
                self.fp.close()
        finally:
            self.fp = None


def load_last_run(paths: Paths) -> Optional[datetime]:
    try:
        s = paths.last_run_file.read_text(encoding="utf-8").strip()
        if not s:
            return None
        dt = parse_ymdhm(s)
        log(f"[STATE] last_run 로드: {s}")
        return dt
    except FileNotFoundError:
        return None
    except Exception as e:
        log(f"[STATE][WARN] last_run 로드 실패: {e}")
        return None


def save_last_run(paths: Paths, dt: datetime) -> None:
    s = ymdhm(dt)
    paths.last_run_file.write_text(s + "\n", encoding="utf-8")
    log(f"[STATE] last_run 저장: {s}")


def compute_window(args: argparse.Namespace, paths: Paths) -> Tuple[datetime, datetime]:
    now = _now()
    force_from = (args.force_from or os.environ.get("FORCE_FROM") or "").strip()
    force_to = (args.force_to or os.environ.get("FORCE_TO") or "").strip()
    if force_from or force_to:
        start = parse_ymdhm(force_from) if force_from else now - timedelta(hours=max(1, args.hours or 1))
        end = parse_ymdhm(force_to) if force_to else now
        log(f"[FORCE] 조회기간 override: {ymdhm(start)} ~ {ymdhm(end)}")
        return start, end

    if args.hours is not None:
        hours = max(1, int(args.hours))
        start = now - timedelta(hours=hours)
        log(f"[MAIN] --hours={hours} 명시 → 최근 {hours}시간 조회")
    else:
        last = load_last_run(paths)
        first_run_today = last is None or last.date() < now.date()
        if first_run_today and 6 <= now.hour <= 9:
            start = datetime.combine(now.date() - timedelta(days=1), datetime.min.time())
            log("[MAIN] 오늘 첫 실행(아침) → 전날 00:00부터 조회")
        elif last:
            start = last - timedelta(minutes=GRACE_MINUTES)
            log(f"[MAIN] last_run 기반 조회 시작: {ymdhm(start)} (버퍼 {GRACE_MINUTES}분)")
        else:
            start = now - timedelta(hours=1)
            log("[MAIN] last_run 없음 → 최근 1시간 조회")

    end = now
    if end - start > timedelta(days=MAX_DAYS):
        start = end - timedelta(days=MAX_DAYS)
        log(f"[MAIN][WARN] 조회기간 {MAX_DAYS}일 초과 → {ymdhm(start)}부터로 조정")
    return start, end


def make_bid_key(row: Dict[str, Any]) -> str:
    bid_no = norm_text(row.get("공고번호") or row.get("bid_no") or row.get("tndrPbanno"))
    bid_ord = norm_text(row.get("차수") or row.get("bid_ord") or "000") or "000"
    return f"{bid_no}-{bid_ord}" if bid_no else ""


def load_history(paths: Paths) -> set:
    keys = set()
    if not paths.history_file.exists():
        return keys
    try:
        with paths.history_file.open("r", encoding="REDACTED_PRIVATE_VALUE", newline="") as f:
            for r in csv.DictReader(f):
                key = norm_text(r.get("key") or r.get("공고키"))
                if key:
                    keys.add(key)
    except Exception as e:
        log(f"[HISTORY][WARN] 이력 로드 실패: {e}")
    return keys


def append_history(paths: Paths, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        return
    exists = paths.history_file.exists()
    with paths.history_file.open("a", encoding="REDACTED_PRIVATE_VALUE", newline="") as f:
        fieldnames = ["ts", "key", "공고번호", "차수", "공고명", "대표지역", "알림대상", "수신번호"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        now_s = _now().strftime("%Y-%m-%d %H:%M:%S")
        for row in rows:
            writer.writerow(
                {
                    "ts": now_s,
                    "key": make_bid_key(row),
                    "공고번호": row.get("공고번호", ""),
                    "차수": row.get("차수", "000"),
                    "공고명": row.get("공고명", ""),
                    "대표지역": row.get("대표지역", ""),
                    "알림대상": row.get("알림대상", ""),
                    "수신번호": row.get("수신번호", ""),
                }
            )
    log(f"[HISTORY] append rows={len(rows)} -> {paths.history_file}")


def load_existing_report_keys(paths: Paths) -> set:
    keys = set()
    files = sorted(paths.report.glob("입찰리포트_수자원공사_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return keys
    latest = files[0]
    try:
        df = pd.read_excel(latest, dtype=str)
        for _, r in df.iterrows():
            bid_no = norm_text(r.get("공고번호"))
            bid_ord = norm_text(r.get("차수") or "000") or "000"
            if bid_no:
                keys.add(f"{bid_no}-{bid_ord}")
        log(f"[DEDUP][REPORT] 기준파일={latest} keys={len(keys)}")
    except Exception as e:
        log(f"[DEDUP][REPORT][WARN] 기준파일 로드 실패: {e}")
    return keys



def _selenium_visible_elements(page: Any, selector: str) -> List[Any]:
    """Return visible Selenium elements for selector. Empty for Playwright/other adapters."""
    if not hasattr(page, "driver"):
        return []
    try:
        from selenium.webdriver.common.by import By  # type: ignore
        els = page.driver.find_elements(By.CSS_SELECTOR, selector)
    except Exception:
        return []
    out = []
    for el in els:
        try:
            if el.is_displayed():
                out.append(el)
        except Exception:
            pass
    return out


def _selenium_el_meta(driver: Any, el: Any) -> str:
    try:
        return driver.execute_script(
            """
            const e = arguments[0];
            const parts = [];
            let n = e;
            for (let i=0; n && i<6; i++, n=n.parentElement) {
              const id = n.id ? ('#'+n.id) : '';
              const cls = n.className && typeof n.className === 'string' ? ('.'+n.className.trim().replace(/\s+/g,'.')) : '';
              parts.push(n.tagName.toLowerCase()+id+cls);
            }
            const txt = (e.innerText || e.value || e.title || '').replace(/\s+/g,' ').trim();
            return txt + ' | ' + parts.join(' < ');
            """,
            el,
        ) or ""
    except Exception:
        return ""


def _selenium_click_element(page: Any, el: Any, timeout: int = 2500) -> bool:
    """Click using real mouse events first. Falls back to DOM click."""
    if not hasattr(page, "driver"):
        return False
    driver = page.driver
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", el)
        time.sleep(0.2)
    except Exception:
        pass
    try:
        from selenium.webdriver.common.action_chains import ActionChains  # type: ignore
        ActionChains(driver).move_to_element(el).pause(0.1).click().perform()
        page.wait_for_timeout(900)
        return True
    except Exception:
        pass
    try:
        el.click()
        page.wait_for_timeout(900)
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", el)
        page.wait_for_timeout(900)
        return True
    except Exception:
        return False


def maybe_click_text(page: Any, texts: Sequence[str], timeout: int = 2500) -> bool:
    """Generic visible text click. Avoid using this for query/search buttons."""
    for text in texts:
        for exact in (True, False):
            try:
                loc = page.get_by_text(text, exact=exact)
                if loc.count() > 0:
                    loc.first.click(timeout=timeout)
                    page.wait_for_timeout(800)
                    log(f"[BROWSER] click text={text!r}")
                    return True
            except Exception:
                continue
    return False


def click_left_menu_bid_category(page: Any, category: str = "공사", timeout: int = 2500) -> bool:
    """Click K-water left navigation item: 입찰공고 > 공사/전체/용역/내자/물품.

    v3 clicked any visible '조회' text and sometimes landed in the global integrated-search
    no-result screen. v4 navigates by stable left-menu ids/titles first and avoids header search.
    """
    if hasattr(page, "driver"):
        driver = page.driver
        selectors = [
            "#mf_wfm_left_GEN_NAV_LIST_0_GEN_LEVEL1_0_ANC_LEVEL1",
            "#mf_wfm_left a[title='1차메뉴']",
        ]
        # Open/activate 입찰공고 depth. Prefer the explicit anchor containing 입찰공고.
        clicked_parent = False
        for sel in selectors:
            for el in _selenium_visible_elements(page, sel):
                try:
                    txt = norm_text(el.text or el.get_attribute("title") or el.get_attribute("value") or "")
                except Exception:
                    txt = ""
                if "입찰공고" in txt:
                    if _selenium_click_element(page, el, timeout=timeout):
                        log(f"[BROWSER][NAV] click left 입찰공고: {_selenium_el_meta(driver, el)[:180]}")
                        clicked_parent = True
                        break
            if clicked_parent:
                break
        page.wait_for_timeout(1200)

        cat_selectors = [
            f"#mf_wfm_left_GEN_NAV_LIST_0_GEN_LEVEL1_0_GEN_LEVEL2 a[title='{category}']",
            f"#mf_wfm_left a[title='{category}']",
            f"a[id*='GEN_NAV_LIST_0_GEN_LEVEL1_0_GEN_LEVEL2'][title='{category}']",
        ]
        for sel in cat_selectors:
            els = _selenium_visible_elements(page, sel)
            for el in els:
                try:
                    txt = norm_text(el.text or el.get_attribute("title") or el.get_attribute("value") or "")
                except Exception:
                    txt = ""
                if txt == category or category in txt:
                    if _selenium_click_element(page, el, timeout=timeout):
                        log(f"[BROWSER][NAV] click left category={category!r}: {_selenium_el_meta(driver, el)[:180]}")
                        page.wait_for_timeout(2500)
                        return True
        log(f"[BROWSER][NAV][WARN] left category click failed: {category!r}")
        return False

    # Playwright fallback.
    try:
        maybe_click_text(page, ["입찰공고"])
        ok = maybe_click_text(page, [category, "전체"])
        page.wait_for_timeout(2500)
        return ok
    except Exception:
        return False


def maybe_click_content_query_button(page: Any, timeout: int = 2500) -> bool:
    """Click the search/query button in the content area only.

    This deliberately excludes the global header/title search buttons:
    mf_header_group_btnSearch and mf_wfm_title_btnTotSearch. Those produce
    '결과없음 | K-water 전자조달시스템' when the keyword box is empty.
    """
    if hasattr(page, "driver"):
        driver = page.driver
        try:
            from selenium.webdriver.common.by import By  # type: ignore
            candidates = driver.find_elements(By.CSS_SELECTOR, "a,button,input[type='button'],input[type='submit']")
        except Exception:
            candidates = []
        scored: List[Tuple[int, Any, str]] = []
        for el in candidates:
            try:
                if not el.is_displayed():
                    continue
                txt = norm_text((el.text or "") + " " + (el.get_attribute("value") or "") + " " + (el.get_attribute("title") or ""))
                if not re.search(r"(^|\s)(조회|검색)(\s|$)|조회|검색", txt):
                    continue
                meta = _selenium_el_meta(driver, el)
                meta_l = meta.lower()
                # Exclude global integrated-search controls. This was the v3 failure point.
                if any(bad in meta_l for bad in [
                    "mf_header_group", "mf_wfm_title", "btntotsearch", "btnheader", "searchtext", "searchdiv"
                ]):
                    log(f"[BROWSER][QUERY] skip global search button: {meta[:160]}")
                    continue
                score = 0
                if "mf_wframe_content" in meta_l or "content" in meta_l:
                    score += 100
                if "btn" in meta_l:
                    score += 10
                if "조회" in txt:
                    score += 5
                scored.append((score, el, meta))
            except Exception:
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            score, el, meta = scored[0]
            if _selenium_click_element(page, el, timeout=timeout):
                log(f"[BROWSER][QUERY] click content query button score={score}: {meta[:180]}")
                return True
        log("[BROWSER][QUERY][WARN] content-area 조회 버튼을 찾지 못했습니다. global 통합검색 버튼은 클릭하지 않았습니다.")
        return False

    # Playwright fallback: scope to content if possible, then avoid global title/header search.
    try:
        for selector in [
            "#mf_wframe_content a:has-text('조회')",
            "#mf_content-area a:has-text('조회')",
            "#mf_wframe_content input[value='조회']",
            "#mf_content-area input[value='조회']",
            "button:has-text('조회')",
        ]:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.click(timeout=timeout)
                page.wait_for_timeout(900)
                log(f"[BROWSER][QUERY] click selector={selector!r}")
                return True
    except Exception:
        pass
    log("[BROWSER][QUERY][WARN] content-area 조회 버튼을 찾지 못했습니다.")
    return False


def maybe_fill_date_inputs(page: Any, start: datetime, end: datetime) -> None:
    values = [
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
    ]
    try:
        inputs = page.locator("input")
        count = min(inputs.count(), 80)
        date_like = []
        for i in range(count):
            inp = inputs.nth(i)
            attrs = " ".join(
                norm_text(inp.get_attribute(a))
                for a in ["id", "name", "title", "placeholder", "class"]
                if inp.get_attribute(a)
            )
            attrs_l = attrs.lower()
            typ = norm_text(inp.get_attribute("type")).lower()
            if typ in {"hidden", "button", "submit", "checkbox", "radio"}:
                continue
            # Never fill global search keyword boxes.
            if any(bad in attrs_l for bad in ["searchtext", "검색어", "mf_header_group", "mf_wfm_title"]):
                continue
            if re.search(r"일자|일시|date|from|to|시작|종료|게시|공고", attrs, re.I):
                date_like.append(inp)
        if len(date_like) >= 2:
            date_like[0].fill(values[0], timeout=1500)
            date_like[1].fill(values[1], timeout=1500)
            log("[BROWSER] date inputs filled as YYYY-MM-DD")
        elif len(date_like) == 1:
            date_like[0].fill(values[0], timeout=1500)
            log("[BROWSER] one date input filled")
        else:
            log("[BROWSER][DATE][WARN] content date inputs not found")
    except Exception as e:
        log(f"[BROWSER][WARN] 날짜 입력 자동 설정 실패: {e}")


def log_current_page_state(page: Any, label: str) -> None:
    try:
        title = page.driver.title if hasattr(page, "driver") else page.evaluate("document.title")
    except Exception:
        title = ""
    try:
        body = page.evaluate("() => (document.body && document.body.innerText || '').replace(/\\s+/g,' ').slice(0,500)")
    except Exception:
        body = ""
    log(f"[BROWSER][STATE] {label}: title={title!r} body[:500]={body!r}")


def _xpath_literal(value: str) -> str:
    """Return a safe XPath string literal."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


class SeleniumLocator:
    """Tiny adapter that mimics the Playwright methods used by this script."""

    def __init__(self, page: "SeleniumPage", selector: Optional[str] = None, elements: Optional[List[Any]] = None):
        self.page = page
        self.selector = selector
        self.elements = elements

    def _resolve(self) -> List[Any]:
        if self.elements is not None:
            return list(self.elements)
        if not self.selector:
            return []
        from selenium.webdriver.common.by import By  # type: ignore
        try:
            return self.page.driver.find_elements(By.CSS_SELECTOR, self.selector)
        except Exception:
            return []

    def count(self) -> int:
        return len(self._resolve())

    def nth(self, index: int) -> "SeleniumLocator":
        els = self._resolve()
        if 0 <= index < len(els):
            return SeleniumLocator(self.page, elements=[els[index]])
        return SeleniumLocator(self.page, elements=[])

    @property
    def first(self) -> "SeleniumLocator":
        return self.nth(0)

    def _first_el(self) -> Any:
        els = self._resolve()
        if not els:
            raise RuntimeError("selenium locator has no elements")
        return els[0]

    def click(self, timeout: Optional[int] = None) -> None:
        el = self._first_el()
        try:
            self.page.driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", el)
            time.sleep(0.15)
        except Exception:
            pass
        try:
            el.click()
        except Exception:
            self.page.driver.execute_script("arguments[0].click();", el)

    def get_attribute(self, name: str) -> str:
        try:
            value = self._first_el().get_attribute(name)
            return value or ""
        except Exception:
            return ""

    def fill(self, value: str, timeout: Optional[int] = None) -> None:
        el = self._first_el()
        try:
            self.page.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        try:
            el.clear()
        except Exception:
            pass
        try:
            el.send_keys(value)
        except Exception:
            self.page.driver.execute_script(
                "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true})); arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                el,
                value,
            )

    def inner_text(self, timeout: Optional[int] = None) -> str:
        try:
            return self._first_el().text or ""
        except Exception:
            return ""


class SeleniumPage:
    def __init__(self, driver: Any):
        self.driver = driver

    def set_default_timeout(self, timeout: int) -> None:
        return None

    def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 60000) -> None:
        try:
            self.driver.set_page_load_timeout(max(5, int(timeout / 1000)))
        except Exception:
            pass
        self.driver.get(url)

    def wait_for_load_state(self, state: str = "networkidle", timeout: int = 10000) -> None:
        # Selenium has no direct networkidle equivalent. Give WebSquare scripts time to settle.
        time.sleep(min(max(timeout / 1000.0, 0.5), 3.0))

    def wait_for_timeout(self, ms: int) -> None:
        time.sleep(max(ms, 0) / 1000.0)

    def locator(self, selector: str) -> SeleniumLocator:
        return SeleniumLocator(self, selector=selector)

    def get_by_text(self, text: str, exact: bool = False) -> SeleniumLocator:
        from selenium.webdriver.common.by import By  # type: ignore
        lit = _xpath_literal(text)
        cond = f"normalize-space(.) = {lit}" if exact else f"contains(normalize-space(.), {lit})"
        xpath = f"//*[not(self::script) and not(self::style) and {cond}]"
        try:
            els = self.driver.find_elements(By.XPATH, xpath)
        except Exception:
            els = []
        visible = []
        for el in els:
            try:
                if el.is_displayed():
                    visible.append(el)
            except Exception:
                pass
        priority = {"button": 0, "a": 1, "input": 2, "span": 3, "td": 4, "div": 5, "li": 6}
        def key(el: Any) -> Tuple[int, int]:
            try:
                tag = (el.tag_name or "").lower()
                txt = el.text or ""
                return (priority.get(tag, 9), len(txt))
            except Exception:
                return (9, 9999)
        visible.sort(key=key)
        return SeleniumLocator(self, elements=visible)

    def evaluate(self, script: str) -> Any:
        code = str(script or "").strip()
        if code.startswith("() =>") or code.startswith("async () =>") or code.startswith("function"):
            code = "return (" + code + ")();"
        elif not re.match(r"^\s*(return|var |let |const )", code):
            code = "return " + code
        return self.driver.execute_script(code)

    def content(self) -> str:
        try:
            return self.driver.page_source or ""
        except Exception:
            return ""

    def close(self) -> None:
        return None


def build_selenium_driver(paths: Paths, headless: bool) -> Any:
    try:
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.chrome.options import Options  # type: ignore
        from selenium.webdriver.chrome.service import Service  # type: ignore
    except Exception as e:
        raise RuntimeError("selenium이 필요합니다. pip install selenium 또는 requirements.txt 재설치가 필요합니다.") from e

    options = Options()
    if headless:
        # Chromium 92 on Raspberry Pi OS Buster supports the legacy headless flag.
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("REDACTED_PRIVATE_VALUE")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1100")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--disable-features=TranslateUI")

    chromium_executable = (
        os.environ.get("SELENIUM_CHROMIUM_EXECUTABLE_PATH")
        or os.environ.get("CHROMIUM_EXECUTABLE_PATH")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or ""
    ).strip()
    if chromium_executable:
        options.binary_location = chromium_executable
        log(f"[SELENIUM] using chromium executable: {chromium_executable}")

    chromium_args = os.environ.get("CHROMIUM_ARGS", "").strip()
    if chromium_args:
        for arg in shlex.split(chromium_args):
            options.add_argument(arg)

    try:
        paths.raw_download.mkdir(parents=True, exist_ok=True)
        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": str(paths.raw_download.resolve()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            },
        )
    except Exception:
        pass

    chromedriver_path = (
        os.environ.get("CHROMEDRIVER_PATH")
        or shutil.which("chromedriver")
        or "REDACTED_PRIVATE_VALUE"
    )
    if chromedriver_path and Path(chromedriver_path).exists():
        service = Service(chromedriver_path)
        log(f"[SELENIUM] using chromedriver: {chromedriver_path}")
    else:
        service = Service()
        log("[SELENIUM] using chromedriver from PATH")

    return webdriver.Chrome(service=service, options=options)


def collect_kwater_rows_selenium(start: datetime, end: datetime, paths: Paths, headless: bool, max_details: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    driver = build_selenium_driver(paths, headless=headless)
    page = SeleniumPage(driver)
    try:
        # 1차: 기본 메인 URL + 메뉴 클릭. 실패 시 직접 view URL 후보를 순차 시도한다.
        for attempt_idx, url in enumerate(KWATER_LIST_CANDIDATE_URLS, start=1):
            snapshot_file = paths.debug / f"kwater_snapshot_try{attempt_idx}_{ymdhm(_now())}.html"
            screenshot_file = paths.debug / f"kwater_snapshot_try{attempt_idx}_{ymdhm(_now())}.png"
            log(f"[SELENIUM] open try{attempt_idx}: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2200)

                # 메뉴형 진입에서는 공사 탭이 실제 입찰공고 목록인 경우가 많다.
                log_current_page_state(page, f"try{attempt_idx} after load")
                click_left_menu_bid_category(page, "공사")
                log_current_page_state(page, f"try{attempt_idx} after nav")
                maybe_fill_date_inputs(page, start, end)
                maybe_click_content_query_button(page)
                page.wait_for_timeout(4500)

                rows = extract_rows_from_current_page(page)
                log(f"[COLLECT][SELENIUM] try{attempt_idx} top/frame rows={len(rows)}")

                if not rows:
                    # WebSquare가 iframe 안에 검색조건/그리드를 두는 경우가 있어 프레임 내부에서도 조회 동작을 재시도한다.
                    log(f"[SELENIUM] try{attempt_idx} rows=0 → iframe 내부 조회/추출 재시도")
                    selenium_retry_query_in_frames(page, start, end)
                    page.wait_for_timeout(4500)
                    rows = extract_rows_from_current_page(page)
                    log(f"[COLLECT][SELENIUM] try{attempt_idx} after iframe retry rows={len(rows)}")

                try:
                    snapshot_file.write_text(page.content(), encoding="utf-8")
                    log(f"[DEBUG] snapshot saved: {snapshot_file}")
                except Exception:
                    pass
                try:
                    driver.save_screenshot(str(screenshot_file))
                    log(f"[DEBUG] screenshot saved: {screenshot_file}")
                except Exception:
                    pass
                try:
                    dump_selenium_page_diagnostics(page, paths, f"try{attempt_idx}")
                except Exception as e:
                    log(f"[DEBUG][WARN] diagnostics dump 실패: {e}")

                if rows:
                    break
            except Exception as e:
                log(f"[SELENIUM][WARN] try{attempt_idx} 실패: {e}")
                continue

        if rows:
            enrich_rows_with_detail_pages_selenium(page, rows, max_details=max_details)
        else:
            log("[COLLECT][SELENIUM][WARN] 모든 후보 URL/iframe 조회 후에도 목록 행을 찾지 못했습니다. debug snapshot/png/diagnostics를 확인하세요.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return rows



def enrich_rows_with_detail_pages_selenium(page: SeleniumPage, rows: List[Dict[str, Any]], max_details: int) -> None:
    for idx, row in enumerate(rows[:max_details], start=1):
        bid_no = norm_text(row.get("공고번호"))
        if not bid_no:
            continue
        href = norm_text(row.get("상세링크"))
        if not href or href == "about:blank":
            href = KWATER_DETAIL_URL.format(bid_no=bid_no)
            row["상세링크"] = href
        try:
            page.goto(href, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=8000)
            page.wait_for_timeout(800)
            detail = parse_detail_page(page)
            if detail:
                row.update({k: v for k, v in detail.items() if v not in (None, "")})
                row.update(normalize_kwater_row(row))
            if idx % 10 == 0:
                log(f"[DETAIL][SELENIUM] enriched {idx}/{min(len(rows), max_details)}")
        except Exception as e:
            log(f"[DETAIL][SELENIUM][WARN] {bid_no} 상세 조회 실패: {e}")


def collect_kwater_rows(start: datetime, end: datetime, paths: Paths, headless: bool, max_details: int) -> List[Dict[str, Any]]:
    engine = (os.environ.get("BID_WATER_BROWSER_ENGINE") or os.environ.get("BROWSER_ENGINE") or "auto").strip().lower()
    if engine in {"selenium", "webdriver"}:
        return collect_kwater_rows_selenium(start, end, paths, headless=headless, max_details=max_details)

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # type: ignore
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as e:
        if engine in {"playwright", "pw"}:
            raise RuntimeError("playwright가 필요합니다. pip install -r requirements.txt 및 playwright install chromium 실행 필요") from e
        log(f"[BROWSER][WARN] Playwright 사용 불가: {e}. Selenium으로 대체 실행합니다.")
        return collect_kwater_rows_selenium(start, end, paths, headless=headless, max_details=max_details)

    rows: List[Dict[str, Any]] = []
    snapshot_file = paths.debug / f"kwater_snapshot_{ymdhm(_now())}.html"

    with sync_playwright() as p:
        launch_kwargs: Dict[str, Any] = {"headless": headless}
        chromium_executable = (
            os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
            or os.environ.get("CHROMIUM_EXECUTABLE_PATH")
            or ""
        ).strip()
        if chromium_executable:
            launch_kwargs["executable_path"] = chromium_executable
            log(f"[BROWSER] using external chromium executable: {chromium_executable}")
        chromium_args = os.environ.get("CHROMIUM_ARGS", "").strip()
        if chromium_args:
            launch_kwargs["args"] = shlex.split(chromium_args)
            log(f"[BROWSER] chromium args: {launch_kwargs['args']}")
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            accept_downloads=True,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()
        page.set_default_timeout(8000)
        try:
            log(f"[BROWSER] open {KWATER_URL}")
            page.goto(KWATER_URL, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=25000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(1800)

            log_current_page_state(page, "playwright after load")
            click_left_menu_bid_category(page, "공사")
            log_current_page_state(page, "playwright after nav")
            maybe_fill_date_inputs(page, start, end)
            maybe_click_content_query_button(page)
            page.wait_for_timeout(2500)

            rows = extract_rows_from_current_page(page)
            log(f"[COLLECT] current page rows={len(rows)}")

            if not rows:
                downloaded = try_download_excel(page, paths)
                if downloaded:
                    rows = read_downloaded_excel(downloaded)
                    log(f"[COLLECT] downloaded excel rows={len(rows)}")

            if rows:
                enrich_rows_with_detail_pages(context, rows, max_details=max_details)

            try:
                snapshot_file.write_text(page.content(), encoding="utf-8")
                log(f"[DEBUG] snapshot saved: {snapshot_file}")
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    return rows

def extract_rows_from_current_page(page: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows.extend(extract_rows_from_current_context(page))
    # Selenium에서는 WebSquare 본문이 iframe/frame 안에 들어가는 경우가 있어 모든 프레임도 탐색한다.
    if hasattr(page, "driver"):
        try:
            frame_rows = extract_rows_from_selenium_frames(page)
            if frame_rows:
                log(f"[COLLECT][SELENIUM] iframe rows={len(frame_rows)}")
            rows.extend(frame_rows)
        except Exception as e:
            log(f"[COLLECT][SELENIUM][WARN] iframe rows 추출 실패: {e}")
            try:
                page.driver.switch_to.default_content()
            except Exception:
                pass
    return dedupe_by_bid_no(rows)


def extract_rows_from_current_context(page: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows.extend(extract_from_tables(page))
    rows.extend(extract_from_anchors(page))
    rows.extend(extract_from_body_text(page))
    rows.extend(extract_from_websquare_grids(page))
    return rows


def extract_rows_from_selenium_frames(page: Any, max_depth: int = 4) -> List[Dict[str, Any]]:
    from selenium.webdriver.common.by import By  # type: ignore
    driver = page.driver
    rows: List[Dict[str, Any]] = []

    def walk(depth: int, path: str) -> None:
        if depth > max_depth:
            return
        try:
            frame_elements = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        except Exception:
            frame_elements = []
        for idx in range(len(frame_elements)):
            try:
                # frame 전환 후 DOM이 바뀔 수 있으므로 매번 다시 찾는다.
                frame_elements2 = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
                if idx >= len(frame_elements2):
                    continue
                frame = frame_elements2[idx]
                driver.switch_to.frame(frame)
                here = extract_rows_from_current_context(page)
                if here:
                    log(f"[COLLECT][SELENIUM] frame {path}/{idx} rows={len(here)}")
                    rows.extend(here)
                walk(depth + 1, f"{path}/{idx}")
                driver.switch_to.parent_frame()
            except Exception as e:
                log(f"[COLLECT][SELENIUM][WARN] frame {path}/{idx} 접근 실패: {e}")
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                # 실패 후 다음 형제 프레임 탐색을 위해 부모 context 복구가 어려우면 최상위에서 중단
                return

    try:
        driver.switch_to.default_content()
        walk(0, "root")
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    return rows


def selenium_retry_query_in_frames(page: Any, start: datetime, end: datetime, max_depth: int = 4) -> bool:
    """Try filling dates and clicking 조회/검색 inside every Selenium frame."""
    from selenium.webdriver.common.by import By  # type: ignore
    driver = page.driver
    clicked = False

    def visit_current(depth: int, path: str) -> None:
        nonlocal clicked
        try:
            before = len(extract_rows_from_current_context(page))
        except Exception:
            before = 0
        try:
            click_left_menu_bid_category(page, "공사", timeout=1200)
            maybe_fill_date_inputs(page, start, end)
            if maybe_click_content_query_button(page, timeout=1500):
                clicked = True
                log(f"[SELENIUM] iframe {path} 조회/검색 클릭")
                page.wait_for_timeout(1200)
        except Exception as e:
            log(f"[SELENIUM][WARN] iframe {path} 조회 재시도 실패: {e}")
        try:
            after = len(extract_rows_from_current_context(page))
            if before or after:
                log(f"[SELENIUM] iframe {path} rows before/after={before}/{after}")
        except Exception:
            pass

    def walk(depth: int, path: str) -> None:
        if depth > max_depth:
            return
        visit_current(depth, path)
        try:
            frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        except Exception:
            frames = []
        for idx in range(len(frames)):
            try:
                frames2 = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
                if idx >= len(frames2):
                    continue
                driver.switch_to.frame(frames2[idx])
                walk(depth + 1, f"{path}/{idx}")
                driver.switch_to.parent_frame()
            except Exception as e:
                log(f"[SELENIUM][WARN] iframe {path}/{idx} 조회 walk 실패: {e}")
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                return

    try:
        driver.switch_to.default_content()
        walk(0, "root")
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    return clicked


def dump_selenium_page_diagnostics(page: Any, paths: Paths, label: str) -> None:
    """Save a compact diagnostics file to understand WebSquare DOM/frames on Raspberry Pi."""
    from selenium.webdriver.common.by import By  # type: ignore
    driver = page.driver
    ts = ymdhm(_now())
    out = paths.debug / f"kwater_diag_{label}_{ts}.txt"
    lines: List[str] = []

    def current_summary(path: str) -> None:
        try:
            title = driver.title
        except Exception:
            title = ""
        try:
            url = driver.current_url
        except Exception:
            url = ""
        try:
            body = norm_text(driver.find_element(By.TAG_NAME, "body").text)[:3000]
        except Exception:
            body = ""
        lines.append(f"## frame={path}")
        lines.append(f"title={title}")
        lines.append(f"url={url}")
        lines.append(f"body[:3000]={body}")
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, "button, a, input, select, textarea, [role='button'], [onclick]")[:220]
            lines.append(f"elements={len(elems)}")
            for i, el in enumerate(elems[:120]):
                try:
                    tag = el.tag_name
                    txt = norm_text(el.text)[:80]
                    attrs = {k: norm_text(el.get_attribute(k))[:100] for k in ["id", "name", "title", "placeholder", "value", "class", "type", "href", "onclick"]}
                    lines.append(f"  [{i}] <{tag}> text={txt!r} attrs={attrs}")
                except Exception:
                    continue
        except Exception as e:
            lines.append(f"elements_error={e}")

    def walk(depth: int, path: str) -> None:
        if depth > 3:
            return
        current_summary(path)
        try:
            frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        except Exception:
            frames = []
        lines.append(f"frame_count_at_{path}={len(frames)}")
        for idx in range(len(frames)):
            try:
                frames2 = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
                if idx >= len(frames2):
                    continue
                driver.switch_to.frame(frames2[idx])
                walk(depth + 1, f"{path}/{idx}")
                driver.switch_to.parent_frame()
            except Exception as e:
                lines.append(f"frame {path}/{idx} error={e}")
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                return

    try:
        driver.switch_to.default_content()
        walk(0, "root")
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    out.write_text("\n".join(lines), encoding="utf-8")
    log(f"[DEBUG] diagnostics saved: {out}")


def extract_from_websquare_grids(page: Any) -> List[Dict[str, Any]]:
    """Fallback for WebSquare/grid-style DIV lists that are not normal tables."""
    try:
        items = page.evaluate(
            """
            () => {
              const out = [];
              const seen = new Set();
              const candidates = Array.from(document.querySelectorAll('div, span, li, tr, [role="row"], [class*="grid"], [id*="grid"], [class*="w2grid"], [id*="grd"]'));
              for (const el of candidates) {
                const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
                if (!text || text.length < 20 || text.length > 2000) continue;
                if (!/B\d{9,12}/.test(text)) continue;
                if (seen.has(text)) continue;
                seen.add(text);
                let href = '';
                const a = el.querySelector && el.querySelector('a[href]');
                if (a) href = a.href || '';
                out.push({text, href});
              }
              return out;
            }
            """
        )
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for item in items or []:
        text = norm_text(item.get("text"))
        href = norm_text(item.get("href"))
        bid_no = extract_kwater_bid_no(text + " " + href)
        if not bid_no:
            continue
        title = guess_title_from_chunk(text, bid_no)
        out.append(normalize_kwater_row({"공고번호": bid_no, "공고명": title, "상세링크": href, "원문요약": text}))
    return out


def extract_from_tables(page: Any) -> List[Dict[str, Any]]:
    tables = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('table')).map((table) => {
          const trs = Array.from(table.querySelectorAll('tr'));
          return trs.map((tr) => Array.from(tr.querySelectorAll('th,td')).map((td) => (td.innerText || '').trim()));
        })
        """
    )
    out: List[Dict[str, Any]] = []
    for table in tables or []:
        if not table or len(table) < 2:
            continue
        # 가장 헤더처럼 보이는 행 선택
        header_idx = None
        for i, r in enumerate(table[:5]):
            joined = " ".join(r)
            if any(k in joined for k in ["공고명", "공고번호", "게시일", "발주금액", "입찰"]):
                header_idx = i
                break
        if header_idx is None:
            continue
        headers = clean_headers(table[header_idx])
        for r in table[header_idx + 1 :]:
            if len([c for c in r if norm_text(c)]) < 2:
                continue
            item = {headers[i] if i < len(headers) else f"col{i+1}": c for i, c in enumerate(r)}
            row = normalize_kwater_row(item)
            if row.get("공고번호") or row.get("공고명"):
                out.append(row)
    return out


def clean_headers(headers: Sequence[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out = []
    for i, h in enumerate(headers):
        h2 = norm_text(h) or f"col{i+1}"
        h2 = h2.replace("\n", " ")
        if h2 in seen:
            seen[h2] += 1
            h2 = f"{h2}_{seen[h2]}"
        else:
            seen[h2] = 1
        out.append(h2)
    return out


def extract_from_anchors(page: Any) -> List[Dict[str, Any]]:
    anchors = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a')).map((a) => {
          const tr = a.closest('tr');
          return {text: (a.innerText || '').trim(), href: a.href || '', parent: tr ? (tr.innerText || '').trim() : ((a.parentElement && a.parentElement.innerText) || '').trim()};
        })
        """
    )
    out: List[Dict[str, Any]] = []
    for a in anchors or []:
        text = norm_text(a.get("text"))
        href = norm_text(a.get("href"))
        parent = norm_text(a.get("parent"))
        if not (text or parent):
            continue
        bid_no = extract_kwater_bid_no(href + " " + parent + " " + text)
        if not bid_no:
            continue
        row = normalize_kwater_row({"공고번호": bid_no, "공고명": text, "상세링크": href, "원문요약": parent})
        out.append(row)
    return out


def extract_from_body_text(page: Any) -> List[Dict[str, Any]]:
    try:
        body = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    # B로 시작하는 K-water 공고번호 주변 텍스트 추출
    for m in re.finditer(r"\bB\d{9,12}\b", body):
        start = max(0, m.start() - 240)
        end = min(len(body), m.end() + 380)
        chunk = norm_text(body[start:end])
        bid_no = m.group(0)
        title = guess_title_from_chunk(chunk, bid_no)
        out.append(normalize_kwater_row({"공고번호": bid_no, "공고명": title, "원문요약": chunk}))
    return out


def guess_title_from_chunk(chunk: str, bid_no: str) -> str:
    s = chunk.replace(bid_no, " ")
    parts = [p.strip() for p in re.split(r"\s{2,}|\t|\n", s) if p.strip()]
    best = ""
    for p in parts:
        if 8 <= len(p) <= 120 and not re.search(r"공고번호|게시일|발주금액|전자입찰", p):
            best = p
            break
    return best


def extract_kwater_bid_no(text: str) -> str:
    m = re.search(r"\bB\d{9,12}\b", text or "")
    return m.group(0) if m else ""


def try_download_excel(page: Any, paths: Paths) -> Optional[Path]:
    triggers = ["엑셀", "Excel", "EXCEL", "다운로드", "저장"]
    for text in triggers:
        try:
            loc = page.get_by_text(text, exact=False)
            if loc.count() <= 0:
                continue
            with page.expect_download(timeout=5000) as download_info:
                loc.first.click(timeout=2500)
            download = download_info.value
            suggested = safe_filename(download.suggested_filename or f"kwater_{ymdhm(_now())}.xlsx")
            dest = paths.raw_download / f"{ymdhm(_now())}_{suggested}"
            download.save_as(str(dest))
            log(f"[DOWNLOAD] {dest}")
            return dest
        except Exception:
            continue
    return None


def read_downloaded_excel(path: Path) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(path, dtype=str)
    except Exception:
        try:
            df = pd.read_csv(path, dtype=str, encoding="REDACTED_PRIVATE_VALUE")
        except Exception as e:
            log(f"[DOWNLOAD][WARN] 파일 읽기 실패: {path} / {e}")
            return []
    rows = []
    for rec in df.fillna("").to_dict("records"):
        rows.append(normalize_kwater_row(rec))
    return rows


def enrich_rows_with_detail_pages(context: Any, rows: List[Dict[str, Any]], max_details: int) -> None:
    page = context.new_page()
    try:
        for idx, row in enumerate(rows[:max_details], start=1):
            bid_no = norm_text(row.get("공고번호"))
            if not bid_no:
                continue
            href = norm_text(row.get("상세링크"))
            if not href or href == "about:blank":
                href = KWATER_DETAIL_URL.format(bid_no=bid_no)
                row["상세링크"] = href
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                page.wait_for_timeout(600)
                detail = parse_detail_page(page)
                if detail:
                    row.update({k: v for k, v in detail.items() if v not in (None, "")})
                    row.update(normalize_kwater_row(row))
                if idx % 10 == 0:
                    log(f"[DETAIL] enriched {idx}/{min(len(rows), max_details)}")
            except Exception as e:
                log(f"[DETAIL][WARN] {bid_no} 상세 조회 실패: {e}")
    finally:
        page.close()



def parse_detail_page(page: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    try:
        body_text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        body_text = ""

    # WebSquare 상세 화면은 일반 table DOM 안에 숨은 접근성 텍스트/헤더가 섞여
    # th/td 2칸씩 단순 매핑하면 공고번호=회원사업자등록번호, 공고명=없음처럼
    # 헤더와 값이 밀리는 경우가 있다. 먼저 DOM pair를 읽되, 값 검증을 통과한 것만 사용한다.
    try:
        pairs = page.evaluate(
            """
            () => {
              const out = [];
              for (const tr of Array.from(document.querySelectorAll('tr'))) {
                const cells = Array.from(tr.querySelectorAll('th,td')).map(td => (td.innerText || '').trim()).filter(Boolean);
                if (cells.length >= 2) {
                  for (let i = 0; i < cells.length - 1; i += 2) out.push([cells[i], cells[i+1]]);
                }
              }
              return out;
            }
            """
        )
        for k, v in pairs or []:
            assign_detail_pair(result, k, v)
    except Exception:
        pass

    # 본문 텍스트의 라벨 순서 기반 파싱을 우선값으로 사용한다.
    # 이 방식은 "제한방법 낙찰자결정방법 소액전자"처럼 값이 비어 있는 라벨도
    # 다음 라벨을 값으로 잘못 잡지 않는다.
    text_values = extract_detail_values_from_text(body_text)
    for k, v in text_values.items():
        if not v:
            continue
        if k not in result or not result.get(k) or is_bad_detail_value(k, result.get(k, "")):
            result[k] = v
        elif k in {"공고번호", "공고명", "게시일", "계약방법", "낙찰방법세부기준", "발주금액", "수요기관", "입찰마감일시", "시작일시"}:
            # 핵심 항목은 DOM pair보다 본문 라벨 파싱값이 더 정확하다.
            result[k] = v

    if body_text:
        result.setdefault("원문요약", norm_text(body_text[:1200]))
    result = normalize_kwater_row(result)
    return result


# 정확히 매칭할 상세 라벨만 둔다. "공고명"처럼 너무 넓은 라벨은
# "공고명(영문) 없음"을 공고명으로 덮어쓰는 원인이 되므로 사용하지 않는다.
DETAIL_LABELS = {
    "공고명(한글)": "공고명",
    "공고번호": "공고번호",
    "게시일": "게시일",
    "계약방법": "계약방법",
    "제한방법": "제한방법",
    "낙찰자결정방법": "낙찰방법세부기준",
    "낙찰방법": "낙찰방법세부기준",
    "발주금액": "발주금액",
    "기초금액": "기초금액",
    "추정가격": "추정가격",
    "전자입찰여부": "전자입찰여부",
    "입찰서제출마감일시": "입찰마감일시",
    "입찰마감일시": "입찰마감일시",
    "입찰서접수마감일시": "입찰마감일시",
    "시작일시": "시작일시",
    "현장위치": "현장위치",
    "공사현장": "현장위치",
    "수요기관": "수요기관",
    "발주부서": "수요기관",
    "부서명": "수요기관",
    "참가지역": "지역제한",
    "지역제한": "지역제한",
}

# 라벨 순서 기반 텍스트 파싱에 사용할 라벨. 값으로 저장하지 않는 라벨도
# 다음 라벨 경계로는 필요하므로 포함한다.
DETAIL_TEXT_LABELS = [
    ("공고명(한글)", "공고명"),
    ("공고명(영문)", None),
    ("공고번호", "공고번호"),
    ("발주계획번호", None),
    ("게시일", "게시일"),
    ("계약방법", "계약방법"),
    ("제한방법", "제한방법"),
    ("낙찰자결정방법", "낙찰방법세부기준"),
    ("입찰보증금", None),
    ("발주금액", "발주금액"),
    ("전자입찰여부", "전자입찰여부"),
    ("지문입찰여부", None),
    ("공동계약허용여부", None),
    ("공동이행여부", None),
    ("입찰장소", None),
    ("분담이행여부", None),
    ("고정비 합계금액(A)", None),
    ("자격 및 유의사항", None),
    ("담당자정보", None),
    ("입찰진행부서", None),
    ("부서명", "수요기관"),
    ("전산장애", None),
    ("전화번호", None),
    ("입찰집행순서", None),
    ("입찰진행순서", None),
    ("진행순서", None),
    ("진행구분", None),
    ("진행구분명", None),
    ("시작일시", "시작일시"),
    ("종료일시", "입찰마감일시"),
    ("입찰서제출마감일시", "입찰마감일시"),
    ("입찰마감일시", "입찰마감일시"),
]


def compact_label(s: Any) -> str:
    return re.sub(r"\s+", "", norm_text(s))


def assign_detail_pair(result: Dict[str, Any], label: Any, value: Any) -> None:
    k = norm_text(label)
    v = clean_detail_value(value)
    if not k or not v:
        return
    ck = compact_label(k)

    # 영문 공고명은 대부분 "없음"이며, 한글 공고명을 덮어쓰면 안 된다.
    if "공고명(영문)" in k or "공고명영문" in ck:
        return

    for label_key, out_key in DETAIL_LABELS.items():
        lk = compact_label(label_key)
        if ck == lk or ck.endswith(lk):
            if is_bad_detail_value(out_key, v):
                return
            result[out_key] = v
            return


def clean_detail_value(value: Any) -> str:
    v = norm_text(value)
    v = re.sub(r"^[\s:：,./-]+|[\s:：,./-]+$", "", v)
    v = re.sub(r"\s+", " ", v)
    return v


def is_bad_detail_value(key: str, value: Any) -> bool:
    v = clean_detail_value(value)
    if not v:
        return True
    compact = compact_label(v)
    label_compacts = {compact_label(lbl) for lbl, _ in DETAIL_TEXT_LABELS}
    if compact in label_compacts:
        return True
    if "에대한표이다" in compact or "공고내용으로" in compact or "그리드시작" == compact:
        return True
    if key == "공고번호":
        return not bool(extract_kwater_bid_no(v))
    if key == "공고명":
        if v in {"없음", "-", "해당없음"}:
            return True
        if "공고명(영문)" in v or "공고번호" in v:
            return True
        return len(v) < 4
    if key in {"게시일", "시작일시", "입찰마감일시"}:
        return not bool(re.search(r"\d{4}[-./]?\d{2}[-./]?\d{2}", v))
    if key in {"기초금액", "추정가격", "발주금액"}:
        return not bool(re.search(r"\d", v))
    if key in {"제한방법", "낙찰방법세부기준", "계약방법"}:
        if any(compact.startswith(compact_label(lbl)) for lbl, _ in DETAIL_TEXT_LABELS):
            return True
    if key in {"지역제한", "공동도급지역", "공동도급지역_추가"}:
        if "공고문" in v and "참고" in v:
            return True
    return False


def extract_detail_values_from_text(body_text: str) -> Dict[str, str]:
    text = norm_text(body_text)
    if not text:
        return {}
    matches = []
    labels = [lbl for lbl, _ in DETAIL_TEXT_LABELS]
    # 긴 라벨 우선으로 찾되, 같은 위치 중복은 가장 긴 라벨만 남긴다.
    for label, out_key in DETAIL_TEXT_LABELS:
        for m in re.finditer(re.escape(label), text):
            matches.append((m.start(), m.end(), label, out_key))
    if not matches:
        return {}
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    dedup = []
    used_starts = set()
    for item in matches:
        if item[0] in used_starts:
            continue
        used_starts.add(item[0])
        dedup.append(item)

    out: Dict[str, str] = {}
    for i, (st, en, label, out_key) in enumerate(dedup):
        next_st = dedup[i + 1][0] if i + 1 < len(dedup) else min(len(text), en + 160)
        value = clean_detail_value(text[en:next_st])
        if not out_key:
            continue
        if is_bad_detail_value(out_key, value):
            continue
        # 같은 라벨이 여러 번 나오면 실제 값이 있는 뒤쪽 occurrence를 우선한다.
        out[out_key] = value

    # K-water 가격입찰 진행일시 보강

    # 입찰공고 게시기간이 아닌 가격입찰서 제출 시작·마감일시를 사용한다.

    dt_pattern = r"(\d{4}[-./]\d{2}[-./]\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?)"

    price_patterns = [

        r"가격입찰\s+가격입찰서제출\s+" + dt_pattern + r"\s+" + dt_pattern,

        r"가격입찰서제출\s+" + dt_pattern + r"\s+" + dt_pattern,

    ]



    for pattern in price_patterns:

        m = re.search(pattern, text)

        if m:

            out["시작일시"] = clean_detail_value(m.group(1))

            out["입찰마감일시"] = clean_detail_value(m.group(2))

            break



    # 공고번호는 대괄호 제목에도 노출되므로 추가 보강한다.
    bid = extract_kwater_bid_no(text)
    if bid:
        out["공고번호"] = bid
    return out


def sanitize_row_values(row: Dict[str, Any]) -> Dict[str, Any]:
    """헤더-값 불일치를 일으키는 WebSquare 접근성/헤더 문구를 정리한다."""
    bid_no = extract_kwater_bid_no(norm_text(row.get("공고번호")))
    if not bid_no:
        bid_no = extract_kwater_bid_no(" ".join(norm_text(v) for v in row.values()))
    if bid_no:
        row["공고번호"] = bid_no
        detail = norm_text(row.get("상세링크"))
        if not detail or bid_no not in detail:
            row["상세링크"] = KWATER_DETAIL_URL.format(bid_no=bid_no)

    parsed = extract_detail_values_from_text(norm_text(row.get("원문요약")))
    for key in ["공고명", "수요기관", "게시일", "계약방법", "제한방법", "낙찰방법세부기준", "발주금액", "시작일시", "입찰마감일시"]:
        val = norm_text(row.get(key))
        if is_bad_detail_value(key, val):
            row[key] = parsed.get(key, "")

    for key in ["지역제한", "공동도급지역", "공동도급지역_추가"]:
        if is_bad_detail_value(key, row.get(key, "")):
            row[key] = ""
    return row


def normalize_kwater_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    lower = {norm_text(k).lower(): v for k, v in raw.items()}

    def pick(*names: str) -> str:
        for name in names:
            if name in raw and norm_text(raw.get(name)):
                return norm_text(raw.get(name))
            n = name.lower()
            if n in lower and norm_text(lower[n]):
                return norm_text(lower[n])
        # 느슨한 포함 검색
        for key, val in raw.items():
            kk = norm_text(key)
            if any(name in kk for name in names) and norm_text(val):
                return norm_text(val)
        return ""

    bid_no = pick("공고번호", "입찰공고번호", "tndrPbanno", "bidNo", "bid_no")
    # 공고번호는 반드시 K-water 형식(B + 숫자)이어야 한다. WebSquare 표 헤더가 밀리면
    # "회원사업자등록번호" 같은 문구가 들어올 수 있으므로 전체 원문에서 다시 찾는다.
    valid_bid_no = extract_kwater_bid_no(bid_no)
    source_text = " ".join(norm_text(v) for v in raw.values() if v is not None)
    if valid_bid_no:
        bid_no = valid_bid_no
    else:
        bid_no = extract_kwater_bid_no(source_text)

    title = pick("공고명", "공고명(한글)", "입찰명", "건명", "제목", "tndrNm")
    parsed_from_text = extract_detail_values_from_text(source_text)
    if is_bad_detail_value("공고명", title) and parsed_from_text.get("공고명"):
        title = parsed_from_text["공고명"]

    detail = pick("상세링크", "href", "link", "url")
    if bid_no and (not detail or bid_no not in detail):
        detail = KWATER_DETAIL_URL.format(bid_no=bid_no)

    row = {
        "공고업종코드": pick("공고업종코드", "업종코드", "indstrytyCd", "mainCnsttyCd", "cnsttyCd"),
        "공고업종명": pick("공고업종명", "업종명", "공종", "업종", "mainCnsttyNm", "indstrytyNm"),
        "공고번호": bid_no,
        "차수": pick("차수", "bidNtceOrd", "공고차수") or "000",
        "공고명": title,
        "수요기관": pick("수요기관", "발주부서", "발주기관", "수요처", "dept", "dminsttNm"),
        "계약방법": pick("계약방법", "cntrctMthdNm"),
        "제한방법": pick("제한방법", "lmtMthdNm"),
        "낙찰방법세부기준": pick("낙찰방법세부기준", "낙찰자결정방법", "낙찰방법", "sucsfbidMthdNm"),
        "기초금액": pick("기초금액", "baseAmount", "bssAmt"),
        "추정가격": pick("추정가격", "추정금액", "presmptPrce", "presmptPrceAmt", "estimatPrce", "estimatPrice"),
        "발주금액": pick("발주금액", "bdgtAmt", "budget", "amount"),
        "시작일시": fmt_dt(pick("시작일시", "입찰서접수개시일시", "bidBeginDt", "bidBeginDttm")),
        "입찰마감일시": fmt_dt(pick("입찰마감일시", "입찰서제출마감일시", "입찰서접수마감일시", "투찰마감", "bidClseDt")),
        "게시일": fmt_dt(pick("게시일", "공고일", "등록일", "ntceDt")),
        "대표지역": pick("대표지역", "지역", "지역제한", "참가지역", "prtcptLmtRgnNm", "prtcptPsblRgnNm"),
        "지역제한": pick("지역제한", "참가지역", "prtcptLmtRgnNm", "prtcptPsblRgnNm"),
        "공동도급지역": pick("공동도급지역", "jntcontrctDutyRgnNm1"),
        "공동도급지역_추가": pick("공동도급지역_추가", "jntcontrctDutyRgnNm2"),
        "공동도급비율": pick("공동도급비율", "rgnDutyJntcontrctRt"),
        "상세링크": detail,
        "원문요약": pick("원문요약") or source_text[:1200],
    }
    if not row["공고업종코드"]:
        row["공고업종코드"] = infer_industry_code(row)
    row = sanitize_row_values(row)
    if not row["공고업종코드"]:
        row["공고업종코드"] = infer_industry_code(row)
    if not row["공고업종명"]:
        row["공고업종명"] = infer_industry_name(row["공고업종코드"])
    return row


def infer_industry_code(row: Dict[str, Any]) -> str:

    blob = " ".join(

        norm_text(row.get(k))

        for k in [

            "공고업종명",

            "공고명",

            "원문요약",

            "계약방법",

            "제한방법",

        ]

    )



    # 소방·소화설비가 전기공사로 잘못 분류되지 않도록 먼저 판정한다.

    fire_match = (

        "소방" in blob

        or "소화설비" in blob

        or "소화 설비" in blob

    )



    if fire_match and "전기" in blob:

        return "0038"

    if fire_match and "기계" in blob:

        return "0039"

    if fire_match:

        return "0040"



    if re.search(r"전기공사|전기 공사", blob):

        return "0037"



    if re.search(r"기계설비|기계가스|냉난방|공조|보일러|펌프|배관", blob):

        return "6202"



    return ""

def infer_industry_name(code: str) -> str:
    return {
        "0037": "전기공사",
        "0038": "전문소방시설공사업(전기)",
        "0039": "전문소방시설공사업(기계)",
        "0040": "일반소방시설공사업",
        "6202": "기계설비공사업",
    }.get(code, "")


def decide_scope(row: Dict[str, Any]) -> str:
    method = norm_text(row.get("낙찰방법세부기준") or row.get("계약방법")).replace(" ", "")
    if "소액수의" in method:
        return "지역"
    if "10억원미만" in method or "10억미만" in method:
        return "지역"
    if "10억원이상" in method or "10억이상" in method:
        return "전국"
    amount = amount_to_int(row.get("추정가격")) or amount_to_int(row.get("발주금액")) or amount_to_int(row.get("기초금액"))
    return "전국" if amount >= NATION_THRESHOLD else "지역"


def decide_local_region(row: Dict[str, Any]) -> str:
    for key in ["공동도급지역", "지역제한", "대표지역", "수요기관", "공고명", "원문요약"]:
        reg = norm_region(row.get(key))
        if reg in LOCAL_COMMON:
            return reg
    blob = " ".join(norm_text(row.get(k)) for k in ["수요기관", "공고명", "원문요약"])
    for src, dst in [("세종", "세종"), ("충청북도", "충북"), ("충북", "충북"), ("대구", "대구"), ("경상북도", "경북"), ("경북", "경북")]:
        if src in blob:
            return dst
    return ""


def decide_receivers(row: Dict[str, Any]) -> List[str]:

    code = norm_text(row.get("공고업종코드")) or infer_industry_code(row)



    if code not in TARGET_INDS:

        return []



    scope = decide_scope(row)



    # 추정가격 10억원 이상: 전국

    if scope == "전국":

        # 전국 전기공사(0037)는 지정된 1명에게만 알림

        if code == "0037":

            return ["REDACTED_PRIVATE_VALUE"]



        # 전국 소방·기계설비는 등록된 4명 모두에게 알림

        if code in {"0038", "0039", "0040", "6202"}:

            return NATION_COMMON.copy()



        return []



    # 추정가격 10억원 미만: 지역

    if scope == "지역":

        # 지역 전기공사(0037)는 알림 제외

        if code == "0037":

            return []



        # 지역 소방·기계설비는 세종·충북·대구·경북 해당자만

        if code in {"0038", "0039", "0040", "6202"}:

            local_region = decide_local_region(row)

            return LOCAL_COMMON.get(local_region, []).copy()



    return []

def apply_final_rule(row: Dict[str, Any]) -> Dict[str, Any]:
    code = norm_text(row.get("공고업종코드")) or infer_industry_code(row)
    row["공고업종코드"] = code
    if not row.get("공고업종명"):
        row["공고업종명"] = infer_industry_name(code)
    scope = decide_scope(row)
    local_region = decide_local_region(row)
    receivers = decide_receivers(row)
    row["대표지역"] = "전국" if scope == "전국" else local_region
    row["수신번호"] = ",".join(receivers) if receivers else ""
    row["알림대상"] = "Y" if receivers else "N"
    row["_force_norecv"] = "" if receivers else "1"
    return row


def filter_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        row = normalize_kwater_row(row)
        row = apply_final_rule(row)
        if not norm_text(row.get("공고번호")):
            continue
        code = norm_text(row.get("공고업종코드"))
        if code not in TARGET_INDS:
            continue
        amount = amount_to_int(row.get("추정가격")) or amount_to_int(row.get("발주금액")) or amount_to_int(row.get("기초금액"))
        if amount and amount < MIN_BUDGET:
            continue
        # 금액이 전혀 없으면 K-water 상세에서 추출 실패 가능성이 있으므로 버리지 않고 남긴다.
        out.append(row)
    return dedupe_by_bid_no(out)


def dedupe_by_bid_no(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        key = make_bid_key(row)
        if not key:
            key = norm_text(row.get("공고명"))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def drop_history_and_report_dups(paths: Paths, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    history = load_history(paths)
    report = load_existing_report_keys(paths)
    before = len(rows)
    out = []
    skipped_history = 0
    skipped_report = 0
    for row in rows:
        key = make_bid_key(row)
        if key in history:
            skipped_history += 1
            continue
        if key in report:
            skipped_report += 1
            continue
        out.append(row)
    log(f"[FILTER] history/report 중복 제외: {before} -> {len(out)} (history={skipped_history}, report={skipped_report})")
    return out


def prepare_df(rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    out_rows = []
    for row in rows:
        r = dict(row)
        for k in ["기초금액", "추정가격", "발주금액"]:
            r[k] = fmt_amount(r.get(k))
        for k in ["시작일시", "입찰마감일시", "게시일"]:
            r[k] = fmt_dt(r.get(k))
        r["원문요약"] = norm_text(r.get("원문요약"))[:1000]
        out_rows.append(r)
    df = pd.DataFrame(out_rows)
    for c in OUT_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    ordered = OUT_COLUMNS + [c for c in df.columns if c not in OUT_COLUMNS and not c.startswith("_")]
    return df[ordered]


def save_raw_excel(paths: Paths, rows: Sequence[Dict[str, Any]], timestamp: str) -> Optional[Path]:
    if not rows:
        return None
    out = paths.raw / f"수자원공사_입찰공고_{timestamp}.xlsx"
    prepare_df(rows).to_excel(out, index=False)
    log(f"[SAVE] raw {out} rows={len(rows)}")
    return out


def save_split_excels(paths: Paths, rows: Sequence[Dict[str, Any]], timestamp: str) -> List[Path]:
    if not rows:
        return []
    df = prepare_df(rows)
    outs = []
    for region, g in df.groupby(df["대표지역"].fillna("").replace("", "미분류")):
        out = paths.split / f"수자원공사_입찰공고_{timestamp}_{safe_filename(region)}.xlsx"
        g.to_excel(out, index=False)
        outs.append(out)
        log(f"[SAVE] split {out} rows={len(g)}")
    return outs


def html_report(df: pd.DataFrame, title: str) -> str:
    table = df.to_html(index=False, escape=True)
    created = _now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: Malgun Gothic, Arial, sans-serif; margin: 24px; }}
h1 {{ font-size: 20px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th,td {{ border: 1px solid #ddd; padding: 6px; vertical-align: top; }}
th {{ background: #f3f3f3; position: sticky; top: 0; }}
.meta {{ color: #555; margin-bottom: 12px; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="meta">created: {created} / rows: {len(df)}</div>
{table}
</body></html>"""


def save_report_files(paths: Paths, rows: Sequence[Dict[str, Any]], timestamp: str) -> List[Path]:
    if not rows:
        return []
    df = prepare_df(rows)
    xlsx = paths.report / f"입찰리포트_수자원공사_{timestamp}.xlsx"
    html_file = paths.report / f"입찰리포트_수자원공사_{timestamp}.html"
    df.to_excel(xlsx, index=False)
    html_file.write_text(html_report(df, f"수자원공사 입찰리포트 {timestamp}"), encoding="utf-8")
    update_report_index(paths)
    log(f"[REPORT] xlsx {xlsx}")
    log(f"[REPORT] html {html_file}")
    return [xlsx, html_file]


def update_report_index(paths: Paths) -> None:
    files = sorted(paths.report.glob("입찰리포트_수자원공사_*.html"), key=lambda p: p.name, reverse=True)
    lines = ["<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>수자원공사 리포트</title></head><body>"]
    lines.append("<h1>수자원공사 입찰리포트 Index</h1><ul>")
    for f in files:
        lines.append(f"<li><a href='{html.escape(f.name)}'>{html.escape(f.name)}</a></li>")
    lines.append("</ul></body></html>")
    (paths.report / "입찰리포트_index.html").write_text("\n".join(lines), encoding="utf-8")


def rotate_old_files(paths: Paths) -> None:
    today = _now().date()
    backup_threshold = today - timedelta(days=1)
    delete_threshold = today - timedelta(days=15)
    for base in [paths.raw, paths.split, paths.report, paths.raw_download]:
        backup = base / "backup"
        backup.mkdir(exist_ok=True)
        for f in list(base.glob("*")):
            if not f.is_file() or f.parent == backup:
                continue
            try:
                if datetime.fromtimestamp(f.stat().st_mtime).date() <= backup_threshold:
                    dst = backup / f.name
                    if dst.exists():
                        dst = backup / f"{f.stem}_{int(time.time())}{f.suffix}"
                    shutil.move(str(f), str(dst))
                    log(f"[ROTATE] backup 이동: {f} -> {dst}")
            except Exception as e:
                log(f"[ROTATE][WARN] backup 실패: {f} / {e}")
        for f in list(backup.glob("*")):
            if not f.is_file():
                continue
            try:
                if datetime.fromtimestamp(f.stat().st_mtime).date() <= delete_threshold:
                    f.unlink()
                    log(f"[ROTATE] old 삭제: {f}")
            except Exception as e:
                log(f"[ROTATE][WARN] delete 실패: {f} / {e}")


def write_json_debug(paths: Paths, rows: Sequence[Dict[str, Any]], name: str) -> None:
    try:
        out = paths.debug / f"{name}_{ymdhm(_now())}.json"
        out.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        log(f"[DEBUG] {out}")
    except Exception:
        pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="K-water 전자조달 입찰공고 자동 수집")
    ap.add_argument("--base", default=str(default_base()), help="저장 루트. 기본: Z:\\VOL1\\bid\\bid\\bid-water 또는 REDACTED_PRIVATE_VALUE")
    ap.add_argument("--hours", type=int, default=None, help="last_run 무시하고 최근 N시간 조회")
    ap.add_argument("--force-from", default="", help="강제 시작 YYYYMMDDHHMM")
    ap.add_argument("--force-to", default="", help="강제 종료 YYYYMMDDHHMM")
    ap.add_argument("--headed", action="store_true", help="브라우저 화면 표시(디버깅용)")
    ap.add_argument("--max-details", type=int, default=DEFAULT_MAX_DETAILS, help="상세화면 보강 최대 건수")
    ap.add_argument("--no-send", action="store_true", help="알림톡을 발송하지 않는 안전 점검")
    ap.add_argument("--no-attachments", action="store_true", help="첨부파일 저장 생략")
    ap.add_argument("--no-history-write", action="store_true", help="history.csv 기록 생략")
    ap.add_argument("--no-state-write", action="store_true", help="last_run 저장 생략")
    ap.add_argument("--no-rotate", action="store_true", help="오래된 파일 backup 이동/삭제 생략")
    return ap.parse_args(argv)



# __KWATER_ALIMTALK_ATTACHMENTS_V1_BEGIN__
def _kw_phone_list(value: Any) -> List[str]:
    out = []
    for part in re.split(r"[,;\s]+", norm_text(value)):
        phone = re.sub(r"\D", "", part)
        if phone and phone not in out:
            out.append(phone)
    return out


def _kw_sent_db(paths: Paths) -> Path:
    return paths.state / "alimtalk_sent.sqlite3"


def _kw_init_sent_db(paths: Paths) -> None:
    with sqlite3.connect(str(_kw_sent_db(paths))) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS sent (
            send_key TEXT NOT NULL, phone TEXT NOT NULL, sent_at TEXT NOT NULL,
            PRIMARY KEY(send_key, phone))""")


def _kw_is_sent(paths: Paths, key: str, phone: str) -> bool:
    with sqlite3.connect(str(_kw_sent_db(paths))) as conn:
        return conn.execute("SELECT 1 FROM sent WHERE send_key=? AND phone=?", (key, phone)).fetchone() is not None


def _kw_mark_sent(paths: Paths, key: str, phone: str) -> None:
    with sqlite3.connect(str(_kw_sent_db(paths))) as conn:
        conn.execute("INSERT OR IGNORE INTO sent(send_key,phone,sent_at) VALUES(?,?,?)",
                     (key, phone, _now().isoformat(timespec="seconds")))


def _kw_send_one(paths: Paths, row: Dict[str, Any], phone: str, no_send: bool) -> bool:
    key = make_bid_key(row)
    if _kw_sent_db(paths).exists() and _kw_is_sent(paths, key, phone):
        log("[SEND][SKIP_ALREADY] %s -> %s" % (key, phone))
        return True
    if no_send:
        log("[SAFE] DRY RUN TB0485: key=%s -> %s / %s" % (key, phone, norm_text(row.get("공고명"))))
        return True
    sys.path.insert(0, "/home/pi/n_data")
    try:
        from notifier import send_tb0485
    finally:
        try: sys.path.remove("/home/pi/n_data")
        except ValueError: pass
    item = {
        "bidNtceNm": norm_text(row.get("공고명")) or "-",
        "bidClseDt": fmt_dt(row.get("입찰마감일시")) or "-",
        "jntcontrctDutyRgnNm1": norm_text(row.get("공동도급지역") or row.get("대표지역")) or "없음",
        "rgnDutyJntcontrctRt": norm_text(row.get("공동도급비율")) or "없음",
        "presmptPrce": amount_to_int(row.get("추정가격")) or amount_to_int(row.get("발주금액")) or amount_to_int(row.get("기초금액")),
        "bidNtceNo": norm_text(row.get("공고번호")),
        "bidNtceOrd": norm_text(row.get("차수")) or "000",
    }
    try:
        ok = bool(send_tb0485(item, [phone]))
    except Exception as e:
        log("[SEND][ERROR] %s -> %s / %s" % (key, phone, e))
        return False
    if ok:
        _kw_mark_sent(paths, key, phone)
        log("[SEND][OK] %s -> %s" % (key, phone))
    else:
        log("[SEND][FAIL] %s -> %s" % (key, phone))
    return ok


def _kw_attachment_candidate(el: Any) -> bool:
    try:
        text = norm_text(el.text)
        href = norm_text(el.get_attribute("href"))
        onclick = norm_text(el.get_attribute("onclick"))
        title = norm_text(el.get_attribute("title"))
        blob = " ".join((text, href, onclick, title)).lower()
        if not blob or len(text) > 240:
            return False
        return bool(re.search(r"첨부|다운로드|download|filedown|atch|\.hwp|\.hwpx|\.pdf|\.xls|\.xlsx|\.zip", blob, re.I))
    except Exception:
        return False


def _kw_wait_download(folder: Path, before: set, timeout: float = 20.0) -> Optional[Path]:
    until = time.time() + timeout
    last = None
    stable = 0
    while time.time() < until:
        current = {p.name for p in folder.iterdir() if p.is_file() and not p.name.endswith((".crdownload", ".tmp"))}
        added = current - before
        if added:
            p = max((folder / x for x in added), key=lambda x: x.stat().st_mtime)
            size = p.stat().st_size
            if size > 0 and last == (p.name, size):
                stable += 1
                if stable >= 2: return p
            else:
                last, stable = (p.name, size), 0
        time.sleep(0.5)
    return None


def _kw_collect_elements_in_frames(driver: Any) -> List[Any]:
    from selenium.webdriver.common.by import By
    found = []
    def walk(depth: int = 0) -> None:
        if depth > 4: return
        for el in driver.find_elements(By.CSS_SELECTOR, "a,button,input[type=button],[onclick],[role=button]"):
            if _kw_attachment_candidate(el): found.append(el)
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
        for frame in frames:
            try:
                driver.switch_to.frame(frame); walk(depth + 1); driver.switch_to.parent_frame()
            except Exception:
                try: driver.switch_to.default_content()
                except Exception: pass
    walk()
    return found


def _kw_download_attachments(paths: Paths, rows: Sequence[Dict[str, Any]], headless: bool) -> None:
    targets = [r for r in rows if norm_text(r.get("알림대상")) == "Y" and _kw_phone_list(r.get("수신번호"))]
    if not targets: return
    driver = build_selenium_driver(paths, headless=headless)
    try:
        for row in targets:
            key = make_bid_key(row)
            posted = parse_any_datetime(row.get("게시일")) or _now()
            folder = paths.base / "attachments" / posted.strftime("%Y년") / posted.strftime("%m월") / posted.strftime("%d일") / safe_filename(key)
            folder.mkdir(parents=True, exist_ok=True)
            row["첨부파일폴더"] = str(folder)
            try:
                driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(folder.resolve())})
                driver.get(norm_text(row.get("상세링크")) or KWATER_DETAIL_URL.format(bid_no=row.get("공고번호")))
                time.sleep(2.0)
                elements = _kw_collect_elements_in_frames(driver)
                log("[ATTACH][FOUND] %s candidates=%d" % (key, len(elements)))
                clicked = set()
                for el in elements:
                    try:
                        sig = (norm_text(el.text), norm_text(el.get_attribute("href")), norm_text(el.get_attribute("onclick")))
                        if sig in clicked: continue
                        clicked.add(sig)
                        before = {p.name for p in folder.iterdir() if p.is_file()}
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", el)
                        p = _kw_wait_download(folder, before)
                        if p: log("[ATTACH][OK] %s %s bytes=%d" % (key, p.name, p.stat().st_size))
                        else: log("[ATTACH][WARN] %s download not detected: %s" % (key, sig[0][:100]))
                    except Exception as e:
                        log("[ATTACH][WARN] %s click failed: %s" % (key, e))
                files = sorted(p for p in folder.iterdir() if p.is_file() and p.stat().st_size > 0)
                row["첨부파일수"] = len(files)
                row["첨부파일목록"] = "\n".join(p.name for p in files)
                row["첨부저장상태"] = "정상" if files else ("첨부없음" if not elements else "저장실패")
            except Exception as e:
                row["첨부파일수"] = 0
                row["첨부저장상태"] = "오류: %s" % e
                log("[ATTACH][ERROR] %s %s" % (key, e))
    finally:
        try: driver.quit()
        except Exception: pass


def _kw_process_targets(paths: Paths, rows: Sequence[Dict[str, Any]], no_send: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    completed, retry = [], []
    if not no_send:
        _kw_init_sent_db(paths)
    for row in rows:
        phones = _kw_phone_list(row.get("수신번호")) if norm_text(row.get("알림대상")) == "Y" else []
        if not phones:
            row["알림톡상태"] = "비대상"
            completed.append(row)
            continue
        results = [_kw_send_one(paths, row, phone, no_send) for phone in phones]
        if no_send:
            row["알림톡상태"] = "DRY_RUN"
            completed.append(row)
        elif all(results):
            row["알림톡상태"] = "발송완료"
            completed.append(row)
        else:
            row["알림톡상태"] = "일부실패 또는 실패"
            retry.append(row)
    return completed, retry
# __KWATER_ALIMTALK_ATTACHMENTS_V1_END__

def main(argv: Optional[Sequence[str]] = None) -> int:
    global PATHS
    args = parse_args(argv)
    PATHS = build_paths(Path(args.base))
    log("[MAIN] === bid-water START ===")
    log(f"[CONF] BASE={PATHS.base}")
    log(f"[CONF] KWATER_URL={KWATER_URL}")
    log(f"[CONF] TARGET_INDS={sorted(TARGET_INDS)} MIN_BUDGET={MIN_BUDGET} NATION_THRESHOLD={NATION_THRESHOLD}")

    try:
        with SingleInstanceLock(PATHS.lock_file):
            if not args.no_rotate:
                rotate_old_files(PATHS)

            start, end = compute_window(args, PATHS)
            ts = ymdhm(_now())
            log(f"[MAIN] 조회기간 {ymdhm(start)} ~ {ymdhm(end)}")

            raw_rows = collect_kwater_rows(start, end, PATHS, headless=not args.headed, max_details=args.max_details)
            log(f"[FETCH] raw rows={len(raw_rows)}")
            write_json_debug(PATHS, raw_rows, "raw_rows")

            filtered = filter_rows(raw_rows)
            log(f"[FILTER] 업종/금액/수신 규칙 후 rows={len(filtered)}")
            write_json_debug(PATHS, filtered, "filtered_rows")

            final_rows = drop_history_and_report_dups(PATHS, filtered)
            if not final_rows:
                log("[MAIN] 신규 저장 대상 없음")
                if not args.no_send and not args.no_state_write:
                    save_last_run(PATHS, end)
                log("[MAIN] === bid-water END success=True ===")
                return 0

            # 알림대상 공고만 첨부파일을 저장한다. DRY RUN에서도 검증을 위해 저장한다.
            if not args.no_attachments:
                _kw_download_attachments(PATHS, final_rows, headless=not args.headed)

            completed_rows, retry_rows = _kw_process_targets(PATHS, final_rows, no_send=args.no_send)
            save_raw_excel(PATHS, final_rows, ts)
            save_split_excels(PATHS, final_rows, ts)
            if not args.no_send:
                save_report_files(PATHS, completed_rows, ts)
            if retry_rows:
                write_json_debug(PATHS, retry_rows, "alimtalk_retry_rows")
                log("[SEND][RETRY_PENDING] rows=%d (history/report에 기록하지 않음)" % len(retry_rows))
            # no-send 검증은 운영 이력과 last_run을 절대 변경하지 않는다.
            if not args.no_send and not args.no_history_write:
                append_history(PATHS, completed_rows)
            if not args.no_send and not args.no_state_write:
                save_last_run(PATHS, end)
            log("[MAIN] === bid-water END success=True ===")
            return 0
    except Exception as e:
        log(f"[FATAL] {e}")
        log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
