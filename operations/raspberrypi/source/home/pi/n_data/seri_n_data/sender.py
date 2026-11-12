
# -*- coding: utf-8 -*-
"""
seri_n_data.sender - 안정화 + 지역/금액별 수신번호 룰 반영 버전
"""

from __future__ import annotations
import csv
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from .config import (
    TEMPLATE_CODE,
    SENDER_NUM,
    TEST_SINGLE_MODE,
    TEST_SINGLE_PHONE,
    DIR_LOG_KAKAO,
    SENT_LOG_FILE,
)
from .utils import log


# ------------------------------------------------------
# Alligo Wrapper
# ------------------------------------------------------

class Alligo:
    def __init__(
        self,
        userid: str = "seri825",
        apikey: str = "REDACTED_PRIVATE_VALUE",
        senderkey: str = "REDACTED_PRIVATE_VALUE",
        plusid: str = "@세리공영",
        log_path: str = "/home/pi/n_data/alligoError.txt",
    ):
        self.userid = userid
        self.apikey = apikey
        self.senderkey = senderkey
        self.plusid = plusid
        self.log_path = log_path

        self.token: Optional[str] = None
        self.token_expire_ts: float = 0.0

        self.session = requests.Session()

        self.token_url = "REDACTED_PRIVATE_VALUE"
        self.send_talk_url = "REDACTED_PRIVATE_VALUE"

    # 내부 에러로그
    def _err(self, msg: str) -> None:
        try:
            p = Path(self.log_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(f"[{datetime.now()}] {msg}\n")
        except Exception:
            pass

    # 토큰 발급/재사용
    def _ensure_token(self) -> Optional[str]:
        now = time.time()
        # 유효 토큰 있으면 재사용
        if self.token and now < self.token_expire_ts - 10:
            return self.token

        try:
            r = self.session.post(
                self.token_url,
                data={"apikey": self.apikey, "userid": self.userid},
                timeout=10,
            )
            r.raise_for_status()
            js = r.json()
        except Exception as e:
            self._err(f"[TOKEN][HTTP] {e}")
            return None

        if js.get("code") != 0:
            self._err(f"[TOKEN][FAIL] {js}")
            return None

        self.token = js.get("token")
        # 20분 유효인데, 안전하게 19분으로
        self.token_expire_ts = now + (19 * 60)
        log("[ALIMTALK] token refreshed")
        return self.token

    # 알림톡 발송
    def send_talk(self, receiver: str, subject: str, message: str) -> bool:
        token = self._ensure_token()
        if not token:
            self._err("[SEND] token 없음")
            return False

        payload = {
            "apikey": self.apikey,
            "userid": self.userid,
            "token": token,
            "sender": SENDER_NUM,
            "senderkey": self.senderkey,
            "tpl_code": TEMPLATE_CODE,
            "receiver_1": receiver,
            "recvname_1": "고객님",
            "subject_1": subject,
            "message_1": message,
            "failover": "N",
        }

        try:
            r = self.session.post(self.send_talk_url, data=payload, timeout=10)
            r.raise_for_status()
            js = r.json()
        except Exception as e:
            self._err(f"[SEND][HTTP] {e}")
            return False

        if js.get("code") != 0:
            self._err(f"[SEND][FAIL] {js}")
            return False

        return True


# Global Alligo
ALIGO = Alligo(log_path=str(DIR_LOG_KAKAO / "alligo_error.log"))


# ------------------------------------------------------
# 유틸 (공통)
# ------------------------------------------------------

def _normalize_phone(num: str) -> Optional[str]:
    """
    전화번호 문자열을 숫자만 추출해서 정규화.
    - 'REDACTED_PHONE' -> 'REDACTED_PRIVATE_VALUE'
    - 엑셀에서 앞자리 0이 떨어진 '1088540340' 같은 경우:
      10자리이고 '10'으로 시작하면 '0'을 붙여서 11자리로 보정.
    """
    if not num:
        return None

    digits = "".join(ch for ch in num if ch.isdigit())
    if not digits:
        return None

    # 엑셀에서 'REDACTED_PRIVATE_VALUE'이 '1088540340' 으로 깨지는 케이스 보정
    if len(digits) == 10 and digits.startswith("10"):
        digits = "0" + digits  # 앞에 0 붙이기

    return digits


def _clean_phone_field(raw: Any) -> List[str]:
    """
    수신번호 필드:
    - NaN / None / 빈 문자열 제거
    - 구분자(쉼표, 세미콜론, 슬래시, 공백) 단위로 split
    - 숫자만 추출하여 정규화(_normalize_phone)
    - 중복 제거 + 정렬
    """
    if raw is None:
        return []

    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return []

    for sep in [";", "/", " "]:
        s = s.replace(sep, ",")

    candidates = [x.strip() for x in s.split(",") if x.strip()]
    out: Set[str] = set()

    for c in candidates:
        norm = _normalize_phone(c)
        if norm:
            out.add(norm)

    return sorted(out)


def _make_key(r: Dict[str, Any]) -> str:
    no = str(r.get("공고번호") or "").strip()
    ord_ = str(r.get("차수") or "").strip() or "000"
    return f"{no}/{ord_}" if no else ""


def _region(r: Dict[str, Any]) -> str:
    return str(r.get("지역태그") or r.get("수요지역") or "").strip()


def _ind(r: Dict[str, Any]) -> str:
    return str(r.get("공고업종코드") or "").strip()


def _title(r: Dict[str, Any]) -> str:
    return str(r.get("공고명") or "").strip()


def _parse_amount(r: Dict[str, Any]) -> int:
    """
    추정금액(원)을 정수로 파싱.
    우선순위: 추정금액_원 -> presmptPrce -> 추정금액
    숫자만 뽑아서 int 변환 실패하면 0 리턴.
    """
    val = r.get("추정금액_원") or r.get("presmptPrce") or r.get("추정금액") or ""
    s = str(val)
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return 0
    try:
        return int(digits)
    except ValueError:
        return 0


def _joint_region_from_text(txt: str) -> str:
    """
    공동도급지역 텍스트에서 지역 추출
    - '대구광역시'   -> '대구'
    - '경상북도 포항시' -> '경북'
    - '충청북도 충주시' -> '충북'
    - '세종특별자치시' -> '세종'
    그 외는 ''(빈 문자열)
    """
    t = (txt or "").strip()
    if not t:
        return ""

    if "대구" in t:
        return "대구"
    if "경상북도" in t or "경북" in t:
        return "경북"
    if "충청북도" in t or "충북" in t:
        return "충북"
    if "세종" in t:
        return "세종"
    return ""


def _effective_region(r: Dict[str, Any]) -> str:
    """
    사용자 규칙을 반영한 '실질 지역' 판정:

    1) 추정금액 11억(=1,100,000,000) 이상이면 전국
    2) 11억 미만이면
       - 지역태그가 대구/경북/충북/세종이면 그 지역
       - 지역태그가 전국이면서 공동도급지역이 특정 지역이면 그 지역
       - 그 외는 지역태그(또는 전국) 그대로
    """
    base_region = str(r.get("지역태그") or "").strip()
    joint_raw = (
        r.get("공동도급지역")
        or r.get("jntcontrctDutyRgnNm1")
        or ""
    )
    joint_region = _joint_region_from_text(joint_raw)
    amount = _parse_amount(r)

    # 1) 11억 이상은 무조건 전국
    if amount >= 1_100_000_000:
        return "전국"

    # 2) 11억 미만
    if base_region in {"대구", "경북", "충북", "세종"}:
        return base_region

    if base_region == "전국" and joint_region:
        # '전국'이지만 공동도급지역이 특정 시/도인 경우
        return joint_region

    # 둘 다 애매하면 base_region 또는 joint_region, 그래도 없으면 전국
    if base_region:
        return base_region
    if joint_region:
        return joint_region

    return "전국"


def _extra_phones_by_region(region: str, ind_code: str) -> List[str]:
    """
    공종(0038,0039,0040,6202) + 지역에 따른 추가 수신번호 규칙.

    - 공종(0038,0039,0040,6202)이 전국/대구/경북 → REDACTED_PHONE
    - 공종(0038,0039,0040,6202)이 전국/충북   → REDACTED_PHONE, REDACTED_PHONE
    - 공종(0038,0039,0040,6202)이 전국/세종   → REDACTED_PHONE, REDACTED_PHONE

    여기서는 '실질 지역'(_effective_region) 결과를 region으로 받고,
    전국인 경우에는 '추가번호 없음'으로 두고, 엑셀에 있는 수신번호 + REDACTED_PHONE에만 의존.
    """

    if ind_code not in {"0038", "0039", "0040", "6202"}:
        return []

    # 지역별 추가 번호
    if region in {"대구", "경북"}:
        return ["REDACTED_PRIVATE_VALUE"]  # REDACTED_PHONE
    if region == "충북":
        return ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]  # REDACTED_PHONE, REDACTED_PHONE
    if region == "세종":
        return ["REDACTED_PRIVATE_VALUE", "REDACTED_PRIVATE_VALUE"]  # REDACTED_PHONE, REDACTED_PHONE

    # 전국(혹은 기타)은 여기서 별도 추가 없음
    return []


