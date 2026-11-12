
"""

notifier.py

- Alligo 문자 발송 모듈 (안전한 새판 뼈대)

"""



from typing import List, Dict, Any

from app.config import load_config

from app.logger import setup_logger



try:

    from alligo import Alligo

except Exception:

    Alligo = None





logger = setup_logger("notifier")





class Notifier:

    def __init__(self):

        self.cfg = load_config()



        if Alligo is None:

            raise RuntimeError("Alligo 모듈을 불러올 수 없습니다 (alligo.py 확인 필요)")



        self.client = Alligo(

            self.cfg.alligo_api_key,

            self.cfg.alligo_user_id,

        )



    def send_sms(

        self,

        receivers: List[str],

        message: str,

        title: str = "세리공영",

    ) -> Dict[str, Any]:

        """

        문자 발송 (공통 인터페이스)

        """

        if not receivers:

            logger.info("[SKIP] 수신자 없음")

            return {"status": "skip", "reason": "no receivers"}



        try:

            logger.info(

                f"[SEND] to={receivers} len={len(message)}"

            )



            result = self.client.send(

                receivers=",".join(receivers),

                message=message,

                title=title,

            )



            logger.info(f"[SUCCESS] result={result}")

            return {"status": "success", "result": result}



        except Exception as e:

            logger.exception("[ERROR] 문자 발송 실패")

            return {"status": "error", "error": str(e)}

