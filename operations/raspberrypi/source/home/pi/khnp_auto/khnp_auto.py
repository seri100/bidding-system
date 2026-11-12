#!/usr/bin/env python3
from __future__ import print_function
import argparse, json, logging, re, sqlite3, subprocess, sys, zipfile
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import requests
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BASE = Path(__file__).resolve().parent
BASE_URL = "https://ebiz.khnp.co.kr"
LOG = logging.getLogger("khnp-auto")

class TableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self); self.rows=[]; self.row=None; self.cell=None; self.cell_tag=None
    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.row=[]
        elif tag in ("th","td") and self.row is not None: self.cell=[]; self.cell_tag=tag
        elif tag == "br" and self.cell is not None: self.cell.append(" ")
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("th","td") and self.cell is not None:
            self.row.append((self.cell_tag,re.sub(r"\s+"," ","".join(self.cell)).strip())); self.cell=None; self.cell_tag=None
        elif tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row=None

def cfg():
    with open(str(BASE/"config.json"),encoding="utf-8") as f: return json.load(f)
def num(v):
    m=re.search(r"-?[\d,]+(?:\.\d+)?",str(v or "")); return int(float(m.group(0).replace(",",""))) if m else 0
def parse_detail(html, seed):
    p=TableParser(); p.feed(html); f={}
    for row in p.rows:
        for i,(tag,label) in enumerate(row):
            if tag!="th" or not label: continue
            vals=[]
            for nt,v in row[i+1:]:
                if nt=="th": break
                if v: vals.append(v)
            if vals: f[label]=" ".join(vals)
    nr=f.get("공고번호 / 차수",seed.get("rfx_no","")); parts=[x.strip() for x in re.split(r"/",nr,maxsplit=1)]
    submit=f.get("입찰서 제출일시",""); dates=re.findall(r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}",submit)
    region=f.get("지역(광역)제한",""); national=(not region or "제한없음" in region or region=="전국")
    attachments=[]
    for file_id,name in re.findall(r"downFn\('([^']+)'\)[^>]*>.*?<a[^>]*>(.*?)</a>",html,re.I|re.S):
        name=re.sub(r"<[^>]+>","",unescape(name)); name=re.sub(r"\s+"," ",name).strip()
        attachments.append({"id":file_id,"name":name})
    return {"rfx_id":seed.get("rfx_id",""),"bid_no":parts[0] or seed.get("rfx_no",""),"revision":(parts[1] if len(parts)>1 else "0").zfill(3),
      "title":f.get("공고명",seed.get("rfx_tit","")),"category":f.get("입찰구분",seed.get("item_typ","")),
      "posted_at":f.get("입찰공고일시","").replace("/","-"),"open_at":(dates[0].replace("/","-")+":00") if dates else "",
      "deadline":(dates[-1].replace("/","-")+":00") if dates else "","estimated_price":num(f.get("추정가격")),
      "base_amount":num(f.get("예비가격기초금액")),"net_cost":num(f.get("예비가격기초금액 중 순공사원가")),
      "a_value":num(f.get("가격점수제외금액(A)")),"region":"전국" if national else region,"is_national":national,
      "trade":f.get("공사업종요건",""),"specialty":f.get("주력분야",""),"joint_allowed":f.get("공동수급체 허용여부",""),
      "attachments":attachments,"detail_url":"%s/getTmpView.do?type=spbidnoti&loadId=%s"%(BASE_URL,seed.get("rfx_id",""))}

