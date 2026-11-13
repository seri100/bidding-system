"""Public G2B detail-page enrichment; never sends messages or reads API keys.

Runtime: installed Selenium + matching system Chromium/ChromeDriver.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def clean(value):
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in ("none", "null", "nan", "n/a") else text


def identity(row):
    return clean(row.get("공고번호")), clean(row.get("차수") or "000").zfill(3)


def needs_lookup(row):
    raw = row.get("원문") or {}
    if not isinstance(raw, dict):
        raw = {}
    if any(clean(row.get(k)) for k in ("공동도급지역", "공동도급지역_추가")):
        return False
    if any(clean(raw.get("jntcontrctDutyRgnNm%d" % i)) for i in (1, 2, 3)):
        return False
    try:
        positive = float(clean(row.get("공동도급비율") or raw.get("rgnDutyJntcontrctRt")).rstrip("%")) > 0
    except ValueError:
        positive = False
    return positive or clean(raw.get("rgnDutyJntcontrctYn")).upper() == "Y"


def parse_detail(expected_no, expected_ord, shown_no, duty, region, ratio):
    """Only consume the exact labeled detail cells, never site/agency text."""
    match = re.fullmatch(r"\s*(R\d{2}BK\d+)\s*-\s*(\d{3})\s*", shown_no)
    if not match or match.groups() != (expected_no, expected_ord):
        raise ValueError("공고번호·차수 불일치")
    duty = clean(duty)
    if duty not in ("해당", "해당없음", "비해당"):
        raise ValueError("지역의무공동도급 상태 확인 불가")
    ratio = clean(ratio).replace("%", "").strip()
    if ratio and not re.fullmatch(r"\d+(?:\.\d+)?", ratio):
        raise ValueError("비율 형식 오류")
    if ratio and not 0 <= float(ratio) <= 100:
        raise ValueError("비율 범위 오류")
    regions = re.findall(r"\[\s*([^\[\]]+)\s*\]", region)
    # A plain region name is accepted only from the exact 공동도급지역 cell.
    if not regions and clean(region) not in ("", "없음", "해당없음", "-"):
        regions = re.split(r"\s*[|,/]\s*", clean(region))
    regions = list(dict.fromkeys(clean(x) for x in regions if clean(x)))
    if any(len(x) > 80 or x in ("전국", "없음", "해당없음") for x in regions):
        raise ValueError("공동도급지역 값 확인 필요")
    if duty == "해당" and (not regions or not ratio or float(ratio) <= 0):
        raise ValueError("의무공동도급 상세값 누락")
    if duty != "해당" and (regions or (ratio and float(ratio) > 0)):
        raise ValueError("의무 여부와 지역·비율 충돌")
    return {"regions": regions, "ratio": ratio, "duty": duty,
            "bid_no": expected_no, "bid_ord": expected_ord,
            "source": "나라장터 상세화면 공동도급지역", "checked_at": time.time()}



STAGES = frozenset(('browser_start', 'home', 'search_tab', 'search_mode', 'search_input',
                    'search_submit', 'search_results', 'detail_open', 'detail_read',
                    'detail_validate', 'worker_start', 'unknown'))


def lookup_phase(driver, name):
    if driver is not None:
        driver._g2b_phase = name
    print('[G2B][PHASE] ' + name, file=sys.stderr, flush=True)


def last_worker_stage(diagnostics):
    phases = re.findall(r'\[G2B\]\[PHASE\] ([a-z_]+)', diagnostics or '')
    return next((name for name in reversed(phases) if name in STAGES), 'worker_start')


def fetch_detail(driver, bid_no, bid_ord):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait

    def visible(elements):
        return next((e for e in elements if driver.execute_script(
            "var r=arguments[0].getBoundingClientRect(); return r.width>0 && r.height>0 && !arguments[0].disabled;", e)), False)

    lookup_phase(driver, "home")
    driver.get("https://www.g2b.go.kr/")
    wait = WebDriverWait(driver, 60)
    lookup_phase(driver, "search_tab")
    tab = wait.until(lambda d: visible(d.find_elements(
        By.CSS_SELECTOR, "[aria-label='Go to slide 2']")))
    print("[G2B] search tab", file=sys.stderr, flush=True)
    driver.execute_script("Array.from(document.querySelectorAll(\"input[id$='_popupCnts_btnClose']\")).reverse().forEach(e=>{if(e.getBoundingClientRect().width) e.click();});")
    tab.send_keys(Keys.ENTER)
    lookup_phase(driver, "search_mode")
    mode = wait.until(lambda d: d.find_elements(
        By.CSS_SELECTOR, "input[type='radio'][title='통합상세']"))[0]
    driver.execute_script("arguments[0].click();", mode)
    lookup_phase(driver, "search_input")
    field = wait.until(lambda d: visible(d.find_elements(
        By.CSS_SELECTOR, "input[id$='_totBizNo']")))
    print("[G2B] field ready", file=sys.stderr, flush=True)
    field.clear()
    field.send_keys(bid_no)
    search = wait.until(lambda d: visible(d.find_elements(
        By.CSS_SELECTOR, "a[id$='_btnUntyDtlSrch']")))
    lookup_phase(driver, "search_submit")
    search.send_keys(Keys.ENTER)
    lookup_phase(driver, "search_results")
    cell = wait.until(lambda d: visible(d.find_elements(
        By.XPATH, "//td[normalize-space(.)='%s']" % bid_no)))
    title = cell.find_element(By.XPATH, "..").find_element(
        By.CSS_SELECTOR, "td[id$='_untyTitleTd'] label[id$='_bizNm']")
    lookup_phase(driver, "detail_open")
    # Notice popups can finish loading after the initial search-tab transition.
    driver.execute_script("Array.from(document.querySelectorAll(\"input[id$='_popupCnts_btnClose']\")).reverse().forEach(e=>e.click());")
    driver.execute_script("arguments[0].click();", title)

    def read_detail(d):
        data = d.execute_script("""
          var out={};
          for(var label of ['입찰공고번호','지역의무공동도급','공동도급지역','공동도급비율']) {
            var hs=Array.from(document.querySelectorAll('th')).filter(e=>e.textContent.trim()===label && e.getBoundingClientRect().width>0);
            if(hs.length!==1) return null;
            var cell=hs[0].nextElementSibling;
            if(!cell || cell.tagName!=='TD') return null;
            var inp=cell.querySelector('input');
            out[label]=inp ? inp.value : cell.innerText;
          }
          return out;
        """)
        if not data or "".join(data['입찰공고번호'].split()) != bid_no + '-' + bid_ord:
            return False
        return data

    lookup_phase(driver, "detail_read")
    data = wait.until(read_detail)
    lookup_phase(driver, "detail_validate")
    return parse_detail(bid_no, bid_ord, data['입찰공고번호'],
                        data['지역의무공동도급'], data['공동도급지역'], data['공동도급비율'])



def worker(jobs, emit=False):
    lookup_phase(None, "browser_start")
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    executable = os.environ.get("G2B_CHROMIUM") or shutil.which("chromium-browser") or shutil.which("chromium")
    chromedriver = os.environ.get("G2B_CHROMEDRIVER") or shutil.which("chromedriver")
    if not executable or not chromedriver:
        raise RuntimeError("Chromium/ChromeDriver 경로 확인 필요")
    options = webdriver.ChromeOptions()
    options.binary_location = executable
    options.page_load_strategy = "normal"
    if os.environ.get("G2B_HEADED") != "1":
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    result = {}
    try:
        driver = webdriver.Chrome(service=Service(chromedriver), options=options)
    except Exception as exc:
        for bid_no, bid_ord in jobs:
            key = bid_no + '-' + bid_ord
            result[key] = {'ok': False, 'error': type(exc).__name__, 'stage': 'browser_start'}
            if emit:
                print(json.dumps({key: result[key]}, ensure_ascii=False), flush=True)
        return result
    print("[G2B] browser ready", file=sys.stderr, flush=True)
    driver.command_executor.set_timeout(65)
    driver.set_page_load_timeout(60)
    try:
        for bid_no, bid_ord in jobs:
            key = bid_no + "-" + bid_ord
            try:
                result[key] = {"ok": True, "data": fetch_detail(driver, bid_no, bid_ord)}
            except Exception as exc:
                stage = getattr(driver, '_g2b_phase', 'unknown')
                print('[G2B][ERROR] stage=%s error=%s' % (stage, type(exc).__name__), file=sys.stderr, flush=True)
                result[key] = {"ok": False, "error": type(exc).__name__, "stage": stage}
            if emit:
                print(json.dumps({key: result[key]}, ensure_ascii=False), flush=True)
    finally:
        driver.quit()
    return result


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".joint-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def fingerprint(row):
    raw = row.get("원문") or {}
    fields = {k: raw.get(k) for k in ("bidNtceDt", "chgDt", "bidNtceNm", "bidNtceOrd",
                                       "rgnDutyJntcontrctYn", "rgnDutyJntcontrctRt")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def enrich_rows(rows, state_dir, normalize, log, cancelled=lambda row: False):
    """Bounded isolated worker; persistent retry queue spans API time windows.

    Unresolved rows are deferred so blank messages cannot consume send dedup keys.
    Successfully resolved rows resume the existing notification flow.
    """
    path = Path(state_dir) / "g2b_joint_region_v1.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(state, dict):
            raise ValueError("invalid state")
    except Exception as exc:
        log("[JOINT_WEB][STATE_ERR] " + type(exc).__name__)
        state = {}
    cache = state.get("cache", {})
    pending = state.get("pending", {})
    if not isinstance(cache, dict) or not isinstance(pending, dict):
        log("[JOINT_WEB][STATE_ERR] invalid cache/pending")
        cache, pending = {}, {}
    now = time.time()
    current = {"-".join(identity(row)): row for row in rows}
    # Current cancellation/changed data always supersedes a pending snapshot.
    for key, entry in list(pending.items()):
        if key in current:
            pending[key]["row"] = current[key]
        elif now - entry.get("created", 0) < 7 * 86400:
            row = entry.get("row", {})
            # Do not replay snapshots after the original bidding deadline.
            deadline = clean(row.get("입찰마감일시")).replace("/", "-")
            from datetime import datetime
            try:
                live = datetime.fromisoformat(deadline) > datetime.now()
            except ValueError:
                live = False
            if live:
                current[key] = row
            else:
                pending.pop(key, None)
        else:
            pending.pop(key, None)
    candidates = {}
    for key, row in current.items():
        if not needs_lookup(row) or cancelled(row):
            pending.pop(key, None)
            continue
        entry = cache.get(key, {})
        if entry.get("fingerprint") == fingerprint(row) and now - entry.get("at", 0) < 21600:
            candidates[key] = entry["data"]
        else:
            previous = pending.get(key, {})
            pending[key] = {"row": row, "created": previous.get("created", now),
                            "attempts": previous.get("attempts", 0),
                            "last_try": previous.get("last_try", 0),
                            "last_error": previous.get("last_error", ""),
                            "last_stage": previous.get("last_stage", "")}
    # Oldest attempts first; at most one per cycle, and 240 seconds total.
    jobs = sorted((key for key in pending if key in current and key not in candidates),
                  key=lambda k: pending[k].get("last_try", 0))[:1]
    if jobs:
        log("[JOINT_WEB][LOOKUP] rows=%d" % len(jobs))
        diagnostics = ''
        worker_error = 'worker_unavailable'
        try:
            interpreter = sys.executable
            process = subprocess.Popen([interpreter, str(Path(__file__).resolve()), "--worker"],
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     universal_newlines=True, start_new_session=True)
            try:
                output, diagnostics = process.communicate(json.dumps([identity(current[k]) for k in jobs]), timeout=240)
            except subprocess.TimeoutExpired:
                # Kill the isolated browser process group as well as its Python parent.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                output, diagnostics = process.communicate()
                worker_error = 'TimeoutExpired'
                log('[JOINT_WEB][TIMEOUT] worker budget=240s stage=' + last_worker_stage(diagnostics))
            results = {}
            for line in output.splitlines():
                results.update(json.loads(line))
            if process.returncode and not results:
                raise RuntimeError("browser worker failed; run standalone probe")
        except Exception as exc:
            if worker_error != 'TimeoutExpired':
                worker_error = type(exc).__name__
            log('[JOINT_WEB][WORKER_ERR] error=%s stage=%s' % (worker_error, last_worker_stage(diagnostics)))
            results = {}
        for key in jobs:
            pending[key]["attempts"] += 1
            pending[key]["last_try"] = now
            result = results.get(key, {})
            if result.get("ok"):
                data = result["data"]
                if (data.get("bid_no"), data.get("bid_ord")) != identity(current[key]):
                    log("[JOINT_WEB][IDENTITY_ERR] " + key)
                    continue
                candidates[key] = data
                cache[key] = {"data": data, "at": now, "fingerprint": fingerprint(current[key])}
            else:
                error = clean(result.get('error') or worker_error)
                error = error if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', error) else 'UnknownError'
                stage = result.get('stage') or last_worker_stage(diagnostics)
                stage = stage if stage in STAGES else 'unknown'
                pending[key]['last_error'] = error
                pending[key]['last_stage'] = stage
                log('[JOINT_WEB][RETRY] %s attempt=%s error=%s stage=%s' %
                    (key, pending[key]['attempts'], error, stage))
    for key, data in candidates.items():
        row = current[key]
        raw = dict(row.get("원문") or {})
        regions = data["regions"]
        for i in (1, 2, 3):
            raw["jntcontrctDutyRgnNm%d" % i] = (
                regions[i - 1] if i < 3 and len(regions) >= i else
                " | ".join(regions[2:]) if i == 3 else "")
        raw["rgnDutyJntcontrctRt"] = data["ratio"]
        raw["rgnDutyJntcontrctYn"] = "Y" if data["duty"] == "해당" else "N"
        refreshed = normalize(raw)
        row.update(refreshed)
        row["공동도급지역_출처"] = data["source"]
        row["공동도급지역_확인시각"] = data["checked_at"]
        pending.pop(key, None)
        log("[JOINT_WEB][OK] %s regions=%s ratio=%s" % (key, " | ".join(regions), data["ratio"]))
    cache = {k: v for k, v in cache.items() if now - v.get("at", 0) < 7 * 86400}
    try:
        atomic_json(path, {"cache": cache, "pending": pending})
    except Exception as exc:
        log("[JOINT_WEB][SAVE_ERR] " + type(exc).__name__)
    deferred = [k for k in current if k in pending]
    if deferred:
        log("[JOINT_WEB][DEFER] rows=%d pending=%d" % (len(deferred), len(pending)))
    return [row for key, row in current.items() if key not in pending]


if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        worker(json.load(sys.stdin), emit=True)
    elif len(sys.argv) in (2, 3) and re.fullmatch(r"R\d{2}BK\d+", sys.argv[1]):
        # Standalone read-only probe. Does not import main_send or alter state.
        result = worker([(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "000")])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if all(x.get("ok") for x in result.values()) else 1)
    else:
        raise SystemExit("Usage: python3 g2b_joint_region.py R26BK01789188 000")
