
from pathlib import Path



# 공유 폴더 위치 (출력파일 저장)

BASE_DIR = Path("/mnt/test_share").resolve()



# 라즈베리파이 내부 로그 저장 위치

LOCAL_LOG_DIR = Path("/home/pi/seri_Alarm_Server6/logs").resolve()



def init_output_dirs():

    """공유폴더 및 로컬 로그 디렉토리 확인"""

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)



    test_file = BASE_DIR / ".test_write"

    try:

        test_file.write_text("ok", encoding="utf-8")

        test_file.unlink(missing_ok=True)

    except Exception as e:

        raise RuntimeError(f"[ERROR] 공유폴더 쓰기 실패: {BASE_DIR}\n원인: {e}")



def out(*parts) -> Path:

    """공유폴더 하위 경로 생성기"""

    return BASE_DIR.joinpath(*parts)



def log(*parts) -> Path:

    """로컬 로그파일 경로 생성기"""

    return LOCAL_LOG_DIR.joinpath(*parts)