class Client(object):
    def __init__(self,verify): self.s=requests.Session(); self.s.headers.update({"User-Agent":"Mozilla/5.0"}); self.verify=verify; self.token=None
    def start(self):
        r=self.s.get(BASE_URL+"/login.do",timeout=30,verify=self.verify); r.raise_for_status(); m=re.search(r'name="_csrf" content="([^"]+)"',r.text)
        if not m: raise RuntimeError("CSRF 토큰을 찾지 못했습니다")
        self.token=m.group(1)
    def latest(self):
        h={"X-CSRF-TOKEN":self.token,"X-Requested-With":"XMLHttpRequest","Origin":BASE_URL,"Referer":BASE_URL+"/login.do","Content-Type":"application/json;charset=UTF-8","Accept":"application/json"}
        r=self.s.post(BASE_URL+"/findSpBidNotiListByNoSession.do",data="{}",headers=h,timeout=30,verify=self.verify)
        if r.status_code==403: self.start(); h["X-CSRF-TOKEN"]=self.token; r=self.s.post(BASE_URL+"/findSpBidNotiListByNoSession.do",data="{}",headers=h,timeout=30,verify=self.verify)
        r.raise_for_status(); return r.json()
    def notices(self,days_back=7,page_size=100):
        """공개 입찰공고 목록을 최근 기간 기준으로 끝 페이지까지 조회."""
        h={"X-CSRF-TOKEN":self.token,"X-Requested-With":"XMLHttpRequest","Origin":BASE_URL,
           "Referer":BASE_URL+"/ui/sp/publicpro/bid/em-sp-bid-list.html",
           "Content-Type":"application/json;charset=UTF-8","Accept":"application/json"}
        today=datetime.now().date()
        # KHNP 검색조건은 KST 자정을 UTC 문자열로 전달한다.
        start_day=today-timedelta(days=max(1,int(days_back)))
        end_day=today+timedelta(days=1)
        def utc_text(day):
            dt=datetime(day.year,day.month,day.day)-timedelta(hours=9)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        url=BASE_URL+"/ui/sp/publicpro/bid/findListBidVdByNSMDI.do"
        all_rows=[]; seen=set(); page=1
        while True:
            payload={"from_noti_dt":utc_text(start_day),"to_noti_dt":utc_text(end_day),
                     "rfx_no":"","rfx_nos":[],"timezone":"9",
                     "page":{"manualQuery":False,"page":page,"size":page_size,
                             "start":((page-1)*page_size)+1,"end":page*page_size}}
            r=self.s.post(url,json=payload,headers=h,timeout=60,verify=self.verify)
            if r.status_code==403:
                self.start(); h["X-CSRF-TOKEN"]=self.token
                r=self.s.post(url,json=payload,headers=h,timeout=60,verify=self.verify)
            r.raise_for_status()
            body=r.json(); rows=body.get("content",[]) if isinstance(body,dict) else body
            if not isinstance(rows,list):
                raise RuntimeError("KHNP 목록 응답 형식 변경")
            before=len(seen)
            for row in rows:
                key=(str(row.get("rfx_id","")),str(row.get("rfx_rev",row.get("bid_rev",""))))
                if key not in seen:
                    seen.add(key); all_rows.append(row)
            if len(rows)<page_size or len(seen)==before: break
            page+=1
            if page>100: raise RuntimeError("KHNP 목록 페이지가 100쪽을 초과했습니다")
        return all_rows,start_day,end_day
    def detail(self,rfx_id):
        r=self.s.get(BASE_URL+"/getTmpView.do",params={"type":"spbidnoti","loadId":rfx_id},headers={"Referer":BASE_URL+"/login.do"},timeout=30,verify=self.verify); r.raise_for_status()
        if "공고번호 / 차수" not in r.text: raise RuntimeError("상세공고 형식 변경: "+rfx_id)
        return r.text

def classify(row):
    t=" ".join((row["title"],row["trade"],row["specialty"]))
    if "전문소방" in t: return "0040","전문소방시설공사업"
    if "소방" in t and "기계" in t: return "0038","일반소방시설공사업(기계)"
    if "소방" in t and "전기" in t: return "0039","일반소방시설공사업(전기)"
    if any(x in t for x in ("소방시설","소방설비")): return "0040","전문소방시설공사업"
    if "소방" in t: return "0040","전문소방시설공사업"
    if any(x in t for x in ("기계설비공사업","기계가스설비공사업","기계설비")): return "6202","기계설비공사업"
    return "",""
def eligible(row,c):
    if "공사" not in row["category"]: return False,"공사 아님"
    row["industry_code"],row["industry_name"]=classify(row)
    if not row["industry_code"]: return False,"대상 면허 아님"
    amount=row["estimated_price"] or row["base_amount"]
    if amount<int(c["min_amount"]): return False,"3천만원 미만 또는 금액 미확인"
    # 다른 기관과 동일하게 10억원 이상은 지역제한과 무관하게 전국 수신 대상으로 분기한다.
    if amount>=1000000000: row["is_national"]=True
    return True,"대상"

