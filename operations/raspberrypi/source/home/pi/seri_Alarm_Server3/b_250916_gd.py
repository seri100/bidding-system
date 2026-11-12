#!/usr/bin/env python
# coding: utf-8

# In[6]:

import sys
import requests
import datetime
import json
import openpyxl
import os

log_dir = "/mnt/vol1/bid/gon_auto"
#log_dir = r"Z:\VOL1\bid\gon_auto"
os.makedirs(log_dir, exist_ok=True)

now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"log_{now_str}.txt")

sys.stdout = open(log_file, "w", encoding="utf-8")
sys.stderr = sys.stdout
# ====================== 설정 로딩 ======================

def load_api_key(filepath='/home/pi/seri_Alarm_Server3/bid_api_key.txt'):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()

def load_region_keywords_from_excel(filepath='settings.xlsx'):
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    raw = ws['G3'].value or ''
    return [s.strip() for s in raw.split(',') if s.strip()]

def load_sms_targets(filepath='companys.xlsx'):
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    targets = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        region, company, phone = row[:3]
        if region and phone:
            targets.append({'지역': region.strip(), '업체명': company.strip() if company else '', '전화번호': phone.strip()})
    return targets

def load_aligo_settings(filepath='aligo_settings.txt'):
    settings = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                settings[k.strip()] = v.strip()
    return settings.get('api_key'), settings.get('user_id'), settings.get('sender')

# ====================== API 요청 ======================

def req_url(uri, params, api_key, timeout=30):
    full_url = uri + '?ServiceKey=' + api_key
    try:
        for retry in range(5):
            response = requests.get(full_url, params=params, timeout=timeout)
            result = response.json()
            if result['response']['header']['resultCode'] == '00':
                return result
        return None
    except Exception as e:
        print("API 요청 실패:", e)
        return None

# ====================== 입찰공고 수집 ======================

def collect_bids(api_key, indstry_codes, min_budget, region_keywords, search_hours=24):
    now = datetime.datetime.now()
    endtime = now.strftime("%Y%m%d%H%M")
    begintime = (now - datetime.timedelta(hours=search_hours)).strftime("%Y%m%d%H%M")

    URI_BID_11 = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch'
    URI_BID_16 = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoPrtcptPsblRgn'

    region_bids = {region: [] for region in region_keywords}

    for code in indstry_codes:
        params = {
            'numOfRows': 100,
            'pageNo': 1,
            'type': 'json',
            'inqryDiv': '1',
            'inqryBgnDt': begintime,
            'inqryEndDt': endtime,
            'indstrytyCd': code
        }
        result = req_url(URI_BID_11, params, api_key)
        if not result:
            continue

        items = result['response']['body'].get('items', [])
        for item in items:
            if item['bidNtceNo'].startswith('T') or '취소' in item.get('ntceKindNm', '') or '국방' in item.get('opengPlce', ''):
                continue

            bdgt_amt = int(item['bdgtAmt']) if item['bdgtAmt'] else 0
            if bdgt_amt < min_budget:
                continue

            bid = {
                '공고명': item.get('bidNtceNm', ''),
                '입찰공고일시': item.get('bidNtceDt', ''),
                '입찰시작일시': item.get('bidBeginDt', ''),
                '입찰마감일시': item.get('bidClseDt', ''),
                '공동도급지역1': item.get('jntcontrctDutyRgnNm1', ''),
                '공동도급지역2': item.get('jntcontrctDutyRgnNm2', ''),
                '공동도급지역3': item.get('jntcontrctDutyRgnNm3', ''),
                '공동도급비율': item.get('rgnDutyJntcontrctRt', ''),
                '추정금액': bdgt_amt,
                '공고번호': item.get('bidNtceNo', ''),
                '차수': item.get('bidNtceOrd', ''),
                '공종코드': code,
                '공고URL': item.get('bidNtceUrl', '')
            }

            matched = False
            if item.get('rgnDutyJntcontrctYn') != 'Y':
                prtcpt_params = {
                    'numOfRows': 10,
                    'pageNo': 1,
                    'type': 'json',
                    'inqryDiv': '2',
                    'bidNtceNo': item['bidNtceNo'],
                    'bidNtceOrd': item['bidNtceOrd']
                }
                result16 = req_url(URI_BID_16, prtcpt_params, api_key)
                if result16:
                    prtcpt_items = result16['response']['body'].get('items', [])
                    if prtcpt_items:
                        region_str = prtcpt_items[0].get('prtcptPsblRgnNm', '')
                        for region in region_keywords:
                            if region in region_str:
                                bid_copy = bid.copy()
                                bid_copy['참가가능지역'] = region_str
                                region_bids[region].append(bid_copy)
                                matched = True
            else:
                for region in region_keywords:
                    if any(region in item.get(f'jntcontrctDutyRgnNm{i}', '') for i in range(1, 4)):
                        bid_copy = bid.copy()
                        bid_copy['참가가능지역'] = region
                        region_bids[region].append(bid_copy)
                        matched = True
    return region_bids

