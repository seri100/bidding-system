"""G2B 2026-11-03 API migration. Python 3.7 compatible."""
import re
from collections import defaultdict
BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService02/"
OPS = (
 'REDACTED_PRIVATE_VALUE',
 'REDACTED_PRIVATE_VALUE',
 'REDACTED_PRIVATE_VALUE',
 'REDACTED_PRIVATE_VALUE',
)
def identity(row):
 return (str(row.get("bidNtceNo", "")).strip(),
         str(row.get("bidNtceOrd", "000")).strip().zfill(3))
def migrate_url(url):
 if re.match(r"https?://apis\.data\.go\.kr/1230000/(?:ad/)?BidPublicInfoService(?:02)?/", url):
  op = url.rsplit("/", 1)[-1]
  return BASE + (op if op.endswith("02") else op + "02")
 return url
def merge(row, groups):
 key = identity(row)
 for index, grouped in enumerate(groups):
  details = grouped.get(key, [])
  row["_api02_" + OPS[index]] = details
  for pos, item in enumerate(details, 1):
   try: seq = int(item.get("sno", pos))
   except (ValueError, TypeError): seq = pos
   if index == 0:
    name = item.get("JntcontrctDutyRgnNm") or item.get("jntcontrctDutyRgnNm")
    if name and 1 <= seq <= 3: row["jntcontrctDutyRgnNm%d" % seq] = name
    if item.get("rgnDutyJntcontrctRt") not in (None, ""):
     row["rgnDutyJntcontrctRt"] = item["rgnDutyJntcontrctRt"]
   elif index == 1:
    name = item.get("IncntvRgnNm") or item.get("incntvRgnNm")
    if name and 1 <= seq <= 4: row["incntvRgnNm%d" % seq] = name
   elif index == 2 and 1 <= seq <= 10:
    for field in ("subsiCnsttyCd", "subsiCnsttyNm", "subsiCnsttyIndstrytyEvlRt"):
     if item.get(field) not in (None, ""): row[field + str(seq)] = item[field]
   elif index == 3:
    url = item.get("atchFileUrl")
    if not url: continue
    slots = range(1, 11)
    if any(row.get("ntceSpecDocUrl%d" % n) == url for n in slots): continue
    slot = next((n for n in slots if not row.get("ntceSpecDocUrl%d" % n)), None)
    if slot is not None:
     row["ntceSpecDocUrl%d" % slot] = url
     row["ntceSpecFileNm%d" % slot] = item.get("atchFileNm", "")
 return row
def install(request, log):
 cache = {}
 def supplemental(params):
  query = {k: params[k] for k in ("serviceKey", "inqryDiv", "inqryBgnDt", "inqryEndDt",
           "bidNtceNo", "bidNtceOrd", "type") if k in params}
  token = tuple(sorted((k, str(v)) for k,v in query.items() if k != "serviceKey"))
  if token in cache: return cache[token]
  groups = []
  for op in OPS:
   grouped = defaultdict(list)
   p = dict(query, numOfRows=999)
   if op == OPS[3]: p["bsnsDivCd"] = "3"
   for page in range(1, 201):
    p["pageNo"] = page
    items = request(BASE + op, p)
    for item in items: grouped[identity(item)].append(item)
    if len(items) < 999: break
   else: raise RuntimeError("API02 supplemental page limit: " + op)
   log("[API02][DETAIL] %s rows=%d" % (op, sum(map(len, grouped.values()))))
   groups.append(grouped)
  cache[token] = groups
  return groups
 def wrapped(url, params, timeout=25):
  url = migrate_url(url)
  items = request(url, params, timeout=timeout)
  op = url.rsplit("/", 1)[-1]
  if items and op in ('REDACTED_PRIVATE_VALUE', 'REDACTED_PRIVATE_VALUE'):
   groups = supplemental(params)
   for row in items: merge(row, groups)
  return items
 return wrapped
