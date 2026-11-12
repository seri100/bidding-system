
# -*- coding: utf-8 -*-

from __future__ import annotations



import os

from pathlib import Path



# --------------------------------------------------

# 기본 경로 / 상수

# --------------------------------------------------



# 공공데이터 API 키 (환경변수 또는 파일에서 사용)

SERVICE_KEY_ENV = os.getenv("SERVICE_KEY")

KEY_PATH = "/home/pi/n_data/bid_api_key.txt"



# 나라장터 공사공고 API URL

API_BASE = (

    "http://apis.data.go.kr/1230000/ad/"

    "REDACTED_LONG_LITERAL"

)



# 대상 업종 코드

TARGET_INDS = ["6202", "0040", "0037", "0038", "0039"]



# 기본 출력 폴더 (NAS 마운트 기준)

OUTDIR = Path("/mnt/vol1/bid/n_data")

NDATA_BASE = OUTDIR



# 표준 폴더 구조

DIR_RAW = NDATA_BASE / "raw"              # 원본 통합 엑셀

DIR_SPLIT = NDATA_BASE / "split"          # 지역/공종 분할 엑셀

DIR_SPLIT_HISTORY = DIR_SPLIT / "history" # 분할 엑셀 히스토리

DIR_REPORT = NDATA_BASE / "report"        # 리포트(HTML/XLSX)

DIR_LOG = NDATA_BASE / "logs"             # 공용 로그 루트

DIR_LOG_KAKAO = DIR_LOG / "kakao"         # 알림톡 발송 로그

DIR_LOG_MAIN = DIR_LOG / "main_send"      # main_send 전용 로그(확장 여지)



# 디렉터리 생성

for d in [

    NDATA_BASE,

    DIR_RAW,

    DIR_SPLIT,

    DIR_SPLIT_HISTORY,

    DIR_REPORT,

    DIR_LOG,

    DIR_LOG_KAKAO,

    DIR_LOG_MAIN,

]:

    d.mkdir(parents=True, exist_ok=True)



# --------------------------------------------------

# 보존 기간(일)

# --------------------------------------------------

# RAW 통합 엑셀

RETENTION_RAW_DAYS = 90

# 분할 엑셀 (현재 파일)

RETENTION_SPLIT_DAYS = 60

# 분할 엑셀 history

RETENTION_SPLIT_HISTORY_DAYS = 7

# 리포트(HTML/XLSX)

RETENTION_REPORT_DAYS = 180

# 로그

RETENTION_LOG_DAYS = 365



# --------------------------------------------------

# 알리고 / 알림톡 관련 설정

# --------------------------------------------------



# 기본 템플릿 코드 / 발신번호

TEMPLATE_CODE = os.getenv("ALLIGO_TPL_CODE", "TB_0485")

SENDER_NUM = os.getenv("ALLIGO_SENDER", "REDACTED_PRIVATE_VALUE")



# 업종코드별 템플릿 매핑 (필요 시 확장)

# 현재는 모두 기본 템플릿을 사용

TEMPLATE_MAP_BY_IND = {

    "6202": TEMPLATE_CODE,

    "0040": TEMPLATE_CODE,

    "0037": TEMPLATE_CODE,

    "0038": TEMPLATE_CODE,

    "0039": TEMPLATE_CODE,

}



# 테스트용: 특정 번호 1인 발송 모드

TEST_SINGLE_MODE = os.getenv("KAKAO_SINGLE_MODE", "0") == "1"

TEST_SINGLE_PHONE = os.getenv("KAKAO_SINGLE_PHONE", "REDACTED_PRIVATE_VALUE")



# 발송 로그 파일 (sender.py 에서 사용)

SENT_LOG_FILE = DIR_LOG_KAKAO / "alimtalk_sent.log"



# --------------------------------------------------

# 필터링 / 기타

# --------------------------------------------------



# 금액 필터 (0이면 사용 안 함)

MIN_ESTIMATE_FOR_TARGET = 0

# 공동도급 비율 필터 필요 여부 (현재 미사용)

REQUIRE_JOINT_RATE = False



# 락 파일 경로 (실행 중복 방지용, lockutil 에서 사용)

LOCK_FILE = "/run/lock/seri-main-send.lock"


