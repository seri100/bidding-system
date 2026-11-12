
# -*- coding: utf-8 -*-

import os

import json

import requests

from pathlib import Path





class AlligoClient:

    def __init__(self):

        # .env 로드(아주 단순 버전)

        self._load_env(Path("/home/pi/seri_Alarm_Server2/.env"))



        self.userid = os.getenv("ALLIGO_USERID", "").strip()

        self.apikey = os.getenv("ALLIGO_APIKEY", "").strip()

        self.senderkey = os.getenv("ALLIGO_SENDERKEY", "").strip()

        self.kakao_channel_id = os.getenv("KAKAO_CHANNEL_ID", "").strip()



        self.token = None



        self.token_url = "REDACTED_PRIVATE_VALUE"

        self.template_list_url = "https://kakaoapi.aligo.in/akv10/template/list/"

        self.send_talk_url = "REDACTED_PRIVATE_VALUE"



        # SSL 인증서 문제 있으면 True로 그대로 두고,

        # 나중에 ca_bundle.pem 경로를 지정하는 방식으로 바꿀 수 있음.

        self.verify = True



        if not self.userid or not self.apikey:

            raise RuntimeError("ALLIGO_USERID / ALLIGO_APIKEY 가 비어있습니다. .env 파일을 확인하세요.")



    def _load_env(self, env_path: Path):

        if not env_path.exists():

            return

        for line in env_path.read_text(encoding="utf-8").splitlines():

            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:

                continue

            k, v = line.split("=", 1)

            os.environ.setdefault(k.strip(), v.strip())



    def get_token(self) -> str:

        params = {"apikey": self.apikey, "userid": self.userid}

        r = requests.post(self.token_url, data=params, timeout=15, verify=self.verify)

        result = r.json()

        if result.get("code") != 0:

            raise RuntimeError(f"Alligo token fail: {result}")

        self.token = result.get("urlencode")

        return self.token



    def get_template_codes(self):

        if not self.token:

            self.get_token()



        if not self.senderkey:

            raise RuntimeError("ALLIGO_SENDERKEY(senderkey)가 비어있습니다. .env 값을 확인하세요.")



        params = {

            "apikey": self.apikey,

            "userid": self.userid,

            "token": self.token,

            "senderkey": self.senderkey,  # ✅ 이게 없으면 -99 발생

        }



        r = requests.post(self.template_list_url, data=params, timeout=15, verify=self.verify)

        result = r.json()

        if result.get("code") != 0:

            raise RuntimeError(f"Alligo template list fail: {result}")



        return [x.get("templtCode") for x in result.get("list", [])]



    def send_alimtalk(self, tpl_code: str, sender: str, msg_head: str, message: str, receivers: list) -> bool:

        if not self.token:

            self.get_token()



        if not self.senderkey:

            raise RuntimeError("ALLIGO_SENDERKEY(senderkey)가 비어있습니다. .env 값을 확인하세요.")



        params = {

            "apikey": self.apikey,

            "userid": self.userid,

            "token": self.token,

            "senderkey": self.senderkey,

            "tpl_code": tpl_code,

            "sender": sender,

        }



        # 다건 전송 포맷

        for idx, rcv in enumerate(receivers, start=1):

            params[f"receiver_{idx}"] = rcv

            params[f"subject_{idx}"] = msg_head

            params[f"message_{idx}"] = message



        r = requests.post(self.send_talk_url, data=params, timeout=15, verify=self.verify)

        result = r.json()

        if result.get("code") != 0:

            raise RuntimeError(f"Alligo send fail: {result}")

        return True

