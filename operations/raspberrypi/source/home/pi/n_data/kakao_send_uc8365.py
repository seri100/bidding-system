# -*- coding: utf-8 -*-



from __future__ import print_function



import os



from alligo import Alligo





TEMPLATE_CODE = "UC_8365"





def clean(value, default=""):

    if value is None:

        return default



    text = str(value).strip()



    if not text or text.lower() in (

        "nan",

        "none",

        "null",

    ):

        return default



    return text





def send_for_item(receiver, fields, dry_run=False):

    receiver = clean(receiver)

    bid_no = clean(fields.get("bid_no"), "미확인")

    bid_name = clean(fields.get("bid_name"), "미확인")

    license_name = clean(fields.get("license"), "미확인")

    amount = clean(fields.get("amount"), "0원")

    limit_type = clean(fields.get("limit_type"), "미확인")



    if amount and not amount.endswith("원"):

        amount += "원"



    message = (

        "[세리공영] 한국도로공사 입찰 알림\n"

        "공고번호 : %s\n"

        "공고명 : %s\n"

        "입찰면허 : %s\n"

        "설계금액 : %s\n"

        "제한유형 : %s"

        % (

            bid_no,

            bid_name,

            license_name,

            amount,

            limit_type,

        )

    )



    if (

        os.environ.get(

            "HARD_NO_SEND",

            "",

        ).strip()

        == "1"

    ):

        print(

            "[HARD_NO_SEND] blocked send: receiver=%s"

            % receiver

        )

        return {

            "ok": False,

            "blocked": True,

            "receiver": receiver,

            "template_id": TEMPLATE_CODE,

        }



    if dry_run:

        print(

            "[UC_8365][DRY] receiver=%s"

            % receiver

        )

        print(message)



        return {

            "ok": True,

            "receiver": receiver,

            "template_id": TEMPLATE_CODE,

            "dry_run": True,

            "message": message,

        }



    alligo = Alligo()

    sender = os.getenv(

        "ALLIGO_SENDER",

        "REDACTED_PRIVATE_VALUE",

    ).strip()



    raw_result = alligo.sendTalk(

        tpl_code=TEMPLATE_CODE,

        sender=sender,

        msgHead="[세리공영] 한국도로공사 입찰 알림",

        message=message,

        receiverList=[receiver],

    )



    return {

        "ok": bool(raw_result),

        "receiver": receiver,

        "template_id": TEMPLATE_CODE,

        "dry_run": False,

        "raw_result": raw_result,

    }