# ------------------------------------------------------
# 메시지 생성 (TB_0485 템플릿 대응)
# ------------------------------------------------------

def _build_message(row: Dict[str, Any]) -> Tuple[str, str]:
    """
    알리고 템플릿 TB_0485 에 완전히 맞춘 메시지 생성
    (템플릿이 요구하는 변수명/구조 그대로 구성해야 전송 성공)
    """

    bid_no = str(row.get("공고번호") or "").strip()
    bid_ord = str(row.get("차수") or "000").strip()
    title = str(row.get("공고명") or "").strip()

    # 입찰 마감일시
    close_dt = (
        row.get("입찰마감일시")
        or row.get("입찰마감일")
        or ""
    )
    close_dt = str(close_dt).strip()

    # 공동도급지역
    region = (
        row.get("jntcontrctDutyRgnNm1")
        or row.get("공동도급지역")
        or row.get("지역")
        or ""
    )
    region = str(region).strip()

    # 공동도급비율
    ratio = (
        row.get("rgnDutyJntcontrctRt")
        or row.get("공동도급비율")
        or ""
    )
    ratio = str(ratio).strip()

    # 추정금액
    amount = (
        row.get("presmptPrce")
        or row.get("추정금액_원")
        or row.get("추정금액")
        or ""
    )
    amount = str(amount).strip()

    # 템플릿 제목은 고정
    subject = "[세리공영]"

    # ★ TB_0485 템플릿 형식 그대로 맞춤
    message = (
        "[세리공영]\n\n"
        f"공고명 : {title}\n"
        f"입찰마감일시 :  {close_dt}\n"
        f"공동도급지역 : {region}\n"
        f"공동도급비율 : {ratio}\n"
        f"추정금액 : {amount}\n"
        f"공고번호 : {bid_no} - {bid_ord}"
    )

    return subject, message


