
# -*- coding: utf-8 -*-



from __future__ import print_function



import os

import pickle

from datetime import datetime, timedelta



from googleapiclient.discovery import build

from google.auth.transport.requests import Request

from google_auth_oauthlib.flow import InstalledAppFlow



CALENDAR_ID = "redacted@example.invalid"



CLIENT_SECRET_FILE = "/home/pi/n_data/credentials/google_calendar_oauth_client.json"

TOKEN_FILE = "/home/pi/n_data/credentials/google_calendar_oauth_token.pickle"



SCOPES = ["https://www.googleapis.com/auth/calendar"]





def build_oauth_service():

    creds = None



    if os.path.exists(TOKEN_FILE):

        with open(TOKEN_FILE, "rb") as token:

            creds = pickle.load(token)



    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:

            creds.refresh(Request())

        else:

            flow = InstalledAppFlow.from_client_secrets_file(

                CLIENT_SECRET_FILE,

                SCOPES,

            )



            if hasattr(flow, "run_console"):

                creds = flow.run_console()

            else:

                creds = flow.run_local_server(port=0)



        with open(TOKEN_FILE, "wb") as token:

            pickle.dump(creds, token)



        os.chmod(TOKEN_FILE, 0o600)



    return build("calendar", "v3", credentials=creds)





def main():

    service = build_oauth_service()



    start_dt = datetime(2026, 6, 16, 10, 30, 0)

    end_dt = start_dt + timedelta(minutes=30)



    event = {

        "summary": "[LH-OAUTH-TEST] 참가여부 테스트",

        "description": "\n".join([

            "REDACTED_PRIVATE_VALUE OAuth 테스트",

            "공고번호 : OAUTH-TEST",

            "목적 : OAuth 방식 일정 생성 확인",

        ]),

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

            ],

        },

    }



    created = service.events().insert(

        calendarId=CALENDAR_ID,

        body=event,

    ).execute()



    print("[CREATED]", created.get("summary"))

    print("[ID]", created.get("id"))

    print("[LINK]", created.get("htmlLink"))





if __name__ == "__main__":

    main()

