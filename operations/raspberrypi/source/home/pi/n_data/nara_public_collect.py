
# -*- coding: utf-8 -*-

"""

조달청 입찰공고(시설공사) 공용 수집 모듈

- getBidPblancListInfoCnstwkPPSSrch (공고 목록)

- getBidPblancListInfoPrtcptPsblRgn (참가가능지역)

을 사용해, 지정한 기간/업종의 공고를 가져온다.



PC에서 사용하던 코드와 동일한 방식으로 API를 호출하도록 통일.

"""



import datetime

from typing import List, Dict, Any, Optional



import requests

URI_BID_11 = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"

URI_BID_16 = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn"





# -------------------- 공통 HTTP 호출 --------------------
def _req_url(uri: str, params: Dict[str, Any], api_key: str, timeout: int = 30) -> Optional[Dict[str, Any]]:

    """

    조달청 공공데이터포털 JSON 호출 공통 함수 (serviceKey를 params로 넣는 정석 버전)



    - URL에 직접 ?serviceKey=REDACTED_PRIVATE_VALUE 붙이지 않고,

      params["serviceKey"] = api_key 로 전달 (requests가 알아서 URL 인코딩 처리)

    - 최대 5회 재시도, resultCode == '00' 인 경우만 정상으로 간주.

    - 디버그용으로 status / content-type / 응답 앞부분을 출력.

    """

    # 원래 params 복사해서 serviceKey 추가

    params_with_key = dict(params)

    params_with_key["serviceKey"] = api_key  # ← 여기서 소문자 serviceKey 사용



    for retry in range(5):

        try:

            resp = requests.get(uri, params=params_with_key, timeout=timeout)

        except Exception as e:

            print(f"[REQ] {uri} 호출 실패 (retry={retry}): {e}")

            continue



        status = resp.status_code

        ctype = resp.headers.get("Content-Type", "")

        text_head = resp.text[:300].replace("\n", " ").replace("\r", " ")



        # 우선 JSON 파싱 시도

        try:

            data = resp.json()

        except Exception:

            print(

                f"[REQ][DEBUG] {uri} JSON 파싱 실패 (retry={retry}) "

                f"status={status}, ctype={ctype}, body_head={text_head!r}"

            )

            continue



        # 응답 헤더 확인

        try:

            header = data["response"]["header"]

            code = header.get("resultCode", "")

        except Exception:

            print(

                f"[REQ][DEBUG] {uri} 응답 구조 이상 (retry={retry}) "

                f"status={status}, body_head={text_head!r}"

            )

            continue



        if code == "00":

            return data

        else:

            print(

                f"[REQ][DEBUG] {uri} resultCode={code} (retry={retry}) "

                f"status={status}, body_head={text_head!r}"

            )



    return None

# -------------------- 참가가능지역 조회 --------------------





def _fetch_prtcpt_region(api_key: str, bid_no: str, bid_ord: str) -> str:

    """

    getBidPblancListInfoPrtcptPsblRgn 로부터 참가가능지역 문자열(prtcptPsblRgnNm)을 받아온다.

    - 실패 시 빈 문자열 반환.

    """

    params = {

        "numOfRows": 10,

        "pageNo": 1,

        "type": "json",

        "inqryDiv": "2",  # 공고번호/차수로 조회

        "bidNtceNo": bid_no,

        "bidNtceOrd": bid_ord,

    }

    data = _req_url(URI_BID_16, params, api_key)

    if not data:

        return ""



    try:

        body = data["response"]["body"]

        items = body.get("items", [])

        if not items:

            return ""

        # 여러 건이 있어도 보통 첫 건에 전체 지역 문자열이 들어있음

        return items[0].get("prtcptPsblRgnNm", "") or ""

    except Exception:

        return ""





# -------------------- 공고 목록 조회 (기간 + 업종 코드) --------------------