# ------------------------------------------------------
# 데이터 발송
# ------------------------------------------------------

def send_all(rows: List[Dict[str, Any]]) -> None:
    log(f"[ALIMTALK] send_all rows = {len(rows)}")

    # 1) 전체에서 수신번호 정제 + 지역/공종 규칙 반영
    cleaned: List[Dict[str, Any]] = []
    for r in rows:
        base_phones = _clean_phone_field(r.get("수신번호"))

        # 실질 지역 & 공종코드
        eff_region = _effective_region(r)
        ind_code = _ind(r)

        # 지역/공종 규칙에 따른 추가 번호
        extra = _extra_phones_by_region(eff_region, ind_code)

        phones = base_phones + extra

        # 항상 REDACTED_PHONE 강제 포함 (사용자 요청)
        if "REDACTED_PRIVATE_VALUE" not in phones:
            phones.append("REDACTED_PRIVATE_VALUE")

        phones = sorted(set(phones))

        if phones:
            r["수신번호"] = ",".join(phones)
            cleaned.append(r)

    if not cleaned:
        log("[ALIMTALK] no phones → skip")
        return

    log(f"[ALIMTALK] 전화번호 있는 행 = {len(cleaned)}")

    # 2) 발송 로그 기반 중복 제거
    sent_keys = _load_sent_keys()
    to_send: List[Dict[str, Any]] = []

    for r in cleaned:
        k = _make_key(r)
        if k and k not in sent_keys:
            to_send.append(r)

    if not to_send:
        log("[ALIMTALK] no new rows (중복)")
        return

    log(f"[ALIMTALK] 발송할 신규 건수 = {len(to_send)}")

    # 3) TEST_SINGLE_MODE: 모든 발송을 한 번호로 모으는 옵션
    if TEST_SINGLE_MODE:
        for r in to_send:
            r["수신번호"] = TEST_SINGLE_PHONE

    # 4) 실제 발송
    log_recs: List[Dict[str, Any]] = []

    for r in to_send:
        bid_key = _make_key(r)
        phones = _clean_phone_field(r.get("수신번호"))

        subject, msg = _build_message(r)

        for ph in phones:
            ok = ALIGO.send_talk(ph, subject, msg)
            log(f"[ALIMTALK][SEND][{'OK' if ok else 'FAIL'}] {bid_key} → {ph}")

        log_recs.append(
            {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "key": bid_key,
                "bid_no": r.get("공고번호"),
                "bid_ord": r.get("차수") or "000",
                "region": _region(r),
                "ind": _ind(r),
                "phones": ",".join(phones),
                "title": _title(r),
            }
        )

    _append_sent_log(log_recs)
    log(f"[ALIMTALK] logged {len(log_recs)} rows → {SENT_LOG_FILE}")


# ------------------------------------------------------
# 발송 로그 로딩/쓰기
# ------------------------------------------------------

def _load_sent_keys() -> Set[str]:
    keys: Set[str] = set()
    p = Path(SENT_LOG_FILE)
    if not p.exists():
        return keys

    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                k = (row.get("key") or "").strip()
                if k:
                    keys.add(k)
    except Exception as e:
        log(f"[ALIMTALK][WARN] log read fail: {e}")
    return keys


def _append_sent_log(records: List[Dict[str, Any]]) -> None:
    if not records:
        return

    p = Path(SENT_LOG_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)

    is_new = not p.exists()
    fields = ["ts", "key", "bid_no", "bid_ord", "region", "ind", "phones", "title"]

    with p.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            w.writeheader()
        for r in records:
            w.writerow(r)


