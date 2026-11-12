# -*- coding: utf-8 -*-
import re, shutil, tempfile, time
from datetime import datetime
from pathlib import Path
from selenium.webdriver.common.by import By
import kepco_srm_collect as collector
import kepco_agreement_enrich as enrich

ATTACH_ROOT = Path("/mnt/vol1/bid/bid_elec/attachments")
EXT_RE = re.compile(r"\.(?:hwp|hwpx|pdf|xls|xlsx|xlsm|zip|doc|docx|ppt|pptx|txt)$", re.I)

def safe_name(value):
    value = re.sub(r'[\\/:*?"<>|]+', '_', str(value or '').strip())
    return value[:180] or 'attachment'

def notice_date(row):
    text = str(row.get("공고일시") or row.get("수집시각") or "")
    m = re.search(r"(20\d{2})[-./]?(\d{2})[-./]?(\d{2})", text)
    if m:
        return m.group(1), m.group(2), m.group(3)
    now = datetime.now()
    return now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")

def wait_new_file(folder, before, timeout=180):
    end = time.time() + timeout; previous = None; stable = 0
    while time.time() < end:
        partial = list(folder.glob("*.crdownload"))
        added = [p for p in folder.iterdir() if p.is_file() and p.name not in before and not p.name.endswith(".crdownload")]
        if added and not partial:
            p = max(added, key=lambda x: x.stat().st_mtime)
            state = (p.name, p.stat().st_size)
            stable = stable + 1 if state == previous else 0
            previous = state
            if stable >= 2 and state[1] > 0: return p
        time.sleep(0.7)
    return None

def file_elements(driver):
    found=[]; seen=set()
    for el in driver.find_elements(By.XPATH, "//*[not(*)]"):
        try:
            text = " ".join((el.text or "").split())
            if not text or not EXT_RE.search(text): continue
            if text in seen: continue
            seen.add(text); found.append((text, el))
        except Exception: pass
    return found

def save_target_attachments(row, log=print):
    bid = str(row.get("공고번호") or "").strip()
    if not bid: return row
    y,m,d = notice_date(row)
    folder = ATTACH_ROOT / (y+"년") / (m+"월") / (d+"일") / safe_name(bid+"-"+str(row.get("차수") or "000"))
    folder.mkdir(parents=True, exist_ok=True)
    driver = collector.make_driver()
    errors=[]
    try:
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior":"allow", "downloadPath":str(folder.resolve())})
        enrich.open_srm(driver); enrich.open_detail(driver, bid)
        items=file_elements(driver)
        log("[ATTACH][FOUND] %s files=%d" % (bid,len(items)))
        for label,el in items:
            expected=folder/safe_name(label)
            if expected.exists() and expected.stat().st_size>0:
                log("[ATTACH][EXISTS] %s %s bytes=%d" % (bid,expected.name,expected.stat().st_size)); continue
            before={p.name for p in folder.iterdir() if p.is_file()}
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",el)
                got=wait_new_file(folder,before)
                if not got: raise RuntimeError("다운로드 파일 미검출")
                dst=folder/safe_name(label)
                if got != dst:
                    if dst.exists(): dst=folder/(dst.stem+"_2"+dst.suffix)
                    shutil.move(str(got),str(dst)); got=dst
                log("[ATTACH][OK] %s %s bytes=%d" % (bid,got.name,got.stat().st_size))
            except Exception as exc:
                errors.append("%s: %s"%(label,exc)); log("[ATTACH][WARN] %s %s / %s"%(bid,label,exc))
    except Exception as exc:
        errors.append(str(exc)); log("[ATTACH][ERROR] %s %s"%(bid,exc))
    finally:
        try: driver.quit()
        except Exception: pass
    files=sorted(p for p in folder.iterdir() if p.is_file() and not p.name.endswith(".crdownload") and p.stat().st_size>0)
    row["첨부파일폴더"]=str(folder); row["첨부파일수"]=len(files)
    row["첨부파일목록"]="\n".join(p.name for p in files)
    row["첨부저장상태"]=(("정상" if files else "첨부없음") if not errors else ("일부실패 %d"%len(errors) if files else "실패"))
    log("[ATTACH][DONE] %s files=%d status=%s"%(bid,len(files),row["첨부저장상태"]))
    return row
