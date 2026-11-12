
# -*- coding: utf-8 -*-



from __future__ import print_function



from datetime import datetime, timedelta

from lh_calendar_oauth_test import build_oauth_service, CALENDAR_ID



service = build_oauth_service()



start_dt = datetime(2026, 6, 16, 11, 0, 0)

end_dt = start_dt + timedelta(minutes=30)



event = {

    "summary": "[LH-OAUTH-ATTENDEE-TEST] 참가여부 버튼 테스트",

    "description": "\n".join([

        "REDACTED_PRIVATE_VALUE OAuth 참석자 테스트",

        "공고번호 : OAUTH-ATTENDEE-TEST",

        "목적 : 참석 여부 / 예 / 아니요 / 미정 버튼 표시 확인",

    ]),

    "start": {

        "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),

        "timeZone": "Asia/Seoul",

    },

    "end": {

        "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),

        "timeZone": "Asia/Seoul",

    },

    "attendees": [

        {

            "email": "redacted@example.invalid",

            "responseStatus": "needsAction",

        },

        {

            "email": "redacted@example.invalid",

            "responseStatus": "needsAction",

        },

    ],

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

    sendUpdates="all",

).execute()



print("[CREATED]", created.get("summary"))

print("[ID]", created.get("id"))

print("[LINK]", created.get("htmlLink"))

print("[ATTENDEES]")

for a in created.get("attendees", []):

    print(" -", a.get("email"), a.get("responseStatus"), "self=", a.get("self"))

