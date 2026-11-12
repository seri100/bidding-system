
# -*- coding: utf-8 -*-

"""

물품 CSV에서 GHP, EHP 포함 공고를 별도 폴더로 분리 저장

실행: python3 /home/pi/gongo/filter_ghp_ehp.py

"""



import os

import pandas as pd

from datetime import datetime

import sys

sys.path.insert(0, '/home/pi/gongo')

import config



TODAY = datetime.now().strftime("%Y%m%d")

LOCAL_DIR  = config.LOCAL_RESULT_DIR        # /home/pi/gongo

NETWORK_DIR = config.NETWORK_RESULT_DIR     # /mnt/vol1/bid/result



# 입력 파일

LOCAL_SRC  = os.path.join(LOCAL_DIR,  f"물품_{TODAY}.csv")

NET_SRC    = os.path.join(NETWORK_DIR, f"물품_{TODAY}.csv")



# 출력 폴더

LOCAL_OUT  = os.path.join(LOCAL_DIR,  "ghp_ehp")

NET_OUT    = os.path.join(NETWORK_DIR, "ghp_ehp")



# 출력 파일

LOCAL_DEST = os.path.join(LOCAL_OUT,  f"물품_GHP_EHP_{TODAY}.csv")

NET_DEST   = os.path.join(NET_OUT,    f"물품_GHP_EHP_{TODAY}.csv")



def filter_and_save(src, dest, label):

    if not os.path.exists(src):

        print(f"[{label}] 파일 없음: {src}")

        return 0



    df = pd.read_csv(src, dtype=str, encoding="REDACTED_PRIVATE_VALUE")



    # 입찰공고명 컬럼에서 GHP 또는 EHP 포함 행 필터링

    mask = df["입찰공고명"].str.contains("GHP|EHP", case=False, na=False)

    filtered = df[mask].copy()



    if filtered.empty:

        print(f"[{label}] GHP/EHP 해당 공고 없음")

        return 0



    os.makedirs(os.path.dirname(dest), exist_ok=True)

    filtered.to_csv(dest, index=False, encoding="REDACTED_PRIVATE_VALUE")

    print(f"[{label}] ✅ {len(filtered)}건 저장 → {dest}")

    return len(filtered)



if __name__ == "__main__":

    print(f"=== GHP/EHP 필터링 시작: {TODAY} ===")

    n1 = filter_and_save(LOCAL_SRC,  LOCAL_DEST,  "로컬")

    n2 = filter_and_save(NET_SRC,    NET_DEST,    "NAS")

    print(f"=== 완료: {n1}건(로컬) / {n2}건(NAS) ===")

