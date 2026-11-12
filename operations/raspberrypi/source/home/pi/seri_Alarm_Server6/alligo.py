
import requests

import json

import datetime

import time



def _mask(s: str, keep=4) -> str:

    s = str(s or "")

    return s[:keep] + "*" * max(0, len(s) - keep)



# __ALIGO_SHARED_CONFIG_ONLY_V1_BEGIN__
ALIGO_SHARED_CONFIG_FILE = "/home/pi/n_data/aligo_sms.json"


def _load_shared_aligo_credentials():
    with open(
        ALIGO_SHARED_CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file_obj:
        data = json.load(file_obj)

    if not isinstance(data, dict):
        raise RuntimeError(
            "Aligo shared configuration must be a JSON object"
        )

    user_id = str(
        data.get("user_id")
        or data.get("userid")
        or ""
    ).strip()

    api_key = str(
        data.get("key")
        or data.get("apikey")
        or data.get("api_key")
        or ""
    ).strip()

    if not user_id or not api_key:
        raise RuntimeError(
            "Aligo shared configuration is missing user_id or key"
        )

    return {
        "user_id": user_id,
        "key": api_key,
    }
# __ALIGO_SHARED_CONFIG_ONLY_V1_END__


class Alligo:

    def __init__(self):

        credentials = _load_shared_aligo_credentials()
        self.id = credentials["user_id"]

        self.apikey = credentials["key"]

        self.token = None

        self.kakaoSender = 'REDACTED_PRIVATE_VALUE'

        self.kakaoID = '@세리공영'

        # 토큰 TTL 60초, 전송 직전에 발급

        self.tokenUrl = 'https://kakaoapi.aligo.in/akv10/token/create/60/s/'

        self.templateListUrl = 'https://kakaoapi.aligo.in/akv10/template/list/'

        self.sendTalkUrl = 'REDACTED_PRIVATE_VALUE'

        self.alligoLog = 'alligoError.txt'



    def getToken(self, max_retry=2):

        """전송 직전에 토큰 발급. 응답의 'token' 필드를 사용."""

        params = {'apikey': self.apikey, 'userid': self.id}

        for attempt in range(1, max_retry + 1):

            r = requests.post(self.tokenUrl, data=params, timeout=10)

            try:

                res = r.json()

            except Exception:

                self._elog(f"[TOKEN] invalid json: {r.text[:200]}")

                res = {'code': -999, 'message': 'invalid json'}

            if res.get('code') == 0 and res.get('token'):

                self.token = res['token']

                return self.token

            self._elog(f"[TOKEN] fail attempt={attempt} code={res.get('code')} msg={res.get('message')}")

            time.sleep(1)

        return None



    def getTempList(self):

        """템플릿 목록 조회(필요 시)."""

        if not self.token and not self.getToken():

            return False

        params = {'apikey': self.apikey, 'userid': self.id, 'token': self.token, 'senderkey': self.kakaoSender}

        r = requests.post(self.templateListUrl, data=params, timeout=10)

        try:

            result = r.json()

        except Exception:

            self._elog(f"[TEMPLATE] invalid json: {r.text[:200]}")

            return False

        if result.get('code') != 0:

            self._elog(f"[TEMPLATE] code={result.get('code')} msg={result.get('message')}")

            return False

        return [i['templtCode'] for i in result.get('list', [])]



    def sendTalk(self, tpl_code, sender, msgHead, message, receiverList, max_retry=2):

        """알림톡 전송: 토큰 즉시 발급 + data= 전송 + 1회 재시도."""

        if not self.getToken():

            self._elog("[SEND] token create failed")

            return False



        params = {

            'apikey': self.apikey, 'userid': self.id, 'token': self.token,

            'senderkey': self.kakaoSender, 'tpl_code': tpl_code, 'sender': sender

        }

        for idx, recv in enumerate(receiverList, start=1):

            params[f'receiver_{idx}'] = recv

            params[f'subject_{idx}']  = msgHead

            params[f'message_{idx}']  = message



        for attempt in range(1, max_retry + 1):

            resp = requests.post(self.sendTalkUrl, data=params, timeout=15)  # 중요: data=

            try:

                result = resp.json()

            except Exception:

                result = {'code': -999, 'message': resp.text[:200]}



            code = result.get('code')

            msg = result.get('message')

            self._ilog(f"[SEND] attempt={attempt} code={code} msg={msg} recv_cnt={len(receiverList)}")



            if code == 0:

                return True



            # 토큰/인증/포맷성 오류 추정 시 1회 재시도(토큰 재발급)

            if attempt < max_retry and code in (-10, -101, -110, -120, -998, -999):

                time.sleep(1)

                if not self.getToken():

                    break

                params['token'] = self.token

                continue



            self._wlog(f"code={code} msg={msg}")

            return False



        return False



    def _wlog(self, text):

        with open(self.alligoLog, 'a', encoding='utf-8') as f:

            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            f.write('\n')

            f.write(str(text))

            f.write('\n')



    def _elog(self, text):

        self._wlog(text)



    def _ilog(self, text):

        with open(self.alligoLog.replace('.txt', '_info.txt'), 'a', encoding='utf-8') as f:

            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            f.write(' ')

            f.write(str(text))

            f.write('\n')



    def test(self):

        print('1')

