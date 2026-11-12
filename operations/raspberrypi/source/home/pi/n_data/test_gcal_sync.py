
from modules.calendar_sync import sync_message_to_gcal



sample = """[세리공영]



공고명 : 계영원 스프링클러 설치 소방공사

입찰마감일시 : 2026-05-20 10:00:00

공동도급지역 : 없음

공동도급비율 : 없음

추정금액 : 671,682,000원

공고번호 : R26BK01513674 - 000"""



status, link, event_id = sync_message_to_gcal(sample)



print("status:", status)

print("event_id:", event_id)

print("link:", link)