def collect_bids_range(

    api_key: str,

    indstry_codes: List[str],

    start_dt: datetime.datetime,

    end_dt: datetime.datetime,

    min_budget: int = 0,

) -> List[Dict[str, Any]]:

    """

    주어진 기간(start_dt ~ end_dt)와 업종코드 리스트에 대해

    getBidPblancListInfoCnstwkPPSSrch 를 조회하고,

    필터(취소/국방/T시작 공고/최소 예산)를 거친 후 공고 리스트를 반환한다.



    반환되는 각 dict에는 PC 코드와 유사한 필드:

      - bidNtceNo, bidNtceOrd, bidNtceNm, bidNtceDt, bidBeginDt, bidClseDt

      - bdgtAmt(정수), indstrytyCd, bidNtceUrl

      - rgnDutyJntcontrctYn, jntcontrctDutyRgnNm1~3, rgnDutyJntcontrctRt

      - prtcptPsblRgnNm (필요 시 참가가능지역까지 채워서 돌려줌)

    를 포함한다.

    """

    begin_str = start_dt.strftime("%Y%m%d%H%M")

    end_str = end_dt.strftime("%Y%m%d%H%M")



    print(f"[NARA-COLLECT] 기간 {begin_str} ~ {end_str}, 업종={indstry_codes}")



    all_rows: List[Dict[str, Any]] = []



    for code in indstry_codes:

        page = 1

        while True:

            params = {

                "numOfRows": 100,

                "pageNo": page,

                "type": "json",

                "inqryDiv": "1",  # 기간 조회

                "inqryBgnDt": begin_str,

                "inqryEndDt": end_str,

                "indstrytyCd": code,

            }

            data = _req_url(URI_BID_11, params, api_key)

            if not data:

                print(f"[NARA-COLLECT] ind={code} page={page} → 응답 없음/에러")

                break



            try:

                body = data["response"]["body"]

                items = body.get("items", [])

                total_count = int(body.get("totalCount", len(items)))

            except Exception:

                print(f"[NARA-COLLECT] ind={code} page={page} → body 파싱 오류")

                break



            print(f"[NARA-COLLECT] ind={code} page={page} count={len(items)} total={total_count}")



            if not items:

                break



            for item in items:

                bid_no = item.get("bidNtceNo", "")

                bid_ord = item.get("bidNtceOrd", "")



                # T로 시작하는 테스트성 공고, 취소공고, 국방 관련 제외 (PC 코드와 동일)

                if bid_no.startswith("T"):

                    continue

                if "취소" in str(item.get("ntceKindNm", "")):

                    continue

                if "국방" in str(item.get("opengPlce", "")):

                    continue



                bdgt_raw = item.get("bdgtAmt") or ""

                try:

                    bdgt_amt = int(bdgt_raw)

                except Exception:

                    bdgt_amt = 0



                if bdgt_amt < min_budget:

                    continue



                row: Dict[str, Any] = {}



                # 기본 필드

                row["bidNtceNo"] = bid_no

                row["bidNtceOrd"] = bid_ord

                row["bidNtceNm"] = item.get("bidNtceNm", "")
                row["sucsfbidMthdNm"] = (item.get("sucsfbidMthdNm") or "")
                row.setdefault("낙찰방법세부기준", row.get("sucsfbidMthdNm", ""))

                row["bidNtceDt"] = item.get("bidNtceDt", "")

                row["bidBeginDt"] = item.get("bidBeginDt", "")

                row["bidClseDt"] = item.get("bidClseDt", "")

                row["ntceKindNm"] = item.get("ntceKindNm", "")

                row["opengPlce"] = item.get("opengPlce", "")

                row["bdgtAmt"] = bdgt_amt

                row["indstrytyCd"] = code

                row["bidNtceUrl"] = item.get("bidNtceUrl", "")



                # 공동도급 관련 필드

                row["rgnDutyJntcontrctYn"] = item.get("rgnDutyJntcontrctYn", "")

                row["jntcontrctDutyRgnNm1"] = item.get("jntcontrctDutyRgnNm1", "")

                row["jntcontrctDutyRgnNm2"] = item.get("jntcontrctDutyRgnNm2", "")

                row["jntcontrctDutyRgnNm3"] = item.get("jntcontrctDutyRgnNm3", "")

                row["rgnDutyJntcontrctRt"] = item.get("rgnDutyJntcontrctRt", "")



                # 참가가능지역(필요시)

                row["prtcptPsblRgnNm"] = ""



                # main_send 쪽에서 참가가능지역 우선으로 보려면

                # 여기서 미리 호출해 채워둬도 되고, region_filter 쪽에서 필요시 호출해도 된다.

                # 일단 최소한 한 번 채워두는 버전:

                if row["rgnDutyJntcontrctYn"] != "Y":

                    prgn = _fetch_prtcpt_region(api_key, bid_no, bid_ord)

                    row["prtcptPsblRgnNm"] = prgn



                all_rows.append(row)



            # 페이지네이션: numOfRows=100 기준으로 totalCount를 보고 더 가져올지 결정

            if len(all_rows) >= total_count:

                break

            page += 1



    print(f"[NARA-COLLECT] 총 수집 건수 = {len(all_rows)}")

    return all_rows






