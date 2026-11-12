
# app/lh_collector.py

# LH 입찰 수집 전용 래퍼



from pathlib import Path
import os

import pandas as pd

import subprocess

import sys



BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)

LH_CA_BUNDLE = str((BASE_DIR / "certs" / "combined_ca_bundle.pem").resolve())






def run_lh_crawling():

    """

    main_crawling.py 를 실행하고

    생성된 엑셀을 읽어서 dict 리스트로 반환

    """

    print("[LH] start crawling")

    env = os.environ.copy()
    env["REQUESTS_CA_BUNDLE"] = LH_CA_BUNDLE
    env["SSL_CERT_FILE"] = LH_CA_BUNDLE



    # 1) 크롤링 실행

    proc = subprocess.run(

        [sys.executable, str(BASE_DIR / "main_crawling.py")],

        cwd=str(BASE_DIR),
        env=env,

    )



    if proc.returncode != 0:

        print("[LH] crawling failed")

        return []



    # 2) 가장 최근 엑셀 파일 찾기

    files = sorted(DATA_DIR.glob("LH_*.xlsx"), reverse=True)

    if not files:

        print("[LH] no excel output")

        return []



    latest = files[0]

    print(f"[LH] load excel: {latest.name}")



    # 3) 엑셀 → dict

    df = pd.read_excel(latest)

    return df.to_dict(orient="records")

