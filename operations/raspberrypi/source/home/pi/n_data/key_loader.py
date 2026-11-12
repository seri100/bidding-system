
# -*- coding: utf-8 -*-

import os, urllib.parse, os.path



def load_service_key():

    # 1) 환경변수에서 읽기

    key = os.environ.get("SERVICE_KEY")



    # 2) 없으면 .env에서 읽기

    if not key:

        env_path = "/home/pi/n_data/.env"

        if os.path.isfile(env_path):

            with open(env_path, "r", encoding="utf-8") as f:

                for line in f:

                    if line.strip().startswith("SERVICE_KEY="):

                        key = line.strip().split("=",1)[1]

                        break



    if not key:

        raise RuntimeError("SERVICE_KEY 없음 (.env 또는 환경변수 설정 필요)")



    # 공공데이터포털 키는 종종 이중 인코딩 → 두 번 unquote

    return urllib.parse.unquote(urllib.parse.unquote(key))

