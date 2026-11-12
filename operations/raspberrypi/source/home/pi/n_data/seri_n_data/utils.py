
# -*- coding: utf-8 -*-



import os

import sys

import re

import time

import json

from datetime import datetime

from pathlib import Path

from urllib.parse import unquote



import requests

from requests.exceptions import RequestException



from .config import SERVICE_KEY_ENV, KEY_PATH, DIR_LOG_MAIN



# -----------------------------

# 공통 유틸 함수들

# -----------------------------



# openpyxl 이 싫어하는 제어문자 제거용 정규식

_ILLEGAL_EXCEL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")





def log(msg: str) -> None:
    """
    표준 로그:
      - 콘솔(journalctl) 출력
      - /mnt/vol1/bid/n_data/logs/main_send/main_send_YYYYMMDD.log 에 일자별 파일로 저장
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"

    # 1) 콘솔로 출력 (systemd journal 에 남음)
    try:
        print(line, flush=True)
    except Exception:
        # 콘솔 출력 실패해도 전체 흐름은 깨지지 않도록
        pass

    # 2) 파일 로그 기록
    try:
        DIR_LOG_MAIN.mkdir(parents=True, exist_ok=True)
        fname = DIR_LOG_MAIN / f"main_send_{datetime.now().strftime('%Y%m%d')}.log"
        with open(fname, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # 파일 기록 실패해도 서비스는 계속
        pass

def _norm(x):

    """

    API 응답 element 를 문자열로 정규화

    - list/dict -> 안의 값들을 공백으로 join

    - None -> ""

    - 그 외 -> str(x).strip()

    """

    if isinstance(x, list):

        return " ".join(_norm(v) for v in x)

    if isinstance(x, dict):

        return " ".join(_norm(v) for v in x.values())

    if x is None:

        return ""

    return str(x).strip()





def clamp_len(s, n=80):

    """

    문자열 길이 n 으로 잘라줌 (말줄임표 ...)

    """

    s = _norm(s)

    if len(s) <= n:

        return s

    return s[: n - 1] + "..."





def sanitize_for_excel(value):

    """

    openpyxl 이 싫어하는 제어문자를 제거

    """

    if not isinstance(value, str):

        return value

    return _ILLEGAL_EXCEL_CHARS.sub("", value)





# -----------------------------

# 공공데이터 API 키 관련

# -----------------------------



def get_service_key() -> str:

    """

    공공데이터포털 SERVICE_KEY 로딩

    - 우선 환경변수 SERVICE_KEY

    - 없으면 KEY_PATH 파일(/home/pi/n_data/bid_api_key.txt)

    - 퍼센트 인코딩 되어 있으면 unquote 로 복원

    """

    key = None



    if SERVICE_KEY_ENV:

        key = SERVICE_KEY_ENV.strip()

    else:

        try:

            key = Path(KEY_PATH).read_text(encoding="utf-8").strip()

        except Exception:

            log(f"[ERR] API key file not found: {KEY_PATH}")

            return ""



    if "%" in key:

        try:

            key = unquote(key)

        except Exception as e:

            log(f"[WARN] unquote SERVICE_KEY failed: {e}")



    return key





# -----------------------------

# API 호출용 안전 래퍼 (타임아웃 + 재시도)

# -----------------------------



def safe_get(url, params=None, timeout=30, max_retries=3, sleep_sec=3):

    """

    외부 API 호출용 래퍼

    - timeout: 초 (기본 30초)

    - max_retries: 최대 재시도 횟수

    - 실패 시 로그 남기고 재시도, 끝까지 실패하면 예외 발생

    """

    last_err = None

    for i in range(1, max_retries + 1):

        try:

            resp = requests.get(url, params=params, timeout=timeout)

            resp.raise_for_status()

            return resp

        except RequestException as e:

            last_err = e

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 여기서는 log() 를 쓰면 또 log 안에서 safe_get 을 부를 수 있으므로

            # 순환 의존 방지를 위해 직접 출력 + 파일로그는 생략해도 됨

            msg = f"[{ts}] [ERR] safe_get try={i}/{max_retries} url={url} err={e}"

            try:

                print(msg, flush=True)

            except Exception:

                pass



            if i < max_retries:

                time.sleep(sleep_sec)



    # 최종 실패 시 예외 발생

    if last_err:

        raise last_err

    raise RuntimeError("safe_get: unknown error")





__all__ = [

    "log",

    "_norm",

    "clamp_len",

    "sanitize_for_excel",

    "get_service_key",

    "safe_get",

]