# ============================================================

# PATCH: enrich sucsfbidMthdNm (낙찰방법세부기준) for construction

# - Source: BidPublicInfoService/getBidPblancListInfoCnstwk (bidNtceNo supported)

# - Adds raw["sucsfbidMthdNm"] when missing

# ============================================================



def enrich_cnstwk_sucs_method(service_key: str, rows: list, timeout: int = 20) -> int:

    """

    rows: collect_bids_range 결과(list[dict])를 받아,

          각 원문 dict에 sucsfbidMthdNm 가 없으면 공고번호로 조회하여 주입.

    return: 주입된 건수

    """

    try:

        import requests

    except Exception as e:

        # requests 없으면 보강 불가

        return 0



    if not rows:

        return 0



    def _safe_str(v):

        if v is None:

            return ""

        return str(v).strip()



    # 공고번호 유니크

    bid_nos = []

    seen = set()

    for r in rows:

        if not isinstance(r, dict):

            continue

        if _safe_str(r.get("sucsfbidMthdNm")):

            continue

        bid_no = _safe_str(r.get("bidNtceNo"))

        if not bid_no:

            continue

        if bid_no in seen:

            continue

        seen.add(bid_no)

        bid_nos.append(bid_no)



    if not bid_nos:

        return 0



    url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"



    # 조회 캐시

    cache = {}



    def _fetch_one(bid_no: str) -> str:

        if bid_no in cache:

            return cache[bid_no]

        params = {

            "serviceKey": service_key,

            "pageNo": 1,

            "numOfRows": 10,

            "inqryDiv": 1,

            "bidNtceNo": bid_no,

            "type": "json",

        }

        try:

            resp = requests.get(url, params=params, timeout=timeout)

            resp.raise_for_status()

            js = resp.json()

        except Exception:

            cache[bid_no] = ""

            return ""



        # 응답 구조는 portal/버전에 따라 약간 다를 수 있어 방어적으로 탐색

        items = None

        try:

            body = js.get("response", {}).get("body", {})

            items = body.get("items")

            if isinstance(items, dict):

                items = items.get("item")

        except Exception:

            items = None



        if items is None:

            cache[bid_no] = ""

            return ""



        if isinstance(items, dict):

            items = [items]



        val = ""

        if isinstance(items, list) and items:

            # bidNtceNo 일치하는 것 우선

            for it in items:

                if not isinstance(it, dict):

                    continue

                if _safe_str(it.get("bidNtceNo")) == bid_no:

                    v = _safe_str(it.get("sucsfbidMthdNm"))

                    if v:

                        val = v

                        break

            if not val:

                # fallback: 첫 item

                it = items[0]

                if isinstance(it, dict):

                    val = _safe_str(it.get("sucsfbidMthdNm"))



        cache[bid_no] = val

        return val



    injected = 0

    for r in rows:

        if not isinstance(r, dict):

            continue

        if _safe_str(r.get("sucsfbidMthdNm")):

            continue

        bid_no = _safe_str(r.get("bidNtceNo"))

        if not bid_no:

            continue

        v = _fetch_one(bid_no)

        if v:

            r["sucsfbidMthdNm"] = v

            injected += 1



    return injected



# ===================== END PATCH =============================

