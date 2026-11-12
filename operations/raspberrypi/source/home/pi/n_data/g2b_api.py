
import os, urllib.parse, requests



BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"



def _decode_service_key(raw: str) -> str:

    """SERVICE_KEY가 %로 이중 인코딩돼 들어와도 원문키로 복원"""

    if not raw: 

        return ""

    k = raw.strip()

    # 최대 2회까지 디코딩 시도 (예: %252B -> %2B -> +)

    for _ in range(2):

        if "%" in k:

            k = urllib.parse.unquote(k)

    # 최종적으로 % 문자가 남지 않는 원문키 기대

    return k



def _to_items(j):

    # 응답이 배열/객체 등 어떤 형태로 와도 리스트[dict]로 정규화

    if isinstance(j, list):

        return j

    if not isinstance(j, dict):

        return []

    resp = j.get("response") or {}

    body = resp.get("body") or {}

    items_node = body.get("items")

    if items_node is None:

        return []

    # body.items 가 { item: [...] } 또는 단일객체/리스트 등 다양

    if isinstance(items_node, dict) and "item" in items_node:

        items = items_node.get("item")

    else:

        items = items_node

    if items is None:

        return []

    if isinstance(items, dict):

        return [items]

    if isinstance(items, list):

        return items

    return []



def fetch(ind: str, beg: str, end: str, service_key: str = None, timeout: int = 20):

    """

    ind: '0040'/'0038'/'0039'/'6202'

    beg/end: 'YYYYMMDDHHMM'

    return: list[dict]

    """

    if service_key is None:

        service_key = os.environ.get("SERVICE_KEY", "")

    service_key = _decode_service_key(service_key)

    if not service_key:

        raise RuntimeError("SERVICE_KEY empty")



    params = {

        "serviceKey": service_key,   # 원문키(+,= 포함) → requests가 알아서 인코딩

        "inqryDiv": "1",

        "inqryBgnDt": beg,

        "inqryEndDt": end,

        "type": "json",

        "indstrytyClCode": ind,

    }

    r = requests.get(BASE, params=params, timeout=timeout)

    r.raise_for_status()

    return _to_items(r.json())

