
# -*- coding: utf-8 -*-

"""

실행 중복 방지용 락 유틸 (Python 3.9 호환 버전)

- /run/lock/seri-main-send.lock 파일 기반

"""



import os

import fcntl

from typing import Optional



from .config import LOCK_FILE

from .utils import log





def _read_pid_from_lock(fd) -> Optional[int]:

    """

    lock 파일 안에 PID가 써 있으면 읽어서 int 로 반환.

    없거나, 형식이 이상하면 None.

    """

    try:

        os.lseek(fd, 0, os.SEEK_SET)

        data = os.read(fd, 32)

        if not data:

            return None

        s = data.decode(errors="ignore").strip()

        if not s:

            return None

        return int(s)

    except Exception:

        return None





def acquire_lock() -> Optional[int]:

    """

    /run/lock/seri-main-send.lock 에 대한 비차단 락을 건다.

    - 성공 시: 락 파일 디스크립터(fd)를 반환 (int)

    - 실패 시: None 반환 (이미 다른 프로세스가 잡고 있음)



    호출한 쪽에서는 종료 전에 반드시 os.close(fd) 로 닫아야 함.

    """

    try:

        # 파일 열기 (없으면 생성)

        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o644)



        # 락 획득 시도 (non-block)

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)



        # 디버깅용으로 PID 기록

        try:

            os.ftruncate(fd, 0)

            os.write(fd, str(os.getpid()).encode())

            os.fsync(fd)

        except Exception:

            pass



        return fd

    except BlockingIOError:

        # 이미 다른 인스턴스가 락을 가지고 있음

        try:

            # 가능하면 현재 락 보유자의 PID를 찍어준다

            tmp_fd = os.open(LOCK_FILE, os.O_RDONLY)

            holder = _read_pid_from_lock(tmp_fd)

            os.close(tmp_fd)

        except Exception:

            holder = None



        if holder is not None:

            log("[LOCK] another main_send instance is running (pid=%s); exit." % holder)

        else:

            log("[LOCK] another main_send instance is running; exit.")

        return None

    except Exception as e:

        log("[LOCK][WARN] failed to acquire lock: %s" % e)

        return None


