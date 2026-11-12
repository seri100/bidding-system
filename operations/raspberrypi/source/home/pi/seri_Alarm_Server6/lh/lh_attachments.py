# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
import os
import re
import requests

from lh_notice_doc import DOWNLOAD_URL


def _clean_name(value, fallback):
    name = str(value or "").replace("\\", "_").replace("/", "_").replace("\x00", "").strip()
    name = re.sub(r'[<>:"|?*]', "_", name).rstrip(". ")
    return name[:220] or fallback


def _notice_day(row):
    for key in ("입찰공고일", "공고일", "공고일자"):
        digits = re.sub(r"\D", "", str(row.get(key) or ""))
        if len(digits) >= 8:
            try:
                return datetime.strptime(digits[:8], "%Y%m%d")
            except ValueError:
                pass
    return datetime.now()


def _bid_no(row):
    return _clean_name(row.get("공고번호") or row.get("notice_no"), "UNKNOWN")


def save_target_attachments(rows, session=None, output_root=None, log=print):
    root = Path(output_root or "REDACTED_PRIVATE_VALUE") / "첨부파일"
    http = session or requests.Session()
    total_rows = 0

    for row in rows or []:
        if not isinstance(row, dict) or row.get("_첨부처리완료"):
            continue
        row["_첨부처리완료"] = True
        bid_no = _bid_no(row)
        items = row.get("첨부파일목록") or []
        if not isinstance(items, list):
            items = []

        if not items:
            row["첨부파일폴더"] = ""
            row["첨부파일수"] = 0
            row["첨부저장상태"] = "첨부없음"
            log("[ATTACH][NONE] bid={}".format(bid_no))
            continue

        day = _notice_day(row)
        folder = root / ("%04d년" % day.year) / ("%02d월" % day.month) / ("%02d일" % day.day) / bid_no
        folder.mkdir(parents=True, exist_ok=True)
        ok_count = 0
        errors = []

        for seq, item in enumerate(items, 1):
            if not isinstance(item, dict):
                continue
            display = str(item.get("표시파일명") or "").strip()
            saved = str(item.get("서버파일명") or "").strip()
            name = _clean_name(display, "attachment_%02d.bin" % seq)
            path = folder / name
            part = path.with_name(path.name + ".part")
            try:
                if path.exists() and path.stat().st_size > 0:
                    ok_count += 1
                    log("[ATTACH][EXISTS] bid={} file={} bytes={}".format(bid_no, name, path.stat().st_size))
                    continue
                if not saved:
                    raise RuntimeError("server filename missing")
                if part.exists():
                    part.unlink()
                response = http.post(
                    DOWNLOAD_URL,
                    data={
                        "download.filespec": "bidinfo",
                        "download.filename": display.replace(" ", ""),
                        "download.savedname": saved,
                        "download.bidnum": "",
                    },
                    timeout=(10, 120),
                    stream=True,
                )
                response.raise_for_status()
                content_type = str(response.headers.get("Content-Type", "")).lower()
                with part.open("wb") as handle:
                    for chunk in response.iter_content(256 * 1024):
                        if chunk:
                            handle.write(chunk)
                size = part.stat().st_size
                if size <= 0:
                    raise RuntimeError("empty response")
                if "text/html" in content_type and size < 1024 * 1024:
                    raise RuntimeError("HTML response instead of attachment")
                os.replace(str(part), str(path))
                ok_count += 1
                log("[ATTACH][OK] bid={} file={} bytes={}".format(bid_no, name, size))
            except Exception as exc:
                try:
                    if part.exists():
                        part.unlink()
                except Exception:
                    pass
                errors.append("{}: {}".format(name, exc))
                log("[ATTACH][ERR] bid={} file={} error={}".format(bid_no, name, exc))

        row["첨부파일폴더"] = str(folder)
        row["첨부파일수"] = ok_count
        row["첨부저장상태"] = "정상" if not errors else "일부실패 {}/{}".format(len(errors), len(items))
        row["첨부오류"] = " | ".join(errors)[:1000] if errors else ""
        total_rows += 1

    return total_rows
