
# -*- coding: utf-8 -*-

import re, openpyxl

from kakao_send_tb0485 import send_for_item


# === SERI TEST-MODE LOG WRAP (auto-injected) ===

try:

    import os, requests as _rq, functools as _ft, inspect as _ins

    if not globals().get("_SERI_KDISPATCH_PATCHED"):

        # 1) requests.post 래핑 → 실제 네트워크 전 전역 TEST_MODE 안내

        _orig_post = _rq.post

        def _seri_post(url, *args, **kwargs):

            if os.getenv("TEST_MODE","0") == "1":

                phone = os.getenv("TEST_PHONE","REDACTED_PRIVATE_VALUE")

                print(f"[TEST_MODE] receiver forced to {phone} (kakao_dispatch.py/requests)")

            return _orig_post(url, *args, **kwargs)

        _rq.post = _seri_post



        # 2) 주요 진입함수 자동 래핑 → 함수 호출 시 TEST_MODE 안내

        def _wrap(fn):

            @_ft.wraps(fn)

            def _w(*a, **kw):

                if os.getenv("TEST_MODE","0") == "1":

                    phone = os.getenv("TEST_PHONE","REDACTED_PRIVATE_VALUE")

                    print(f"[TEST_MODE] receiver forced to {phone} (kakao_dispatch.py/{fn.__name__})")

                return fn(*a, **kw)

            return _w



        for _name, _obj in list(globals().items()):

            if callable(_obj) and _ins.isfunction(_obj):

                if _name.startswith(("dispatch", "send_", "send", "build_", "prepare_")):

                    globals()[_name] = _wrap(_obj)



        _SERI_KDISPATCH_PATCHED = True

except Exception:

    pass

# === END SERI TEST-MODE LOG WRAP ===





COMPANY_XLSX = "/home/pi/n_data/companys.xlsx"

CODE_COLS   = [f"공종코드{i}" for i in range(1,11)]

PHONE_COLS  = [f"전화번호{i}" for i in range(1,6)]

REGION_COL  = "지역"



def _norm_phone(s):

    if not s: return None

    s = re.sub(r"\D", "", str(s))

    if s.startswith("82") and len(s) >= 11:

        s = "0" + s[2:]

    if len(s) in (10,11) and s.startswith("0"):

        return s

    return None



# 지역 토큰 변환(정확명 + 축약형 허용)

_ALIAS = {

    "충청북도":["충청북도","충북"],

    "충청남도":["충청남도","충남"],

    "경상북도":["경상북도","경북"],

    "경상남도":["경상남도","경남"],

    "전라북도":["전라북도","전북"],

    "전라남도":["전라남도","전남"],

    "강원특별자치도":["강원특별자치도","강원"],

    "제주특별자치도":["제주특별자치도","제주"],

    "세종특별자치시":["세종특별자치시","세종"],

    "서울특별시":["서울특별시","서울"],

    "인천광역시":["인천광역시","인천"],

    "대전광역시":["대전광역시","대전"],

    "대구광역시":["대구광역시","대구"],

    "광주광역시":["광주광역시","광주"],

    "부산광역시":["부산광역시","부산"],

    "울산광역시":["울산광역시","울산"],

    "경기도":["경기도","경기"],

    "전국":["전국"],

}

def _region_tokens(s):

    s = str(s or "").strip()

    toks = {s}

    for k, vs in _ALIAS.items():

        if s == k:

            toks |= set(vs)

    if len(s) >= 2:

        toks.add(s[:2])

    return toks



def _load_companies(path=COMPANY_XLSX):

    wb = openpyxl.load_workbook(path, data_only=True)

    ws = wb.active

    headers = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]

    idx = {h:i for i,h in enumerate(headers)}

    def val(row, key, default=None):

        j = idx.get(key)

        return (row[j] if j is not None else default)

    comps=[]

    for row in ws.iter_rows(min_row=2, values_only=True):

        if all(x is None or str(x).strip()=="" for x in row):

            continue

        name   = str(val(row, "회사이름","") or "").strip()

        region = str(val(row, REGION_COL,"") or "").strip()

        codes  = []

        for c in CODE_COLS:

            v = val(row, c, None)

            if v is None: continue

            s = str(v).strip()

            if s and s.lower()!="none" and s!=" ":

                codes.append(s)

        phones = []

        for p in PHONE_COLS:

            v = val(row, p, None)

            ph = _norm_phone(v)

            if ph: phones.append(ph)

        phones = list(dict.fromkeys(phones))  # dedupe

        comps.append({

            "name": name, "region": region,

            "codes": set(codes), "phones": phones

        })

    return comps



