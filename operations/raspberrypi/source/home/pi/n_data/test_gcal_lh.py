
from modules.calendar_sync import sync_message_to_gcal, parse_message_to_event



sample = """[세리공영]

LH 입찰공고

공고번호 : 2601654

업종유형 : 소방시설공사

입찰공고건명 : 경산대임 A-3BL 아파트 소방시설공사 3공구

기초금액 : 8,704,396,000원 (팔십칠억사백삼십구만육천원)

참가지역 : 경북

입찰서접수개시일시 : 2026/05/26 10:00

입찰서접수마감일시 : 2026/05/28 13:00"""



event = parse_message_to_event(sample)

print("id:", event["id"])

print("summary:", event["summary"])

print("start:", event["start_dt"])

print("end:", event["end_dt"])

print("location:", event["location"])



status, link, event_id = sync_message_to_gcal(sample)

print("status:", status)

print("event_id:", event_id)

print("link:", link)

