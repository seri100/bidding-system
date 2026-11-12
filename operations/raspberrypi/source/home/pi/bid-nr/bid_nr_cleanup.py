
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import os

import re

import shutil

from datetime import datetime, timedelta

from pathlib import Path



KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "7"))

DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"



NAS_ROOT = Path("/mnt/vol1/bid/bid-nr")

LOCAL_ROOT = Path("/home/pi/bid-nr")



SOURCES = {

    "raw": NAS_ROOT / "raw",

    "report": NAS_ROOT / "report",

    "logs": LOCAL_ROOT / "logs",

}



BACKUP_ROOT = NAS_ROOT / "backup"

LOG_DIR = LOCAL_ROOT / "logs"



now = datetime.now()

cutoff = now - timedelta(days=KEEP_DAYS)

stamp = now.strftime("%Y%m%d_%H%M%S")

log_file = LOG_DIR / f"bid_nr_cleanup_{stamp}.log"



DATE_PATTERN = re.compile(r"(20\d{6})(?:[_-]?(\d{6}))?")



LOG_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_ROOT.mkdir(parents=True, exist_ok=True)





def log(message):

    print(message)

    with log_file.open("a", encoding="utf-8") as fp:

        fp.write(message + "\n")





def file_datetime(path):

    match = DATE_PATTERN.search(path.name)



    if match:

        date_text = match.group(1)

        time_text = match.group(2) or "000000"



        try:

            return datetime.strptime(date_text + time_text, "%Y%m%d%H%M%S")

        except ValueError:

            pass



    return datetime.fromtimestamp(path.stat().st_mtime)





def is_old(path):

    try:

        return path.is_file() and file_datetime(path) < cutoff

    except (FileNotFoundError, OSError):

        return False





def safe_move(src, dst):

    dst.parent.mkdir(parents=True, exist_ok=True)



    if dst.exists():

        if dst.stat().st_size == src.stat().st_size:

            src.unlink()

            log(f"[OK][EXISTS] 기존 백업 확인 후 원본 정리: {src}")

            return



        dst = dst.with_name(

            f"{dst.stem}_{stamp}{dst.suffix}"

        )



    temp_dst = dst.with_name(dst.name + ".part")



    if temp_dst.exists():

        temp_dst.unlink()



    shutil.copy2(str(src), str(temp_dst))



    if temp_dst.stat().st_size != src.stat().st_size:

        temp_dst.unlink()

        raise RuntimeError(f"백업 크기 검증 실패: {src}")



    temp_dst.replace(dst)

    src.unlink()



    log(f"[OK][MOVE] {src} -> {dst}")





log("=" * 70)

log(f"[BID-NR BACKUP] {now:%F %T}")

log(f"KEEP_DAYS={KEEP_DAYS}")

log(f"CUTOFF={cutoff:%F %T}")

log(f"DRY_RUN={1 if DRY_RUN else 0}")

log(f"BACKUP_ROOT={BACKUP_ROOT}")

log("=" * 70)



targets = []



for category, source_dir in SOURCES.items():

    if not source_dir.exists():

        log(f"[WARN] 원본 폴더 없음: {source_dir}")

        continue



    for path in source_dir.iterdir():

        if is_old(path):

            targets.append((category, path))



targets.sort(key=lambda item: (item[0], item[1].name))



log(f"[INFO] 백업 대상 파일 수: {len(targets)}")



moved = 0

failed = 0



for category, src in targets:

    dst = BACKUP_ROOT / category / src.name



    if DRY_RUN:

        log(f"[DRY-RUN] {src} -> {dst}")

        continue



    try:

        safe_move(src, dst)

        moved += 1

    except Exception as exc:

        failed += 1

        log(f"[ERROR] {src}: {exc}")



if DRY_RUN:

    log("[DRY-RUN] 파일을 실제로 이동하지 않았습니다.")

else:

    log(f"[RESULT] 대상={len(targets)} 이동={moved} 실패={failed}")



    if failed:

        raise SystemExit(1)



log("[END] 백업 작업 종료")

