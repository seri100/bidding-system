
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



from pathlib import Path

from datetime import datetime, timedelta

import shutil

import sys



SRC_DIR = Path("/mnt/vol1/bid/gon_auto")

BACKUP_DIR = Path("/mnt/vol1/bid/backup/gon_auto_xlsx")

LOG_DIR = SRC_DIR / "logs"

LOG_FILE = LOG_DIR / "gon_auto_cleanup.log"



BACKUP_AFTER_DAYS = 2

DELETE_AFTER_DAYS = 15



PATTERN = "입찰공고_지역분류_*.xlsx"





def log(msg):

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    line = f"[{now}] {msg}"

    print(line)

    with LOG_FILE.open("a", encoding="utf-8") as f:

        f.write(line + "\n")





def main():

    now = datetime.now()



    if not SRC_DIR.exists():

        log(f"[ERR] SRC_DIR 없음: {SRC_DIR}")

        return 1



    BACKUP_DIR.mkdir(parents=True, exist_ok=True)



    backup_cutoff = now - timedelta(days=BACKUP_AFTER_DAYS)

    delete_cutoff = now - timedelta(days=DELETE_AFTER_DAYS)



    backed = 0

    skipped = 0

    deleted = 0



    files = sorted(SRC_DIR.glob(PATTERN))



    log("==== gon_auto_cleanup.py START ====")

    log(f"SRC_DIR={SRC_DIR}")

    log(f"BACKUP_DIR={BACKUP_DIR}")

    log(f"대상 파일 수={len(files)}")

    log(f"백업 기준: {BACKUP_AFTER_DAYS}일 경과")

    log(f"삭제 기준: {DELETE_AFTER_DAYS}일 경과")



    for src in files:

        try:

            mtime = datetime.fromtimestamp(src.stat().st_mtime)

            dst = BACKUP_DIR / src.name



            # 2일 지난 파일 백업

            if mtime <= backup_cutoff:

                if not dst.exists():

                    shutil.copy2(src, dst)

                    backed += 1

                    log(f"[BACKUP] {src.name} -> {dst}")

                else:

                    skipped += 1



            # 15일 지난 파일 원본 삭제

            if mtime <= delete_cutoff:

                # 삭제 전 백업이 없으면 먼저 백업

                if not dst.exists():

                    shutil.copy2(src, dst)

                    backed += 1

                    log(f"[BACKUP_BEFORE_DELETE] {src.name} -> {dst}")



                src.unlink()

                deleted += 1

                log(f"[DELETE] {src}")



        except Exception as e:

            log(f"[ERR] {src}: {e}")



    log(f"[SUMMARY] backed={backed}, skipped_existing_backup={skipped}, deleted={deleted}")

    log("==== gon_auto_cleanup.py END ====")

    return 0





if __name__ == "__main__":

    sys.exit(main())

