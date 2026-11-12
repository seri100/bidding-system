
# -*- coding: utf-8 -*-

from pathlib import Path

from datetime import datetime



def log_line(log_dir: str, name: str, msg: str):

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    fp = Path(log_dir) / f"{name}.log"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fp.open("a", encoding="utf-8").write(f"[{ts}] {msg}\n")

