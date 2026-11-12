#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n_data 변경공고 알림톡 패치

대상 기본값:
    /home/pi/n_data/main_send.py

적용 내용:
1) 공고번호 차수(-000, -001, -002...)는 기존대로 서로 다른 발송 키로 유지한다.
2) 변경공고에서 presmptPrce가 빠지고 bdgtAmt/추정금액만 내려와도 금액 판정을 한다.
3) 변경공고를 재판정하는 과정에서 이미 계산된 수신자가 사라지지 않게 보존한다.
4) 알림톡 공고명 앞에 [변경공고]를 붙인다.
5) 원본 백업, 구문 검사, 원자적 교체를 수행한다.

사용 예:
    python3 apply_n_data_change_notice_patch.py --dry-run
    sudo python3 apply_n_data_change_notice_patch.py
    python3 apply_n_data_change_notice_patch.py --self-test
"""

from __future__ import print_function

import argparse
import ast
import datetime as _dt
import difflib
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

DEFAULT_FILE = Path("/home/pi/n_data/main_send.py")
PATCH_ID = 'REDACTED_PRIVATE_VALUE'
HELPER_MARKER = "# __CHANGE_NOTICE_ALIMTALK_V1__"
MESSAGE_MARKER = "# __CHANGE_NOTICE_ALIMTALK_V1__: 알림톡 공고명 표기"


class PatchError(RuntimeError):
    pass


def _function_starts(lines, name):
    pat = re.compile(r"^def\s+" + re.escape(name) + r"\s*\(")
    return [i for i, line in enumerate(lines) if pat.match(line)]


def _find_function_span(lines, name):
    """가장 뒤에 정의된 최상위 함수의 시작/끝을 반환한다."""
    starts = _function_starts(lines, name)
    if not starts:
        raise PatchError("함수를 찾지 못했습니다: {}".format(name))

    start = starts[-1]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line[0].isspace():
            end = i
            break
    return start, end, len(starts)


def _replace_function(lines, name, replacement):
    start, end, count = _find_function_span(lines, name)
    lines[start:end] = replacement.strip("\n").splitlines() + [""]
    return count


HELPER_BLOCK = r'''
# __CHANGE_NOTICE_ALIMTALK_V1__
def _is_change_notice(row):
    """
    나라장터 변경/정정공고 판정.

    - ntceKindNm 등에 '변경' 또는 '정정'이 있으면 변경공고
    - 공고 차수가 001 이상이면 변경공고
    """
    try:
        import re as _re

        raw = _fr_get_raw(row)
        kind = _fr_norm_text(
            raw.get("ntceKindNm")
            or raw.get("ntceKind")
            or row.get("ntceKindNm")
            or row.get("공고종류")
            or row.get("공고구분")
            or ""
        )
        if ("변경" in kind) or ("정정" in kind):
            return True

        ord_value = _fr_norm_text(
            raw.get("bidNtceOrd")
            or row.get("bidNtceOrd")
            or row.get("차수")
            or row.get("공고차수")
            or "000"
        )
        digits = _re.sub(r"[^0-9]", "", ord_value)
        return bool(digits and int(digits) > 0)
    except Exception:
        return False
'''.strip("\n")


PRICE_FUNCTION = r'''
def _fr_get_presmpt_price(row):
    """
    추정가격을 우선 사용하되, 변경공고 응답에 추정가격이 빠진 경우
    bdgtAmt/추정금액/기초금액을 금액 판정용 보조값으로 사용한다.
    """
    raw = _fr_get_raw(row)

    return _fr_parse_int(
        raw.get("presmptPrce")
        or raw.get("PresmptPrce")
        or row.get("PresmptPrce")
        or row.get("presmptPrce")
        or row.get("추정가격")
        or raw.get("presmptPrceAmt")
        or raw.get("estimatPrce")
        or raw.get("estimatPrice")
        # 변경공고 보조 금액 필드
        or raw.get("bdgtAmt")
        or raw.get("budgetAmt")
        or raw.get("asignBdgtAmt")
        or row.get("bdgtAmt")
        or row.get("추정금액")
        or row.get("기초금액")
        or 0
    )
'''.strip("\n")


FINAL_RULE_FUNCTION = r'''
def _fr_apply_final_rule(row, log_fn=None):
    def _log(msg):
        try:
            if callable(log_fn):
                log_fn(msg)
        except Exception:
            pass

    # 변경공고를 여러 단계에서 다시 판정할 때 앞 단계의 정상 수신자까지
    # 빈 값으로 덮어쓰지 않도록 먼저 보관한다.
    previous_receivers = []
    try:
        previous_receivers = [
            x.strip()
            for x in str(row.get("수신번호") or "").split(",")
            if x.strip()
        ]
        previous_receivers = list(dict.fromkeys(previous_receivers))
    except Exception:
        previous_receivers = []

    scope = _fr_decide_scope(row)
    local_region = _fr_decide_local_region(row)
    ind = _fr_get_industry_code(row)
    receivers = _fr_decide_receivers(row)
    is_change = _is_change_notice(row)

    # 변경공고의 일부 응답에는 지역/가격 보조 필드가 빠질 수 있다.
    # 이미 앞 단계에서 계산된 수신자가 있다면 그 값을 승계한다.
    if is_change and not receivers and previous_receivers:
        receivers = previous_receivers
        _log(
            "[CHANGE_NOTICE][KEEP-RECV] "
            "ind={} scope={} recv={}".format(ind, scope, receivers)
        )

    rep = "전국" if scope == "전국" else local_region

    if isinstance(row, dict):
        row["대표지역"] = rep
        row["수신번호"] = ",".join(receivers) if receivers else ""
        row["알림대상"] = "Y" if receivers else "N"
        row["_force_norecv"] = "" if receivers else "1"
        row["_is_change_notice"] = "1" if is_change else ""

    try:
        raw = _fr_get_raw(row)
        bid_no = _fr_norm_text(raw.get("bidNtceNo") or row.get("공고번호"))
        bid_ord = _fr_norm_text(
            raw.get("bidNtceOrd") or row.get("차수") or "000"
        ) or "000"
        key = "{}-{}".format(bid_no, bid_ord) if bid_no else ""
    except Exception:
        key = ""

    if is_change:
        try:
            close_time = _fr_norm_text(
                (_fr_get_raw(row) or {}).get("bidClseDt")
                or row.get("입찰마감일시")
                or ""
            )
        except Exception:
            close_time = ""
        _log(
            "[CHANGE_NOTICE] key={} close={} ind={} scope={} "
            "local_region={} rep={} recv={} amount={}".format(
                key,
                close_time,
                ind,
                scope,
                local_region,
                rep,
                receivers,
                _fr_get_presmpt_price(row),
            )
        )

    _log(
        "[FINAL_RULE] key={} ind={} scope={} local_region={} "
        "rep={} recv={} method={!r} presmpt={}".format(
            key,
            ind,
            scope,
            local_region,
            rep,
            receivers,
            _fr_get_method_text(row),
            _fr_get_presmpt_price(row),
        )
    )

    return row
'''.strip("\n")


MESSAGE_INSERT = r'''
    # __CHANGE_NOTICE_ALIMTALK_V1__: 알림톡 공고명 표기
    if _is_change_notice(row):
        _bid_name_text = str(bid_name or "").strip()
        if not _bid_name_text.startswith("[변경공고]"):
            bid_name = "[변경공고] " + _bid_name_text
'''.strip("\n").splitlines()


def patch_source(source):
    lines = source.splitlines()
    notes = []

    already_complete = (
        HELPER_MARKER in source
        and MESSAGE_MARKER in source
        and 'raw.get("bdgtAmt")' in source
        and 'row["_is_change_notice"]' in source
    )
    if already_complete:
        return source, False, ["이미 {} 패치가 적용되어 있습니다.".format(PATCH_ID)]

    if HELPER_MARKER in source or MESSAGE_MARKER in source:
        raise PatchError(
            "동일 패치의 일부 흔적만 발견했습니다. "
            "백업본과 현재 파일을 확인한 뒤 다시 적용하십시오."
        )

    for name in (
        "_fr_get_presmpt_price",
        "_fr_apply_final_rule",
        "build_tb0485_fields",
    ):
        _find_function_span(lines, name)

    # 기존 코드가 공고번호+차수를 합친 키를 쓰는지 검증한다.
    if 'f"{bid_no}-{bid_ord}"' not in source and "f'{bid_no}-{bid_ord}'" not in source:
        raise PatchError(
            "공고번호+차수 발송 키 구조를 확인하지 못했습니다. "
            "현재 main_send.py 버전과 패치 대상이 다를 수 있습니다."
        )
    notes.append("공고번호+차수 별도 키 구조 확인")

    start, _, _ = _find_function_span(lines, "_fr_get_presmpt_price")
    lines[start:start] = HELPER_BLOCK.splitlines() + ["", ""]
    notes.append("_is_change_notice 추가")

    count = _replace_function(lines, "_fr_get_presmpt_price", PRICE_FUNCTION)
    if count > 1:
        notes.append(
            "_fr_get_presmpt_price 중복 정의 {}개 중 마지막 정의를 교체".format(count)
        )
    else:
        notes.append("변경공고 금액 fallback(bdgtAmt/추정금액) 추가")

    count = _replace_function(lines, "_fr_apply_final_rule", FINAL_RULE_FUNCTION)
    if count > 1:
        notes.append(
            "_fr_apply_final_rule 중복 정의 {}개 중 마지막 정의를 교체".format(count)
        )
    else:
        notes.append("변경공고 수신자 보존 및 전용 로그 추가")

    start, end, _ = _find_function_span(lines, "build_tb0485_fields")
    assignment_idx = None
    for i in range(start, end):
        if re.match(r'^\s+bid_name\s*=\s*_g\(\s*"bidNtceNm"', lines[i]):
            assignment_idx = i
            break
    if assignment_idx is None:
        raise PatchError(
            "build_tb0485_fields 안의 bid_name 할당문을 찾지 못했습니다."
        )
    lines[assignment_idx + 1:assignment_idx + 1] = [""] + MESSAGE_INSERT + [""]
    notes.append("알림톡 공고명에 [변경공고] 표시 추가")

    patched = "\n".join(lines)
    if source.endswith("\n"):
        patched += "\n"

    try:
        ast.parse(patched)
    except SyntaxError as exc:
        raise PatchError(
            "패치 결과 구문 검사 실패: {}:{} {}".format(
                exc.lineno, exc.offset, exc.msg
            )
        )

    checks = {
        "helper": HELPER_MARKER in patched,
        "amount fallback": 'raw.get("bdgtAmt")' in patched,
        "message marker": MESSAGE_MARKER in patched,
        "change log": "[CHANGE_NOTICE]" in patched,
        "receiver preservation": "[CHANGE_NOTICE][KEEP-RECV]" in patched,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise PatchError("패치 검증 실패: {}".format(", ".join(failed)))

    return patched, True, notes


def _atomic_write(path, content, mode):
    path = Path(path)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_name, stat.S_IMODE(mode))
        os.replace(temp_name, str(path))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def apply_patch(path, dry_run=False):
    path = Path(path)
    if not path.exists():
        raise PatchError("대상 파일이 없습니다: {}".format(path))
    if not path.is_file():
        raise PatchError("대상이 일반 파일이 아닙니다: {}".format(path))

    source = path.read_text(encoding="utf-8")
    patched, changed, notes = patch_source(source)

    for note in notes:
        print("[PATCH] {}".format(note))

    if not changed:
        print("[OK] 변경할 내용이 없습니다.")
        return 0

    if dry_run:
        diff = difflib.unified_diff(
            source.splitlines(),
            patched.splitlines(),
            fromfile=str(path),
            tofile=str(path) + " (patched)",
            lineterm="",
        )
        print("\n".join(diff))
        print("[DRY-RUN] 파일은 변경하지 않았습니다.")
        return 0

    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(
        "{}.bak_change_notice_{}".format(path.name, timestamp)
    )
    shutil.copy2(str(path), str(backup))

    original_mode = path.stat().st_mode
    try:
        _atomic_write(path, patched, original_mode)
        ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        shutil.copy2(str(backup), str(path))
        raise

    print("[OK] 적용 완료: {}".format(path))
    print("[BACKUP] {}".format(backup))
    print("[VERIFY] python3 -m py_compile {}".format(path))
    print(
        "[SMOKE] 로그에서 [CHANGE_NOTICE]와 공고번호-001을 확인하십시오."
    )
    return 0


def self_test():
    fixture = r'''
def _fr_get_raw(row):
    return row.get("원문") or {}

def _fr_norm_text(v):
    return "" if v is None else str(v).strip()

def _fr_parse_int(v):
    return int(str(v).replace(",", "").replace("원", "") or "0")

def _fr_get_presmpt_price(row):
    raw = _fr_get_raw(row)
    return _fr_parse_int(raw.get("presmptPrce") or 0)

def _fr_decide_scope(row):
    return "전국" if _fr_get_presmpt_price(row) >= 1000000000 else "지역"

def _fr_decide_local_region(row):
    return ""

def _fr_get_industry_code(row):
    return "6202"

def _fr_decide_receivers(row):
    return ["REDACTED_PHONE"] if _fr_decide_scope(row) == "전국" else []

def _fr_get_method_text(row):
    return ""

def _fr_apply_final_rule(row, log_fn=None):
    row["수신번호"] = ""
    return row

def build_tb0485_fields(row: dict) -> dict:
    raw = row.get("원문") or {}
    def _g(*names, default=""):
        for name in names:
            if raw.get(name):
                return raw.get(name)
            if row.get(name):
                return row.get(name)
        return default
    bid_no = str(_g("bidNtceNo", "공고번호", default="")).strip()
    bid_ord = str(_g("bidNtceOrd", "차수", default="000")).strip() or "000"
    bid_name = _g("bidNtceNm", "공고명", default="공고명미기재")
    close_time = _g("bidClseDt", "입찰마감일시", default="미기재")
    return {"bid_name": bid_name, "bid_no": bid_no, "bid_ord": bid_ord}

def dummy_key(bid_no, bid_ord):
    key = f"{bid_no}-{bid_ord}"
    return key
'''.lstrip()

    patched, changed, notes = patch_source(fixture)
    assert changed
    assert HELPER_MARKER in patched
    assert 'raw.get("bdgtAmt")' in patched
    assert MESSAGE_MARKER in patched
    ast.parse(patched)

    patched2, changed2, _ = patch_source(patched)
    assert not changed2
    assert patched2 == patched

    row = {
        "공고번호": "R26BK01622372",
        "차수": "001",
        "공고명": "(가칭)에코1유치원 교사신축 기계설비공사(계속비)",
        "추정금액": "2,098,888,000원",
        "원문": {
            "bidNtceNo": "R26BK01622372",
            "bidNtceOrd": "001",
            "ntceKindNm": "변경공고",
            "bdgtAmt": 2098888000,
            "bidClseDt": "2026-07-28 10:00:00",
            "indstrytyCd": "6202",
        },
    }
    digits = re.sub(r"[^0-9]", "", str(row["차수"]))
    assert int(digits) > 0
    assert int(row["원문"]["bdgtAmt"]) == 2098888000
    assert "{}-{}".format(
        row["원문"]["bidNtceNo"], row["원문"]["bidNtceOrd"]
    ) == "R26BK01622372-001"

    print("[SELF-TEST] PASS")
    for note in notes:
        print("[SELF-TEST] {}".format(note))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="n_data 변경공고 알림톡 패치"
    )
    parser.add_argument(
        "--file",
        default=str(DEFAULT_FILE),
        help="패치할 main_send.py 경로",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="diff만 출력하고 파일은 변경하지 않음",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="패처 자체 테스트만 수행",
    )
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            return self_test()
        return apply_patch(Path(args.file), dry_run=args.dry_run)
    except PatchError as exc:
        print("[ERROR] {}".format(exc), file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(
            "[ERROR] 권한이 없습니다: {}. sudo로 다시 실행하십시오.".format(exc),
            file=sys.stderr,
        )
        return 3
    except Exception as exc:
        print("[ERROR] 예상하지 못한 오류: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
