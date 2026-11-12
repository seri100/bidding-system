
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import sys

from pathlib import Path

from datetime import datetime, timedelta



# 기존 n_data 캘린더 모듈 사용

sys.path.insert(0, "/home/pi/n_data")



from google.oauth2 import service_account

from googleapiclient.discovery import build



CALENDAR_ID = "primary"

SERVICE_ACCOUNT_FILE = "/home/pi/n_data/credentials/google_calendar_service_account.json"

SCOPES = ["https://www.googleapis.com/auth/calendar"]





def build_service():

    creds = service_account.Credentials.from_service_account_file(

        SERVICE_ACCOUNT_FILE,

        scopes=SCOPES,

    )

    return build("calendar", "v3", credentials=creds)





def main():

    service = build_service()



    bid_no = "2602007"

    title = "[LH] 부산명지 A-5BL 아파트 소방시설공사 2공구"



    start_dt = datetime.strptime("2026/06/30 11:00", "%Y/%m/%d %H:%M")

    end_dt = start_dt + timedelta(minutes=30)



    description = "\n".join([

        "REDACTED_PRIVATE_VALUE",

        "공고번호 : 2602007",

        "업종유형 : 소방시설공사",

        "입찰공고건명 : 부산명지 A-5BL 아파트 소방시설공사 2공구",

        "기초금액 : 27,660,601,000원 (이백칠십육억육천육십만일천원)",

        "참가지역 : ",

        "입찰서접수개시일시 : 2026/06/26 10:00",

        "입찰서접수마감일시 : 2026/06/30 11:00",

    ])



    # 중복 방지: 같은 공고번호가 이미 있는지 먼저 검색

    time_min = "2026-06-30T00:00:00+09:00"

    time_max = "2026-07-01T00:00:00+09:00"



    found = service.events().list(

        calendarId=CALENDAR_ID,

        timeMin=time_min,

        timeMax=time_max,

        q=bid_no,

        singleEvents=True,

        orderBy="startTime",

    ).execute().get("items", [])



    if found:

        print("[SKIP] calendar already exists")

        for ev in found:

            print(ev.get("htmlLink", ""))

        return



    event = {

        "summary": title,

        "description": description,

        "start": {

            "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),

            "timeZone": "Asia/Seoul",

        },

        "end": {

            "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),

            "timeZone": "Asia/Seoul",

        },

        "reminders": {

            "useDefault": False,

            "overrides": [

                {"method": "popup", "minutes": 60},

                {"method": "popup", "minutes": 1440},

            ],

        },

    }



    created = service.events().insert(

        calendarId=CALENDAR_ID,

        body=event,

    ).execute()



    print("[OK] calendar inserted")

    print(created.get("htmlLink", ""))





if __name__ == "__main__":

    main()