# ====================== 저장 ======================

def save_by_region(region_bids, save_dir):
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"입찰공고_지역분류_{now_str}.xlsx"
    filepath = os.path.join(save_dir, filename)

    wb = openpyxl.Workbook()
    default_ws = wb.active
    has_data = False

    for region, bids in region_bids.items():
        if not bids:
            continue
        has_data = True
        ws = wb.create_sheet(title=region)
        headers = list(bids[0].keys())
        ws.append(headers)
        for bid in bids:
            ws.append([bid.get(k, '') for k in headers])

    if has_data:
        wb.remove(default_ws)
        os.makedirs(save_dir, exist_ok=True)
        wb.save(filepath)
        print(f"✅ 저장 완료: {filepath}")
    else:
        print("⚠ 저장할 데이터가 없습니다.")

# ====================== 문자 발송 (알리고 연동) ======================

def send_sms_via_alligo(api_key, user_id, sender, receiver, message):
    url = 'https://apis.aligo.in/send/'
    payload = {
        'key': api_key,
        'user_id': user_id,
        'sender': sender,
        'receiver': receiver,
        'msg': message,
        'msg_type': 'SMS',
        'title': '입찰알림'
    }
    try:
        response = requests.post(url, data=payload)
        result = response.json()
        print(f"📤 문자 전송 결과: {receiver} → {result.get('result_code')} / {result.get('message')}")
    except Exception as e:
        print(f"⚠ 문자 전송 실패 ({receiver}):", e)

# ====================== 실행 ======================

if __name__ == "__main__":
    API_KEY = load_api_key('/home/pi/seri_Alarm_Server3/bid_api_key.txt')
    REGION_KEYWORDS = load_region_keywords_from_excel('/home/pi/seri_Alarm_Server3/settings.xlsx')
    SSMS_TARGETS = load_sms_targets('/home/pi/seri_Alarm_Server3/companys.xlsx')
    ALIGO_API_KEY, ALIGO_USER_ID, ALIGO_SENDER = load_aligo_settings('/home/pi/seri_Alarm_Server3/aligo_settings.txt')
    SAVE_DIR ="/mnt/vol1/bid/gon_auto" 
    #SAVE_DIR = r"Z:\VOL1\bid\gon_auto"
    INDSTRY_CODES = ['6202', '0040', '0037', '0038', '0039']
    MIN_BUDGET = 30_000_000

    region_bids = collect_bids(API_KEY, INDSTRY_CODES, MIN_BUDGET, REGION_KEYWORDS)
    save_by_region(region_bids, SAVE_DIR)

   # for target in SMS_TARGETS:
        #region = target['지역']
        #phone = target['전화번호']
        #bids = region_bids.get(region, [])
        #if not bids:
            #continue
        #message = f"[{region}] {len(bids)}건의 입찰공고가 등록되었습니다."
        #print(f"→ {target['업체명']} ({phone}): {message}")
        #send_sms_via_alligo(ALIGO_API_KEY, ALIGO_USER_ID, ALIGO_SENDER, phone, message)


# In[ ]:




