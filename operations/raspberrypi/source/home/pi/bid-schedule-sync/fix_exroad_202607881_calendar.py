#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import sys



sys.path.insert(

    0,

    "/home/pi/bid-schedule-sync"

)



import institution_calendar_bridge as bridge



bid_no = "202607881"

bid_name = "중앙선 죽령터널 소방시설 보수공사"



record = bridge.standard(

    "한국도로공사",

    bid_no,

    bid_name,

    "2026-08-14 10:00",

    "2026-08-24 13:00",

    "",

    status="한국도로공사 공식 상세화면 확인",

    amount=659945000,

    region="",

    license_doc="3000 0039 소방시설공사업",

    agreement_source=(

        "한국도로공사 전자조달 공식 상세화면 "

        "findListBid"

    ),

    system="한국도로공사 전자조달",

)



service = bridge.calendar_service(True)

calendar_id = record["calendar_id"]



events = bridge.list_events(

    service,

    calendar_id

)



matched = []



for event in events:

    combined = "%s\n%s" % (

        event.get("summary", ""),

        event.get("description", "")

    )



    private_bid_no = (

        event.get("extendedProperties", {})

        .get("private", {})

        .get("bid_no", "")

    )



    if (

        bid_no in combined

        or private_bid_no == bid_no

        or bid_name in combined

    ):

        matched.append(event)



body = bridge.event_body(record)



if matched:

    event_id = matched[0]["id"]



    service.events().patch(

        calendarId=calendar_id,

        eventId=event_id,

        body=body,

        sendUpdates="none"

    ).execute()



    print(

        "[OK] 기존 Calendar 이벤트 보정:",

        event_id

    )



    if len(matched) > 1:

        print(

            "[WARN] 같은 공고명 이벤트가",

            len(matched),

            "개입니다. 첫 이벤트만 보정했습니다."

        )

else:

    created = service.events().insert(

        calendarId=calendar_id,

        body=body,

        sendUpdates="none"

    ).execute()



    print(

        "[OK] Calendar 이벤트 신규 생성:",

        created.get("id", "")

    )



print("[OK] 공고번호:", bid_no)

print("[OK] 입찰개시: 2026-08-14 10:00")

print("[OK] 입찰마감: 2026-08-24 13:00")

