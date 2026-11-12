
# -*- coding: utf-8 -*-

"""

공공데이터의 공사공고 가져오기 - LH 크롤링 결과 엑셀 변환 + 알림톡 통지 스크립트



기능:

1) REDACTED_PRIVATE_VALUE/LH_*.csv 중 가장 최신 파일 찾기

2) pandas로 읽어서 /mnt/vol1/bid/lh/LH_YYYYMMDD_HHMMSS.xlsx 로 저장

3) Alligo 알림톡으로 파일 정보 전송

"""



import os

import sys

from pathlib import Path

from datetime import datetime



import pandas as pd



# Alligo 모듈 (이미 main_send 등에서 쓰는 것과 동일하게 사용)

try:

    from alligo import Alligo

except ImportError:

    Alligo = None



# -----------------------------

# 경로 설정

# -----------------------------

EXPORT_DIR = Path("REDACTED_PRIVATE_VALUE")   # LH CSV 저장 위치

OUT_DIR    = Path("/mnt/vol1/bid/lh")                      # 엑셀 저장 위치 (윈도우: Z:\\VOL1\\bid\\lh)

OUT_DIR.mkdir(parents=True, exist_ok=True)



# 템플릿/발신번호/수신번호

TEMPLATE_CODE = os.getenv("ALLIGO_LH_TPL", "TZ_4492")      # LH 템플릿 코드 (기존 LH 알림톡 템플릿 재사용)

SENDER_NUM    = os.getenv("ALLIGO_LH_SENDER", "REDACTED_PRIVATE_VALUE")



# 요청하신 기본 원칙: 테스트 계열은 REDACTED_PHONE 한 번호만 사용

DEFAULT_RECEIVERS = ["REDACTED_PRIVATE_VALUE"]





def log(msg: str):

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("[LH_NOTIFY]", ts, msg)





def find_latest_csv():

    """exports 디렉터리에서 최신 LH_*.csv 하나 찾기"""

    if not EXPORT_DIR.exists():

        log(f"EXPORT_DIR 없음: {EXPORT_DIR}")

        return None



    files = sorted(EXPORT_DIR.glob("LH_*.csv"))

    if not files:

        log("LH_*.csv 파일이 없습니다.")

        return None



    latest = files[-1]

    log(f"최신 CSV: {latest}")

    return latest





def convert_to_excel(csv_path: Path) -> Path:

    """CSV → 엑셀(xlsx) 변환 후 OUT_DIR에 저장"""

    try:

        df = pd.read_csv(csv_path)  # utf-8로 저장했으므로 별도 인코딩 지정 안함

    except Exception as e:

        log(f"CSV 읽기 오류: {csv_path} / {e}")

        raise



    # 파일명 재사용 (확장자만 xlsx로 변경)

    stem = csv_path.stem           # LH_20251016_181005

    xlsx_path = OUT_DIR / f"{stem}.xlsx"



    try:

        df.to_excel(xlsx_path, index=False)

        log(f"엑셀 저장: {xlsx_path}")

        return xlsx_path

    except Exception as e:

        log(f"엑셀 저장 오류: {xlsx_path} / {e}")

        raise





def send_kakao_notify(xlsx_path: Path, row_count: int):

    """생성된 엑셀 파일 정보를 알림톡으로 전송"""

    if Alligo is None:

        log("alligo 모듈이 없습니다. (알림톡 전송 생략)")

        return



    a = Alligo()



    # 윈도우에서 보이는 경로 안내 (Z:\VOL1\...)

    win_path = f"Z:\\VOL1\\bid\\lh\\{xlsx_path.name}"



    subject = "[세리공영] LH 크롤링 엑셀 생성"

    msg_lines = [

        "[세리공영-LH]",

        "",

        "LH 크롤링 결과 엑셀 파일이 생성되었습니다.",

        "",

        f"파일명 : {xlsx_path.name}",

        f"건수   : {row_count} 건",

        "",

        f"저장경로(윈도우) : {win_path}",

        "",

        "※ Z: 드라이브가 안 보이면 NAS 마운트 상태를 확인하세요."

    ]

    message = "\n".join(msg_lines)



    receivers = DEFAULT_RECEIVERS



    log(f"알림톡 전송 준비: {receivers}")

    ok = a.sendTalk(TEMPLATE_CODE, SENDER_NUM, subject, message, receivers)

    if ok:

        log("알림톡 전송 성공")

    else:

        log("알림톡 전송 실패")





def main():

    csv_path = find_latest_csv()

    if not csv_path:

        return



    # CSV → 엑셀 변환

    xlsx_path = convert_to_excel(csv_path)



    # 행 수 카운트해서 메시지에 넣기

    try:

        df = pd.read_excel(xlsx_path)

        cnt = len(df)

    except Exception:

        cnt = 0



    # 알림톡 발송

    send_kakao_notify(xlsx_path, cnt)





if __name__ == "__main__":

    main()

