
import os, sys, json, datetime as dt, urllib.parse, urllib.request

SRCH_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch"



# 환경변수 혹은 .env에서 SERVICE_KEY 로드 시도

SERVICE_KEY = os.getenv("SERVICE_KEY") or os.getenv("G2B_SERVICE_KEY") or ""

if not SERVICE_KEY:

    # .env 파일에서 잡아보기

    for p in ("/home/pi/seri_Alarm_Server/.env.prod", "/home/pi/n_data/.env", "/home/pi/.env"):

        if os.path.exists(p):

            for line in open(p, "r", encoding="utf-8", errors="ignore"):

                if "SERVICE_KEY" in line or "G2B_SERVICE_KEY" in line:

                    SERVICE_KEY = line.strip().split("=",1)[-1].strip().strip("'\"")

                    break

        if SERVICE_KEY: break



if not SERVICE_KEY:

    print("[ERR] SERVICE_KEY 없음. .env 혹은 환경변수에 SERVICE_KEY=... 를 지정하세요.")

    sys.exit(2)



# 기간: 어제~지금(분)

now = dt.datetime.now()

from_dt = (now - dt.timedelta(days=1)).strftime("%Y%m%d%H%M")

to_dt   = now.strftime("%Y%m%d%H%M")



inds = ["0040","0038","0039","6202"]

out_path = "/home/pi/n_data/probe_raw.jsonl"

open(out_path, "w").close()



def request(ind):

    params = {

        "serviceKey": SERVICE_KEY,  # 필요 시 2중 인코딩

        "inqryDiv": 1,

        "inqryBgnDt": from_dt,

        "inqryEndDt": to_dt,

        "type": "json",

        "indstrytyClCode": ind

    }

    # 공공데이터포털은 종종 key를 URL 인코딩 2번 요구함 → 둘 다 시도

    for double in (False, True):

        q = []

        for k,v in params.items():

            if k=="serviceKey" and double:

                v = urllib.parse.quote(v, safe="")  # 2중 인코딩

            q.append(f"{k}={urllib.parse.quote(str(v))}")

        url = SRCH_URL + "?" + "&".join(q)

        try:

            with urllib.request.urlopen(url, timeout=10) as r:

                raw = r.read().decode("utf-8", "ignore")

            data = json.loads(raw)

            return raw, data, url, ("double" if double else "single")

        except Exception as e:

            last_err = e

    raise last_err



def normalize_items(data):

    """

    응답 형태가

    - {"response":{"body":{"items":{"item":[...]}}}}

    - {"response":{"body":{"items":{"item":{...}}}}} (1건일 때 dict)

    - {"response":{"body":{"items":[]}}} (빈)

    등으로 제각각이라 안전 파서로 리스트 반환

    """

    try:

        resp = data.get("response") or {}

        body = (resp.get("body") or {})

        items = body.get("items")

        if items is None:

            return []

        # items 가 리스트면 평탄화

        if isinstance(items, list):

            # 공공데이터가 가끔 [{...}, {...}] 형태 그대로일 때

            return items

        # dict일 때

        if isinstance(items, dict):

            it = items.get("item")

            if it is None:

                return []

            if isinstance(it, list):

                return it

            return [it]  # 단건 dict

        return []

    except Exception:

        return []



for ind in inds:

    try:

        raw, data, url, mode = request(ind)

        rows = normalize_items(data)

        print(f"[OK] ind={ind} rows={len(rows)} mode={mode}")

        with open(out_path, "a", encoding="utf-8") as f:

            f.write(json.dumps({

                "ind": ind, "count": len(rows), "mode": mode, "url": url,

                "sample": rows[:2]

            }, ensure_ascii=False)+"\n")

    except Exception as e:

        print(f"[ERR] ind={ind}: {e.__class__.__name__} {e}")

        with open(out_path, "a", encoding="utf-8") as f:

            f.write(json.dumps({"ind": ind, "error": str(e)}, ensure_ascii=False)+"\n")



print(f"[DUMP] {out_path}")