def _safe_name(name):
    return re.sub(r'[\\/:*?"<>|]+',"_",name).strip() or "입찰공고문"

def _posted_day(row):
    m=re.match(r"(\d{4})-(\d{2})-(\d{2})",str(row.get("posted_at", "")))
    return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3))) if m else datetime.now()

def enrich_notice_doc(cl,row,c):
    """알림 대상 공고의 첨부파일 전체를 저장하고 공고문 핵심 조건을 추출."""
    day=_posted_day(row)
    root=Path(c["output_root"])/("%04d년"%day.year)/("%02d월"%day.month)/("%02d일"%day.day)/"첨부파일"/(row["bid_no"]+"-"+row["revision"])
    root.mkdir(parents=True,exist_ok=True)
    saved=[]
    for index,att in enumerate(row.get("attachments",[]),1):
        name=_safe_name(att["name"])
        file_path=root/name
        if file_path.exists() and file_path.stat().st_size>0:
            saved.append(file_path)
            LOG.info("[ATTACH][EXISTS] %s %s bytes=%d",row["bid_no"],file_path.name,file_path.stat().st_size)
            continue
        r=cl.s.get(BASE_URL+"/download/groupwareLink.do",params={"id":att["id"]},headers={"Referer":row["detail_url"]},timeout=120,verify=cl.verify)
        r.raise_for_status()
        if not r.content: raise RuntimeError("첨부파일 다운로드 내용 없음: "+att["name"])
        file_path.write_bytes(r.content); saved.append(file_path)
        LOG.info("[ATTACH][OK] %s %s bytes=%d",row["bid_no"],file_path.name,len(r.content))
    row["attachment_dir"]=str(root)
    row["attachment_count"]=len(saved)
    candidates=[p for p in saved if "입찰공고문" in p.name and p.suffix.lower() in (".hwp",".hwpx")]
    if not candidates: return row
    file_path=candidates[0]
    text=""
    if file_path.suffix.lower()==".hwp":
        cmd=["/home/pi/.local/bin/hwp5txt",str(file_path)]
        out=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=120)
        if out.returncode!=0: raise RuntimeError("hwp5txt 실패: "+out.stderr[-500:])
        text=out.stdout
    else:
        chunks=[]
        with zipfile.ZipFile(str(file_path)) as zf:
            for name in sorted(zf.namelist()):
                if name.lower().endswith(".xml"):
                    raw=zf.read(name).decode("utf-8","ignore")
                    chunks.append(re.sub(r"<[^>]+>"," ",raw))
        text=unescape("\n".join(chunks))
    text=re.sub(r"[ \t]+"," ",text)
    txt_path=file_path.with_suffix(file_path.suffix+".txt"); txt_path.write_text(text,encoding="utf-8")
    row["notice_file"]=str(file_path)
    row["joint_region"]=""
    m=re.search(r'[“\"]\s*([^”\"]+?)\s*[”\"]에\s*두지\s*않은\s*자는\s*반드시',text,re.S)
    if m: row["joint_region"]=re.sub(r"\s+"," ",m.group(1)).strip()
    row["joint_ratio"]=""
    m=re.search(r"지역업체\s*참여지분(?:은|율은)?\s*(\d+(?:\.\d+)?)\s*%\s*이상",text)
    if m: row["joint_ratio"]=m.group(1)+"% 이상"
    row["member_min_ratio"]=""
    m=re.search(r"구성원별\s*최소\s*지분율(?:을|은)?\s*(\d+(?:\.\d+)?)\s*%\s*이상",text)
    if m: row["member_min_ratio"]=m.group(1)+"% 이상"
    row["joint_method"]="공동이행" if "공동이행방식" in text else ""
    row["member_count"]=""
    m=re.search(r"구성원수[^\n]{0,100}?(\d+)\s*개사\s*이내",text)
    if m: row["member_count"]=m.group(1)+"개사 이내"
    return row
def main_module():

    return None



