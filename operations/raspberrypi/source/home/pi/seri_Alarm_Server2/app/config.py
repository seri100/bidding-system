
import os

from dataclasses import dataclass

from pathlib import Path



BASE_DIR = Path("/home/pi/seri_Alarm_Server2")

DATA_DIR = BASE_DIR / "data"

LOG_DIR = BASE_DIR / "logs"





def _env(name: str, default: str = "") -> str:

    v = os.getenv(name, default)

    return v.strip() if isinstance(v, str) else default





@dataclass(frozen=True)

class Config:

    # 파일

    company_xlsx: Path = DATA_DIR / "companys.xlsx"



    # 로그

    log_file: Path = LOG_DIR / "app.log"



    # Alligo (환경변수로 주입)

    # - ALLIGO_KEY, ALLIGO_USERID, ALLIGO_SENDER

    alligo_key: str = _env("ALLIGO_KEY")

    alligo_userid: str = _env("ALLIGO_USERID")

    alligo_sender: str = _env("ALLIGO_SENDER")  # 발신번호(숫자만 또는 하이픈 포함 가능)

    alligo_test_mode: bool = _env("ALLIGO_TEST", "0") in ("1", "true", "True")



    # 기본 수신자(테스트용)

    default_receiver: str = _env("DEFAULT_RECEIVER", "REDACTED_PRIVATE_VALUE")





def load_config() -> Config:

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    return Config()

