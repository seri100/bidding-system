import os
if os.getenv('TEST_MODE','0')=='1':
    os.environ['ALLIGO_FORCE_PHONE'] = os.getenv('TEST_PHONE','REDACTED_PRIVATE_VALUE')


#!/usr/bin/env python
# coding: utf-8

import sys
import requests
import datetime
import json
import openpyxl
import os
import time
import errno
import shutil
from typing import List, Dict

# ====================== 공용 유틸 ======================

# ✅ 저장 위치를 한 단계 줄여 Windows에서 \\192.168.0.250\bid\gon_auto 로 직접 접근 가능
PRIMARY_OUT_DIR = "/mnt/vol1/gon_auto"                        # SMB 마운트 (Z:\bid\gon_auto)
FALLBACK_OUT_DIR = "/home/pi/seri_Alarm_Server3/out_gon_auto" # 로컬 폴백
FALLBACK_LOG_DIR = "/home/pi/seri_Alarm_Server3/logs"         # 로컬 로그 폴백

def safe_ensure_dir(path: str, retries: int = 8, delay: float = 1.5) -> bool:
    """FUSE/SMB 환경에서 디렉터리 생성/확인 안전화"""
    for _ in range(retries):
        try:
            if os.path.isdir(path):
                return True
            os.makedirs(path, exist_ok=True)
            return True
        except BlockingIOError:
            time.sleep(delay)
        except OSError as e:
            if e.errno in (errno.EEXIST, ):
                return True
            time.sleep(delay)
    return False

def prepare_out_dir(primary: str, fallback: str) -> str:
    """기본 경로 만들기 시도, 실패 시 로컬 폴더로 폴백"""
    if safe_ensure_dir(primary):
        return primary
    os.makedirs(fallback, exist_ok=True)
    print(f"[WARN] SMB/WebDAV 경로 준비 실패. 로컬 폴더로 폴백합니다: {fallback}")
    return fallback

def safe_redirect_stdout(log_dir: str):
    """로그 파일로 stdout/stderr 리다이렉트"""
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if not safe_ensure_dir(log_dir):
        os.makedirs(FALLBACK_LOG_DIR, exist_ok=True)
        log_dir = FALLBACK_LOG_DIR
        print(f"[WARN] 로그 경로 생성 실패 → {log_dir} 로 폴백")
    log_file = os.path.join(log_dir, f"log_{now_str}.txt")
    try:
        log_fp = open(log_file, "w", encoding="utf-8")
        sys.stdout = log_fp
        sys.stderr = sys.stdout
        print(f"[LOG] 시작: {now_str} → {log_file}")
    except Exception as e:
        print(f"[WARN] 로그 파일 오픈 실패({e}). 콘솔 출력으로 진행합니다.")

def try_flush_to_webdav(src_dir: str, dst_dir: str = PRIMARY_OUT_DIR):
    """로컬 폴백 데이터를 SMB/WebDAV 경로로 동기화 시도"""
    if src_dir == dst_dir:
        return
    try:
        if not safe_ensure_dir(dst_dir):
            print(f"[SYNC-WARN] 대상 경로 준비 실패: {dst_dir}")
            return
        for name in os.listdir(src_dir):
            s = os.path.join(src_dir, name)
            d = os.path.join(dst_dir, name)
            try:
                if os.path.isfile(s):
                    shutil.copy2(s, d)
                    print(f"[SYNC] {s} -> {d}")
            except Exception as e:
                print(f"[SYNC-WARN] {s} 복사 실패: {e}")
    except Exception as e:
        print(f"[SYNC-ERROR] 동기화 실패: {e}")

def parse_items_from_body(body_obj):
    items = body_obj.get('items', [])
    if isinstance(items, dict):
        items = items.get('item', [])
    return items or []

def to_int(x, default=0):
    if x is None:
        return default
    try:
        return int(str(x).replace(",", "").strip())
    except Exception:
        return default

# ====================== 설정 로딩 ======================

def load_api_key(filepath='/home/pi/seri_Alarm_Server3/bid_api_key.txt'):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read().strip()

