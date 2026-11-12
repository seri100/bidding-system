
from kakao_send_tb0485 import send_for_item



def notify_kakao(df, recipients):

    for _, row in df.iterrows():

        fields = {

            "bidNtceNm": row.get("bidNtceNm", ""),

            "bidClseDt": row.get("bidClseDt", ""),

            "jntcontrctDutyRgnNm1": row.get("jntcontrctDutyRgnNm1", ""),

            "rgnDutyJntcontrctRt": row.get("rgnDutyJntcontrctRt", ""),

            "presmptPrce": row.get("presmptPrce", ""),

            "bidNtceNo": f"{row.get('bidNtceNo')} - {row.get('bidNtceOrd')}",

        }

        for phone in recipients:

            send_for_item(receiver=phone, fields=fields, dry_run=False)