def receivers(row, mod=None):

    scope = "전국" if row["is_national"] else "지역"

    bridge = {

        "공고업종코드": row["industry_code"],

        "공고업종명": row["industry_name"],

        "scope": scope,

        "전국여부": scope,

        "대표지역": row["region"],

        "local_region": "" if row["is_national"] else row["region"],

        "지역제한": row["region"],

        "공동도급지역": row["region"]

    }



    helper = (

        "import json,sys;"

        "sys.path.insert(0,'/home/pi/n_data');"

        "import main_send;"

        "row=json.loads(sys.argv[1]);"

        "print('KHNP_ROUTE_JSON='+json.dumps(main_send.decide_receivers(row) or []))"

    )



    result = subprocess.run(

        ["/usr/bin/python3", "-c", helper, json.dumps(bridge, ensure_ascii=False)],

        stdout=subprocess.PIPE,

        stderr=subprocess.PIPE,

        universal_newlines=True,

        timeout=60

    )



    if result.returncode != 0:

        raise RuntimeError(

            "기존 수신자 분기 호출 실패: " + result.stderr[-1000:]

        )



    for line in reversed(result.stdout.splitlines()):

        if line.startswith("KHNP_ROUTE_JSON="):

            return json.loads(line.split("=", 1)[1])



    raise RuntimeError(

        "기존 수신자 분기 결과 없음: " + result.stdout[-1000:]

    )


class State(object):
    def __init__(self):
        p=BASE/"state"/"khnp.sqlite3"; p.parent.mkdir(parents=True,exist_ok=True); self.db=sqlite3.connect(str(p)); self.db.execute("CREATE TABLE IF NOT EXISTS sent(send_key TEXT PRIMARY KEY,sent_at TEXT,title TEXT)"); self.db.commit()
    def has(self,key,phone): return self.db.execute("SELECT 1 FROM sent WHERE send_key=?",(key+"|"+re.sub(r"\D","",phone),)).fetchone() is not None
    def mark(self,key,phone,title): self.db.execute("INSERT OR REPLACE INTO sent VALUES(?,?,?)",(key+"|"+re.sub(r"\D","",phone),datetime.now().isoformat(),title)); self.db.commit()

