
# /home/pi/n_data/notifier.py

# 목적: TB_0485 포맷으로 메시지 만들어 Alligo로 발송 + 결과 로깅



from typing import Dict, List, Optional

import datetime, sqlite3, os



from alligo import Alligo  # 이미 /home/pi/n_data/alligo.py에 있음



DB_PATH = "/home/pi/n_data/state.db"

OUTBOX_PATH = "/home/pi/n_data/_outbox.log"



def _fmt_number(num) -> str:

    try:

        n = float(str(num).replace(",", "").strip())

        return f"{int(n):,}"

    except Exception:

        return str(num)



def compose_tb0485_message(item: Dict) -> str:

    """

    item dict에 다음 키가 있다고 가정:

    - bidNtceNm, bidClseDt, jntcontrctDutyRgnNm1, rgnDutyJntcontrctRt, presmptPrce, bidNtceNo, bidNtceOrd

    """

    return (

        "[세리공영]\n\n"

        f"공고명 : {item.get('bidNtceNm','-')}\n"

        f"입찰마감일시 : {item.get('bidClseDt','-')}\n"

        f"공동도급지역 : {item.get('jntcontrctDutyRgnNm1','-')}\n"

        f"공동도급비율 : {item.get('rgnDutyJntcontrctRt','-')}\n"

        f"추정금액 : {_fmt_number(item.get('presmptPrce','-'))}\n"

        f"공고번호 : {item.get('bidNtceNo','-')} - {item.get('bidNtceOrd','-')}"

    )



def send_tb0485(item: Dict, receivers: List[str]) -> bool:

    """

    Alligo로 TB_0485 템플릿 메시지 전송.

    item 필수 키는 compose_tb0485_message 주석 참조.

    """

    msg = compose_tb0485_message(item)

    a = Alligo()

    ok = a.sendTalk(

        tpl_code="TB_0485",

        sender=os.getenv("ONLY_TO","REDACTED_PRIVATE_VALUE"),  # 발신번호(알리고 등록된 번호여야 함)

        msgHead="[세리공영] 입찰 공고 알림",

        message=msg,

        receiverList=receivers,

    )



    # outbox 로그 남기기(운영/테스트 공통)

    try:

        with open(OUTBOX_PATH, "a", encoding="utf-8") as f:

            f.write(

                (

                    '{"ts":"%s","to":"%s","title":"[세리공영] 입찰 공고 알림",'

                    '"body":%r,"prod":%s}\n'

                )

                % (

                    datetime.datetime.now().isoformat(timespec="seconds"),

                    ",".join(receivers),

                    msg,

                    "true",

                )

            )

    except Exception:

        pass



    # DB sent_log 기록 (수신자별)

    try:

        conn = sqlite3.connect(DB_PATH)

        cur = conn.cursor()

        bid_no = item.get("bidNtceNo","")

        bid_ord = item.get("bidNtceOrd","")

        now = datetime.datetime.now().isoformat(timespec="seconds")

        for to in receivers:

            cur.execute(

                "INSERT OR IGNORE INTO sent_log (bid_no,bid_ord,to_no,prod,sent_at) VALUES (?,?,?,?,?)",

                (bid_no, bid_ord, to, 1, now),

            )

        conn.commit()

        conn.close()

    except Exception:

        pass



    return bool(ok)


