
# -*- coding: utf-8 -*-



import os, sys, subprocess, shutil, time

from datetime import datetime

from pathlib import Path



ACTUAL_CRAWLER = "/home/pi/seri_Alarm_Server6/main_crawling.py"

BASE_DIR = Path(os.getenv("BASE_DIR", "/mnt/vol1REDACTED_PRIVATE_VALUE"))

EXPORTS_DIR = Path("REDACTED_PRIVATE_VALUE")

NOTIFIER = "/home/pi/seri_Alarm_Server6/land_notify.py"



def shlex_quote(s):

    return "'" + s.replace("'", "'\"'\"'") + "'"



def move_new_csvs_to_base_dir(since_epoch: float):

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    if EXPORTS_DIR.is_dir():

        for p in sorted(EXPORTS_DIR.glob("*.csv")):

            try:

                if p.stat().st_mtime >= since_epoch:

                    dst = BASE_DIR / p.name

                    shutil.copy2(str(p), str(dst))

            except Exception as e:

                with open(BASE_DIR / "runner_move_errors.log", "a", encoding="utf-8") as logf:

                    logf.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} move fail {p}: {e}\n")



def main():

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    log = BASE_DIR / f"land_crawl_{stamp}.log"



    env = os.environ.copy()

    env["PYTHONIOENCODING"] = "UTF-8"

    env["LANG"] = "ko_KR.UTF-8"

    env["LC_ALL"] = "ko_KR.UTF-8"

    env["BASE_DIR"] = str(BASE_DIR)



    # ✅ main_crawling 내부 발송 차단(가능한 스위치들 모두 강제)

    env["ALLOW_PROD_SEND"] = "0"

    env["TEST_MODE"] = "1"

    env["ALLIGO_FORCE_PHONE"] = ""  # 강제수신자 비움



    start_ts = time.time()

    with open(log, "w", encoding="utf-8") as fh:

        fh.write(f"Start: {stamp}\n")

        fh.flush()



        proc = subprocess.run(

            [sys.executable, ACTUAL_CRAWLER],

            stdout=fh, stderr=fh, env=env, cwd=str(Path(ACTUAL_CRAWLER).parent)

        )

        fh.write(f"\nExit code: {proc.returncode}\n")

        fh.flush()



    # 크롤러가 exports/에 쓴 CSV를 공유폴더로 복사

    move_new_csvs_to_base_dir(start_ts)



    # ✅ 룰 기반 알림톡 발송(중복은 sent_history.jsonl로 완전 차단)

    try:

        # /home/pi/n_data 모듈 재사용을 위해 PYTHONPATH 추가

        env2 = os.environ.copy()

        env2["PYTHONPATH"] = "/home/pi/n_data:" + env2.get("PYTHONPATH","")

        env2["BASE_DIR"] = str(BASE_DIR)



        with open(log, "a", encoding="utf-8") as fh:

            fh.write("\n--- RUN land_notify.py ---\n")

            fh.flush()

            p2 = subprocess.run([sys.executable, NOTIFIER], stdout=fh, stderr=fh, env=env2, cwd=str(Path(NOTIFIER).parent))

            fh.write(f"land_notify exit={p2.returncode}\n")

    except Exception as e:

        with open(log, "a", encoding="utf-8") as fh:

            fh.write(f"[ERROR] notifier failed: {e}\n")



    # 비정상 종료면 서비스에서 실패 감지 가능

    if proc.returncode != 0:

        raise SystemExit(proc.returncode)



if __name__ == "__main__":

    main()