def load_region_keywords_from_excel(filepath='/home/pi/seri_Alarm_Server3/settings.xlsx') -> List[str]:
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    raw = ws['G3'].value or ''
    return [s.strip() for s in str(raw).split(',') if s and s.strip()]

def load_sms_targets(filepath='/home/pi/seri_Alarm_Server3/companys.xlsx') -> List[Dict[str, str]]:
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    targets = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        region, company, phone = row[:3]
        if region and phone:
            targets.append({
                '지역': str(region).strip(),
                '업체명': (str(company).strip() if company else ''),
                '전화번호': str(phone).strip()
            })
    return targets

def load_aligo_settings(filepath='/home/pi/seri_Alarm_Server3/aligo_settings.txt'):
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
    for retry in range(5):
        try:
            resp = requests.get(full_url, params=params, timeout=timeout)
            data = resp.json()
            code = str(data.get('response', {}).get('header', {}).get('resultCode', ''))
            if code == '00':
                return data
            else:
                print(f"[API] 재시도 {retry+1}/5: resultCode={code}")
        except Exception as e:
            print(f"[API] 예외 재시도 {retry+1}/5: {e}")
        time.sleep(0.8)
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
            print(f"[WARN] 코드 {code} 결과 없음/실패")
            continue

        body = result.get('response', {}).get('body', {}) or {}
        items = parse_items_from_body(body)

        for item in items:
            if str(item.get('bidNtceNo', '')).startswith('T'):
                continue
            if '취소' in str(item.get('ntceKindNm', '')):
                continue
            if '국방' in str(item.get('opengPlce', '')):
                continue

            bdgt_amt = to_int(item.get('bdgtAmt'))
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
            if str(item.get('rgnDutyJntcontrctYn', '')).upper() != 'Y':
                prtcpt_params = {
                    'numOfRows': 10,
                    'pageNo': 1,
                    'type': 'json',
                    'inqryDiv': '2',
                    'bidNtceNo': item.get('bidNtceNo', ''),
                    'bidNtceOrd': item.get('bidNtceOrd', '')
                }
                result16 = req_url(URI_BID_16, prtcpt_params, api_key)
                if result16:
                    body16 = result16.get('response', {}).get('body', {}) or {}
                    prtcpt_items = parse_items_from_body(body16)
                    if prtcpt_items:
                        region_str = str(prtcpt_items[0].get('prtcptPsblRgnNm', ''))
                        for region in region_keywords:
                            if region and (region in region_str):
                                bid_copy = bid.copy()
                                bid_copy['참가가능지역'] = region_str
                                region_bids[region].append(bid_copy)
                                matched = True
            else:
                for region in region_keywords:
                    if not region:
                        continue
                    if any(region in str(item.get(f'jntcontrctDutyRgnNm{i}', '')) for i in range(1, 4)):
                        bid_copy = bid.copy()
                        bid_copy['참가가능지역'] = region
                        region_bids[region].append(bid_copy)
                        matched = True
            # 매칭되지 않으면 버림
    return region_bids

# ====================== 저장 ======================

def save_by_region(region_bids: Dict[str, List[Dict]], save_dir: str):
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"입찰공고_지역분류_{now_str}.xlsx"
    tmp_dir = "/home/pi/seri_Alarm_Server3/tmp_xlsx"
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, filename)

    wb = openpyxl.Workbook()
    default_ws = wb.active
    has_data = False

    for region, bids in region_bids.items():
        if not bids:
            continue
        has_data = True
        ws = wb.create_sheet(title=str(region)[:31] or "Sheet")
        headers = list(bids[0].keys())
        ws.append(headers)
        for bid in bids:
            ws.append([bid.get(k, '') for k in headers])

    if has_data:
        wb.remove(default_ws)
        wb.save(tmp_path)
        print(f"✅ 임시 저장 완료: {tmp_path}")
        if safe_ensure_dir(save_dir):
            try:
                dst_path = os.path.join(save_dir, filename)
                shutil.copy2(tmp_path, dst_path)
                print(f"✅ 최종 저장 완료: {dst_path}")
                return dst_path
            except Exception as e:
                print(f"[WARN] 복사 실패. 로컬만 보존합니다: {e}")
                return tmp_path
        else:
            print(f"[WARN] 저장 경로 준비 실패. 로컬만 보존합니다: {tmp_path}")
            return tmp_path
    else:
        print("⚠ 저장할 데이터가 없습니다.")
        return None

