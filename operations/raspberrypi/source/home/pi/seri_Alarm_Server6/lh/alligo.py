import requests
import json
import datetime


# __LH_SHARED_ALIGO_CONFIG_V2_BEGIN__
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
# __LH_SHARED_ALIGO_CONFIG_V2_END__


class Alligo:
    def __init__(self):
        credentials = _load_shared_aligo_credentials()
        self.id = credentials["user_id"]
        self.apikey = credentials["key"]
        self.token = None
        self.kakaoSender = 'REDACTED_PRIVATE_VALUE'
        self.kakaoID = '@세리공영'
        self.tokenUrl = 'REDACTED_PRIVATE_VALUE'
        self.templateListUrl = 'https://kakaoapi.aligo.in/akv10/template/list/'
        self.sendTalkUrl = 'REDACTED_PRIVATE_VALUE'
        self.alligoLog = 'alligoError.txt'

    def getToken(self):
        cnt = 0
        params = {'apikey': self.apikey, 'userid': self.id}
        response = requests.post(self.tokenUrl, params)
        result = json.loads(response.text)
        while result['code'] != 0:
            response = requests.post(self.tokenUrl, params)
            result = json.loads(response.text)
            cnt = cnt + 1
            if cnt > 10:
                return False
        self.token = result['urlencode']
        return result['urlencode']

    def getTempList(self):
        cnt = 0
        params = {'apikey': self.apikey, 'userid': self.id, 'token': self.token, 'senderkey': self.kakaoSender}
        response = requests.post(self.templateListUrl, params)
        result = json.loads(response.text)
        resList = []
        while result['code'] != 0:
            response = requests.post(self.templateListUrl, params)
            result = json.loads(response.text)
            cnt = cnt + 1
            if cnt > 10:
                return False
        for i in result['list']:
            resList.append(i['templtCode'])

        return resList

    def sendTalk(self, tpl_code, sender, msgHead, message, receiverList):
        cnt = 0
        params = {'apikey': self.apikey, 'userid': self.id, 'token': self.token, 'senderkey': self.kakaoSender,
                  'tpl_code': tpl_code, 'sender': sender}
        recvCnt = 1
        for i in receiverList:
            params['receiver_' + str(recvCnt)] = i
            params['subject_' + str(recvCnt)] = msgHead
            params['message_' + str(recvCnt)] = message
            recvCnt = recvCnt + 1

        # __LH_MASK_ALLIGO_PARAMS_V1__
        print(
            '[Alligo] sendTalk request prepared '
            'tpl_code={} receiver_count={}'.format(
                tpl_code,
                len(receiverList),
            )
        )

        response = requests.post(self.sendTalkUrl, params)
        result = json.loads(response.text)
        if result['code'] != 0:
            response = requests.post(self.sendTalkUrl, params)
            result = json.loads(response.text)
            if result['code'] != 0:
                print(f"전송실패했습니다. 로그 참조. code: {result['code']}")
                # TODO 로그 작성하는 코드 쓰기.
                f = open(self.alligoLog, 'a')
                f.write(datetime.datetime.now().strftime("%Y-%m-%d :: %H-%M-%S"))
                f.write('\n')
                f.write(result['message'])
                f.write('\n')
                f.close()
                return False
        return True

    def test(self):
        print('1')
