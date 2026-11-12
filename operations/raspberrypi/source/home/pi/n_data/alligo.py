

import requests

import json

import datetime

from typing import List, Optional


# === SERI TEST-MODE LOG WRAP (auto-injected) ===

try:

    import os, requests as _rq

    if not getattr(_rq, "_seri_testmode_patch", False):

        _orig_post = _rq.post

        def _seri_post(url, *args, **kwargs):

            if os.getenv("TEST_MODE","0") == "1":

                phone = os.getenv("TEST_PHONE","REDACTED_PRIVATE_VALUE")

                print(f"[TEST_MODE] receiver forced to {phone} (alligo.py)")

            return _orig_post(url, *args, **kwargs)

        _rq.post = _seri_post

        _rq._seri_testmode_patch = True

except Exception:

    pass

# === END SERI TEST-MODE LOG WRAP ===





class Alligo:

    def __init__(self,

                 userid: str = 'seri825',

                 apikey: str = 'REDACTED_PRIVATE_VALUE',

                 senderkey: str = 'REDACTED_PRIVATE_VALUE',

                 plusid: Optional[str] = '@세리공영',

                 log_path: str = '/home/pi/n_data/alligoError.txt'):

        self.id = userid

        self.apikey = apikey

        self.token = None

        self.kakaoSender = senderkey

        self.plusid = plusid

        self.tokenUrl = 'REDACTED_PRIVATE_VALUE'

        self.templateListUrl = 'https://kakaoapi.aligo.in/akv10/template/list/'

        self.sendTalkUrl = 'REDACTED_PRIVATE_VALUE'

        self.alligoLog = log_path

        self._timeout = 10



    def _log(self, *args):

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg = f"[{ts}] " + " ".join(map(str, args))

        print(msg, flush=True)

        try:

            with open(self.alligoLog, 'a', encoding='utf-8') as f:

                f.write(msg + "\n")

        except Exception:

            pass



    def _post(self, url, data, timeout=None):

        timeout = timeout or self._timeout

        try:

            r = requests.post(url, data=data, timeout=timeout)
            print(f"[SEND] HTTP {r.status_code}", flush=True)

            # API 토큰 등 인증 응답 원문은 출력하지 않는다.

            print(f"[SEND] RESPONSE_RECEIVED bytes={len(r.content)}", flush=True)


            r.raise_for_status()

            try:

                return r.json()

            except Exception:

                return json.loads(r.text)

        except Exception as e:

            self._log(f"[HTTP_ERR] {url} :: {e}")

            return {"code": -9999, "message": str(e)}



    def getToken(self) -> Optional[str]:

        params = {'apikey': self.apikey, 'userid': self.id}

        for attempt in range(1, 6):

            res = self._post(self.tokenUrl, params)

            self._log(f"[TOKEN][try={attempt}] code={res.get('code') if isinstance(res, dict) else 'invalid'}")

            if isinstance(res, dict) and res.get('code') == 0:

                token = res.get('token') or res.get('urlencode')

                self.token = token

                return token

        self._log("[TOKEN][FAIL] 토큰 발급 실패")

        return None



    def getTempList(self) -> Optional[List[str]]:

        if not self.token and not self.getToken():

            return None

        params = {

            'apikey': self.apikey,

            'userid': self.id,

            'token': self.token,

            'senderkey': self.kakaoSender

        }

        res = self._post(self.templateListUrl, params)

        self._log(f"[TEMPLATES] resp={res}")

        if not isinstance(res, dict) or res.get('code') != 0:

            return None

        return [item.get('templtCode') for item in res.get('list', [])]



    def sendTalk(self,

                 tpl_code: str,

                 sender: str,

                 msgHead: str,

                 message: str,

                 receiverList: List[str]) -> bool:

        if not self.token and not self.getToken():

            return False



        params = {

            'apikey': self.apikey,

            'userid': self.id,

            'token': self.token,

            'senderkey': self.kakaoSender,

            'tpl_code': tpl_code,

            'sender': sender

        }

        if self.plusid:

            params['plusid'] = self.plusid



        # 알림톡 최종 실패 시 동일 수신자에게 SMS/LMS 자동 대체발송

        params['failover'] = 'Y'



        for idx, recv in enumerate(receiverList, start=1):

            params[f'receiver_{idx}'] = recv

            params[f'subject_{idx}'] = msgHead

            params[f'message_{idx}'] = message

            params[f'fsubject_{idx}'] = msgHead

            params[f'fmessage_{idx}'] = message



        self._log(f"[SEND][REQ] to={receiverList} tpl={tpl_code}")

        res = self._post(self.sendTalkUrl, params)

        self._log(f"[SEND][RESP-1] {res}")



        if not isinstance(res, dict) or res.get('code') != 0:

            res2 = self._post(self.sendTalkUrl, params)

            self._log(f"[SEND][RESP-2] {res2}")

            if not isinstance(res2, dict) or res2.get('code') != 0:

                self._log("[SEND][FAIL] 전송실패", res2)

                return False

        return True



    def test(self):

        self._log('[TEST] alive')