def _save_day(rows,c,n):
    root=Path(c["output_root"])/("%04d년"%n.year)/("%02d월"%n.month)/("%02d일"%n.day); root.mkdir(parents=True,exist_ok=True); path=root/("KHNP_공고정보_%s.xlsx"%n.strftime("%Y%m%d"))
    heads=["공고번호","차수","공고명","업종코드","공사업종요건","주력분야","지역","수신범위","추정가격","기초금액","순공사원가","A값","공고일시","입찰개시","입찰마감","공동수급","공동도급지역","공동도급비율","공동도급방식","구성원최소지분율","구성원수","수신자수","상세URL","공고문파일","첨부파일폴더","첨부파일수","수집시각"]
    wb=load_workbook(str(path)) if path.exists() else Workbook(); ws=wb.active; ws.title="공고정보"
    if ws.max_row>=2 and ws.cell(1,1).value is None and ws.cell(2,1).value=="공고번호": ws.delete_rows(1,1)
    if ws.max_row==1 and ws.cell(1,1).value is None:
        ws.delete_rows(1,1); ws.append(heads); ws.freeze_panes="A2"; ws.auto_filter.ref="A1:AA1"
        for c0 in ws[1]: c0.font=Font(bold=True,color="FFFFFF"); c0.fill=PatternFill("solid",fgColor="1F4E78"); c0.alignment=Alignment(horizontal="center")
    old_heads=[ws.cell(1,i).value for i in range(1,ws.max_column+1)]
    if old_heads!=heads:
        for i,h in enumerate(heads,1): ws.cell(1,i).value=h
    existing={(str(ws.cell(r,1).value),str(ws.cell(r,2).value)):r for r in range(2,ws.max_row+1)}
    for x in rows:
        values=[x["bid_no"],x["revision"],x["title"],x["industry_code"],x["trade"],x["specialty"],x["region"],"전국" if x["is_national"] else "지역",x["estimated_price"],x["base_amount"],x["net_cost"],x["a_value"],x["posted_at"],x["open_at"],x["deadline"],x["joint_allowed"],x.get("joint_region") or "없음",x.get("joint_ratio") or "없음",x.get("joint_method") or "없음",x.get("member_min_ratio") or "없음",x.get("member_count") or "없음",len(x["receivers"]),x["detail_url"],x.get("notice_file", ""),x.get("attachment_dir", ""),x.get("attachment_count",0),datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        target=existing.get((x["bid_no"],x["revision"]))
        if target is None: ws.append(values)
        else:
            for i,value in enumerate(values,1): ws.cell(target,i).value=value
    ws.auto_filter.ref="A1:AA%d"%max(1,ws.max_row)
    for i,w in enumerate([18,8,52,10,30,20,28,12,16,16,16,16,20,20,20,22,36,16,16,18,14,10,58,58,58,12,20],1): ws.column_dimensions[get_column_letter(i)].width=w
    wb.save(str(path)); return path
def save(rows,c):
    groups={}
    for row in rows: groups.setdefault(_posted_day(row).date(),[]).append(row)
    return [_save_day(group,c,datetime(day.year,day.month,day.day)) for day,group in sorted(groups.items())]
def send(row,phone):
    sys.path.insert(0,"/home/pi/n_data")
    try: from notifier import send_tb0485
    finally: sys.path.pop(0)
    item={"bidNtceNm":row["title"],"bidClseDt":row["deadline"],"jntcontrctDutyRgnNm1":row.get("joint_region") or "없음","rgnDutyJntcontrctRt":row.get("joint_ratio") or "없음","presmptPrce":row["estimated_price"] or row["base_amount"],"bidNtceNo":row["bid_no"],"bidNtceOrd":row["revision"]}
    return bool(send_tb0485(item,[phone]))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dry-run",action="store_true"); ap.add_argument("--no-excel",action="store_true"); a=ap.parse_args(); logging.basicConfig(level=logging.INFO,format="[%(asctime)s] %(message)s"); c=cfg()
    if not c.get("verify_tls",True): requests.packages.urllib3.disable_warnings()
    cl=Client(c.get("verify_tls",True)); cl.start()
    latest,start_day,end_day=cl.notices(c.get("lookback_days",7),c.get("page_size",100))
    LOG.info("[COLLECT] range=%s~%s total=%d",start_day,end_day,len(latest)); mod=main_module(); selected=[]; st=State()
    for seed in latest:
        item_typ=str(seed.get("item_typ","")).strip().upper()
        if item_typ not in ("CT","공사") and "공사" not in item_typ:
            LOG.info("[FILTER] %s 공사 아님 item_typ=%s",seed.get("rfx_no"),item_typ); continue
        try:
            row=parse_detail(cl.detail(seed["rfx_id"]),seed); ok,reason=eligible(row,c); LOG.info("[FILTER] %s %s %s",row["bid_no"],ok,reason)
            if not ok: continue
            row["receivers"]=receivers(row,mod); LOG.info("[ROUTE] %s industry=%s region=%s receivers=%d",row["bid_no"],row["industry_code"],row["region"],len(row["receivers"]))
            if not row["receivers"]: continue
            key=row["bid_no"]+"-"+row["revision"]
            if not a.dry_run:
                row["receivers"]=[phone for phone in row["receivers"] if not st.has(key,phone)]
                if not row["receivers"]:
                    LOG.info("[TARGET][SKIP_ALREADY] %s 첨부파일 재수집 안 함",key); continue
            row=enrich_notice_doc(cl,row,c)
            LOG.info("[NOTICE_DOC] %s region=%s ratio=%s method=%s member_min=%s members=%s attachments=%d",row["bid_no"],row.get("joint_region") or "없음",row.get("joint_ratio") or "없음",row.get("joint_method") or "없음",row.get("member_min_ratio") or "없음",row.get("member_count") or "없음",row.get("attachment_count",0))
            selected.append(row)
        except Exception as e: LOG.exception("[DETAIL][ERR] %s %s",seed.get("rfx_no"),e)
    if not a.no_excel:
        for path in save(selected,c): LOG.info("[SAVE] %s",path)
    if a.dry_run: LOG.info("[DRY_RUN] 발송하지 않음"); return 0
    for row in selected:
        key=row["bid_no"]+"-"+row["revision"]
        for phone in row["receivers"]:
            if st.has(key,phone): LOG.info("[SEND][SKIP_ALREADY] %s",key); continue
            if send(row,phone): st.mark(key,phone,row["title"]); LOG.info("[SEND][OK] %s",key)
            else: LOG.error("[SEND][FAIL] %s",key)
    return 0
if __name__=="__main__": sys.exit(main())
