"""Apply only after exact live results, syntax checks, original hashes and service lock."""
import argparse
import ast
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

EXPECTED = {"R26BK01789188": "경상남도", "R26BK01788813": "서울특별시"}
NAMES = ("g2b_joint_region.py", "kakao_send_tb0485.py", "main_send.py")


def validate_result(bid, result):
    data = result.get("data", {})
    if not (result.get("ok") and data.get("bid_no") == bid and data.get("bid_ord") == "000"
            and data.get("regions") == [EXPECTED[bid]] and data.get("ratio") == "49"
            and data.get("duty") == "해당"
            and -60 <= time.time() - data.get("checked_at", 0) <= 900):
        raise SystemExit("[STOP] 실제 상세값 검증 실패 또는 15분 경과: " + bid)
    print("[VERIFIED] %s %s 49%%" % (bid, EXPECTED[bid]), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default="/home/pi/n_data")
    parser.add_argument("--verified-file")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    target = Path(args.target).resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    for name in NAMES:
        ast.parse((source / name).read_text(encoding="utf-8"))
    if args.verified_file:
        results = json.loads(Path(args.verified_file).read_text(encoding="utf-8"))
    else:
        process = subprocess.Popen([sys.executable, str(source / "g2b_joint_region.py"), "--worker"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   universal_newlines=True, start_new_session=True)
        try:
            output, _ = process.communicate(json.dumps([[bid, "000"] for bid in EXPECTED]), timeout=360)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise SystemExit("[STOP] 실제 조회 시간 초과 (운영 변경 없음)")
        results = {}
        for line in output.splitlines():
            results.update(json.loads(line))
    for bid in EXPECTED:
        validate_result(bid, results.get(bid + "-000", {}))
    # Same lock as the production service: never replace files during a run.
    with open("/tmp/main_send.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("[STOP] 운영 서비스 실행 중 (변경 없음)")
        for name, expected in manifest["original_sha256"].items():
            p = target / name
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                raise SystemExit("[STOP] 원본 해시 불일치: " + name + " (변경 없음)")
        backup = target / ("backup_joint_web_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        backup.mkdir()
        existed = {name: (target / name).exists() for name in NAMES}
        for name in NAMES:
            if existed[name]:
                shutil.copy2(target / name, backup / name)
        try:
            for name in NAMES:
                temporary = target / (name + ".joint-new")
                shutil.copyfile(source / name, temporary)
                if existed[name]:
                    shutil.copymode(target / name, temporary)
                else:
                    temporary.chmod(0o644)
                temporary.replace(target / name)
        except Exception:
            for name in NAMES:
                if existed[name]:
                    shutil.copy2(backup / name, target / name)
                elif (target / name).exists():
                    (target / name).unlink()
            raise
        print("[BACKUP] " + str(backup))
        print("[APPLIED] 실조회·구문·원본 해시·운영 잠금 확인 후 적용. 발송·재발송·타이머 변경 없음.")


if __name__ == "__main__":
    main()
