
# -*- coding: utf-8 -*-

"""

kakao_send_tb0485.py (shim)

- lh_notify_only.py 가 `from kakao_send_tb0485 import send_for_item` 를 기대하므로,

  그에 맞춰 send_for_item()을 제공한다.

- 실제 전송은 /home/pi/seri_Alarm_Server6/alligo.py 의 Alligo 클래스를 사용한다.

"""



import os

import sys

from typing import Any, Dict, List, Union



# ✅ alligo.py 가 있는 상위 폴더(/home/pi/seri_Alarm_Server6)를 PYTHONPATH에 강제로 추가

BASE_DIR = "/home/pi/seri_Alarm_Server6"

if BASE_DIR not in sys.path:

    sys.path.insert(0, BASE_DIR)



from alligo import Alligo  # /home/pi/seri_Alarm_Server6/alligo.py



# 기본값들 (필요하면 여기만 바꿔도 됨)

TPL_CODE = os.environ.get("ALIGO_TPL_CODE", "TB_0485")

SENDER   = os.environ.get("ALIGO_SENDER", "REDACTED_PRIVATE_VALUE")  # 너가 쓰는 발신번호로

MSG_HEAD = os.environ.get("ALIGO_MSG_HEAD", "[세리공영]")



def send_for_item(

    receiver: Union[str, List[str]],

    fields: Union[str, Dict[str, Any]],

    dry_run: bool = False

) -> bool:

    """

    receiver: "010..." 또는 ["010..", "010.."]

    fields:   (1) 문자열 메시지 또는

              (2) dict - {'message': '...', 'msgHead': '...'} 같은 형태

    """

    # 수신자 리스트 정리

    if isinstance(receiver, str):

        recv_list = [receiver]

    else:

        recv_list = list(receiver)



    # 메시지/헤더 정리

    if isinstance(fields, str):

        message = fields

        msg_head = MSG_HEAD

    else:

        message = str(fields.get("message") or fields.get("msg") or "")

        msg_head = str(fields.get("msgHead") or fields.get("subject") or MSG_HEAD)



    message = message.strip()

    if not message:

        # 메시지가 비면 전송 안 함

        return False



    if dry_run:

        print("[DRYRUN] to=", recv_list)

        print(message)

        return True



    a = Alligo()

    return bool(a.sendTalk(

        tpl_code=TPL_CODE,

        sender=SENDER,

        msgHead=msg_head,

        message=message,

        receiverList=recv_list,

    ))