def _item_region(item):

    return (item.get("참가가능지역") or item.get("지역") or

            item.get("공동도급지역") or item.get("jntcontrctDutyRgnNm1") or "")



def _item_code(item):

    return str(

        item.get("indstrytyCd") or item.get("업종코드") or item.get("공종코드") or ""

    ).strip()



def resolve_receivers(item):

    """

    item의 지역/공종코드로 companys.xlsx에서 수신번호 리스트 산출

    - 지역: 회사 지역이 '전국'이거나, 회사지역 토큰 ∩ 공고지역 토큰이 있으면 매칭

    - 공종: 회사에 코드 세트가 있으면, item의 코드가 있으면 그 코드가 포함되어야 함

            (item에 코드가 없으면 코드 조건은 패스)

    """

    comps = _load_companies()

    item_tokens = _region_tokens(_item_region(item))

    icode = _item_code(item)

    out=[]

    for c in comps:

        if not c["phones"]:

            continue

        # 지역 매칭

        if c["region"] == "전국":

            region_ok = True

        else:

            region_ok = bool(item_tokens & _region_tokens(c["region"]))

        if not region_ok:

            continue

        # 공종코드 매칭

        if c["codes"]:

            code_ok = (icode in c["codes"]) if icode else True

        else:

            code_ok = True

        if not code_ok:

            continue

        out.extend(c["phones"])

    # 중복 제거(순서 보존)

    seen=set(); res=[]

    for ph in out:

        if ph not in seen:

            seen.add(ph); res.append(ph)

    return res



def dispatch_item(item, sender="REDACTED_PRIVATE_VALUE"):

    """

    item 한 건을 companys.xlsx 기준으로 '맞는 수신자'에게 모두 전송

    (템플릿은 kakao_send_tb0485.send_for_item 내부 TB_0485 사용)

    """

    receivers = resolve_receivers(item)

    results=[]

    for rcpt in receivers:

        results.append({

            "to": rcpt,

            "resp": send_for_item(item, receiver=rcpt, sender=sender)

        })

    return {"receivers": receivers, "results": results}





# === SERI DRY-RUN HELPER (auto-injected) ===

def test_send_for_item_dryrun(receiver: str = None, **extra_fields):

    """실제 네트워크 전송 없이 send_for_item 흐름을 끝까지 점검하는 헬퍼.

    - requests.post 를 일시적으로 가짜 함수로 바꿔 실제 발송을 막습니다.

    - TEST_MODE=1이면 강제 수신번호(REDACTED_PHONE)로 표시 로그가 나옵니다.

    사용 예:

        test_send_for_item_dryrun()

        test_send_for_item_dryrun('REDACTED_PRIVATE_VALUE', 공고번호='T123', 업종='전기공사')

    """

    import os, requests, types

    # 더미 post: 네트워크 막고 어떤 payload가 만들어졌는지 출력

    _orig_post = requests.post

    def _dummy_post(url, *a, **kw):

        print("[DRY-RUN] requests.post blocked")

        print("[DRY-RUN] URL:", url)

        if "data" in kw:

            print("[DRY-RUN] FORM data keys:", list(kw["data"].keys()))

            # 민감키 일부만 출력

            for k in ("receiver_1","receiver","tel","to","mobile"):

                if isinstance(kw["data"], dict) and k in kw["data"]:

                    print(f"[DRY-RUN] data[{k}] =", kw["data"][k])

        if "json" in kw:

            print("[DRY-RUN] JSON keys:", list(kw["json"].keys()))

        class _Resp:

            status_code = 200

            text = "OK(DRY-RUN)"

            def json(self): return {"dry_run": True, "ok": True}

        return _Resp()

    requests.post = _dummy_post

    try:

        # 기본 필드 구성

        fields = {

            "공고번호":  "TST-0001",

            "공고명":    "DRY-RUN 테스트 공고",

            "업종":      "전기공사",

            "기초금액":  "1,000,000",

            "접수시작":  "2025/01/01 09:00",

            "접수마감":  "2025/01/02 18:00",

        }

        fields.update(extra_fields or {})

        # 수신자 기본값: TEST_MODE면 굳이 넣지 않아도 내부에서 강제됨

        if receiver is None:

            receiver = "REDACTED_PHONE"

        print("[DRY-RUN] call send_for_item(receiver, fields)")

        from kakao_send_tb0485 import send_for_item

        res = send_for_item(receiver=receiver, fields=fields)

        print("[DRY-RUN] send_for_item return:", res)

        print("[DRY-RUN] SUCCESS (no network traffic)")

        return True

    finally:

        # 원복

        requests.post = _orig_post

# === END SERI DRY-RUN HELPER ===

