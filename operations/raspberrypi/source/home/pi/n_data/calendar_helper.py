
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



from googleapiclient.discovery import build

from google.auth.transport.requests import Request

from google.oauth2.credentials import Credentials

import os

import pickle

from datetime import datetime, timedelta



CALENDAR_ID = "primary"

SCOPES = ['https://www.googleapis.com/auth/calendar']



def get_calendar_service():

    """Google Calendar 서비스 (기본 인증 사용)"""

    creds = None

    token_file = '/home/pi/n_data/token.pickle'

    

    if os.path.exists(token_file):

        with open(token_file, 'rb') as f:

            creds = pickle.load(f)

        

        if creds and creds.expired and creds.refresh_token:

            creds.refresh(Request())

    

    if not creds:

        return None

    

    return build('calendar', 'v3', credentials=creds)





def should_add_to_calendar(row):

    """

    규칙 필터: 전국(0038,0039,0040,6202), 충북/세종(0038,0039,0040,6202)만 추가

    """

    try:

        raw = row.get('원문') or {}

        

        # 1) 업종 확인

        ind = str(raw.get('indstrytyCd') or row.get('공고업종코드') or '').strip()

        if ind not in ('0038', '0039', '0040', '6202'):

            return False

        

        # 2) 지역 확인 (전국/충북/세종만)

        region = str(row.get('대표지역') or '').strip()

        if region not in ('전국', '충북', '세종'):

            return False

        

        # 3) 수신번호 확인 (발송 대상이어야 함)

        recv = str(row.get('수신번호') or '').strip()

        if not recv:

            return False

        

        return True

    

    except Exception:

        return False





def add_event_to_calendar(row):

    """공고를 Google Calendar에 추가 (입찰 개시일 기준)"""

    try:

        service = get_calendar_service()

        if not service:

            bid_no = str((row.get('원문') or {}).get('bidNtceNo') or row.get('공고번호') or '')

            return {'success': False, 'error': 'No service', 'bid_no': bid_no}

        

        # 필터 확인

        if not should_add_to_calendar(row):

            bid_no = str((row.get('원문') or {}).get('bidNtceNo') or row.get('공고번호') or '')

            return {'success': False, 'error': 'Filter not matched', 'bid_no': bid_no}

        

        raw = row.get('원문') or {}

        

        bid_no = str(raw.get('bidNtceNo') or row.get('공고번호') or '')

        bid_name = str(raw.get('bidNtceNm') or row.get('공고명') or '')

        

        # 입찰 개시일 (bidBeginDt or 시작일시)

        begin_time_str = str(raw.get('bidBeginDt') or raw.get('bidBeginDtTm') or row.get('시작일시') or '')

        

        # 입찰 마감일

        close_time_str = str(raw.get('bidClseDt') or row.get('입찰마감일시') or '')

        

        amount = str(row.get('추정금액') or '0')

        region = str(row.get('대표지역') or '')

        ind = str(raw.get('indstrytyCd') or row.get('공고업종코드') or '')

        

        # 개시일 파싱

        try:

            if begin_time_str and len(begin_time_str) >= 8:

                # YYYYMMDDHHMM 또는 YYYY-MM-DD HH:MM:SS 형식

                if 'T' in begin_time_str or '-' in begin_time_str:

                    begin_dt = datetime.fromisoformat(begin_time_str.replace('Z', '+00:00'))

                else:

                    # 숫자만 있는 경우

                    if len(begin_time_str) == 12:

                        begin_dt = datetime.strptime(begin_time_str, '%Y%m%d%H%M')

                    elif len(begin_time_str) >= 8:

                        begin_dt = datetime.strptime(begin_time_str[:8], '%Y%m%d')

                    else:

                        begin_dt = datetime.now()

            else:

                begin_dt = datetime.now()

        except Exception:

            begin_dt = datetime.now()

        

        # 마감일 파싱

        try:

            if close_time_str and len(close_time_str) >= 8:

                if 'T' in close_time_str or '-' in close_time_str:

                    close_dt = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))

                else:

                    if len(close_time_str) == 12:

                        close_dt = datetime.strptime(close_time_str, '%Y%m%d%H%M')

                    elif len(close_time_str) >= 8:

                        close_dt = datetime.strptime(close_time_str[:8], '%Y%m%d')

                    else:

                        close_dt = begin_dt + timedelta(days=7)

            else:

                close_dt = begin_dt + timedelta(days=7)

        except Exception:

            close_dt = begin_dt + timedelta(days=7)

        

        # 개시일 + 1시간을 종료시간으로 설정

        end_dt = begin_dt + timedelta(hours=1)

        

        # 업종명 매핑

        ind_name = {

            '0038': '소방',

            '0039': '기계설비',

            '0040': '기계설비',

            '6202': '기계설비',

        }.get(ind, '기타')

        

        # 이벤트 생성

        event = {

            'summary': f"[입찰개시] {bid_name}",

            'description': (

                f"공고번호: {bid_no}\n"

                f"업종: {ind_name}\n"

                f"지역: {region}\n"

                f"추정금액: {amount}원\n"

                f"입찰개시: {begin_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"

                f"입찰마감: {close_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"

                f"나라장터: https://www.g2b.go.kr:8101/ep/result/serviceList.do?bidno={bid_no}"

            ),

            'start': {

                'dateTime': begin_dt.isoformat(),

                'timeZone': 'Asia/Seoul',

            },

            'end': {

                'dateTime': end_dt.isoformat(),

                'timeZone': 'Asia/Seoul',

            },

            'location': region,

        }

        

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

        

        return {'success': True, 'bid_no': bid_no}

    

    except Exception as e:

        bid_no = str((row.get('원문') or {}).get('bidNtceNo') or row.get('공고번호') or '')

        return {'success': False, 'error': str(e), 'bid_no': bid_no}





def add_events_batch(rows):

    """여러 공고를 캘린더에 추가 (필터링 적용)"""

    return [add_event_to_calendar(r) for r in rows]