# ====================== 문자 발송 ======================

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
        response = requests.post(url, data=payload, timeout=20)
        result = response.json()
        print(f"문자 전송 결과: {receiver} → {result.get('result_code')} / {result.get('message')}")
    except Exception as e:
        print(f"문자 전송 실패 ({receiver}): {e}")

# ====================== 실행 ======================

if __name__ == "__main__":
    # ✅ 결과 엑셀 최종 저장 경로를 NAS 폴더로 고정
    OUT_DIR = "/mnt/vol1/bid/gon_auto"
    os.makedirs(OUT_DIR, exist_ok=True)

    safe_redirect_stdout(OUT_DIR)

    API_KEY = load_api_key('/home/pi/seri_Alarm_Server3/bid_api_key.txt')
    REGION_KEYWORDS = load_region_keywords_from_excel('/home/pi/seri_Alarm_Server3/settings.xlsx')
    SMS_TARGETS = load_sms_targets('/home/pi/seri_Alarm_Server3/companys.xlsx')
    ALIGO_API_KEY, ALIGO_USER_ID, ALIGO_SENDER = load_aligo_settings('/home/pi/seri_Alarm_Server3/aligo_settings.txt')
    INDSTRY_CODES = ['6202', '0040', '0037', '0038', '0039']
    MIN_BUDGET = 30_000_000

    print(f"[CONF] OUT_DIR={OUT_DIR}")
    print(f"[CONF] REGIONS={REGION_KEYWORDS}")
    print(f"[CONF] CODES={INDSTRY_CODES}")

    region_bids = collect_bids(API_KEY, INDSTRY_CODES, MIN_BUDGET, REGION_KEYWORDS)
    saved_path = save_by_region(region_bids, OUT_DIR)

    try_flush_to_webdav(OUT_DIR if OUT_DIR != FALLBACK_OUT_DIR else FALLBACK_OUT_DIR, PRIMARY_OUT_DIR)

    # 문자 발송이 필요하면 주석 해제
    # for target in SMS_TARGETS:
    #     region = target['지역']
    #     phone = target['전화번호']
    #     bids = region_bids.get(region, [])
    #     if not bids:
    #         continue
    #     message = f"[{region}] {len(bids)}건의 입찰공고가 등록되었습니다."
    #     print(f"→ {target['업체명']} ({phone}): {message}")
    #     send_sms_via_alligo(ALIGO_API_KEY, ALIGO_USER_ID, ALIGO_SENDER, phone, message)

    # 7) 하루 단위 백업:이 코드가 실행될 때마다 금일 생성된 파일만 자동으로 날짜별 폴더에 복사합니다.

    try:

        backup_root = "/mnt/vol1/gon_auto_backup"

        today = datetime.datetime.now().strftime("%Y-%m-%d")

        backup_dir = os.path.join(backup_root, today)

        os.makedirs(backup_dir, exist_ok=True)



        # 오늘 생성된 파일만 복사 (이 스크립트 실행 시점 기준 하루)

        cutoff = datetime.datetime.now() - datetime.timedelta(days=1)

        for name in os.listdir(OUT_DIR):

            src_path = os.path.join(OUT_DIR, name)

            if os.path.isfile(src_path):

                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(src_path))

                if mtime.date() == datetime.datetime.now().date():

                    shutil.copy2(src_path, backup_dir)

        print(f"[BACKUP] 오늘 파일을 {backup_dir} 로 백업 완료")

    except Exception as e:

        print(f"[BACKUP-WARN] 백업 실패: {e}")



