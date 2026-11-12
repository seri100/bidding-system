# alligo_client.py  — INSERT 로직 패치 버전

# -*- coding: utf-8 -*-



import pymysql

import logging

from datetime import datetime



class AlligoClient:

    def __init__(self, apikey, userid, token, kakao_sender, send_url):

        self.apikey = apikey

        self.userid = userid

        self.token = token

        self.kakao_sender = kakao_sender

        self.send_url = send_url



        self.db_host = "REDACTED_PRIVATE_VALUE"

        self.db_user = "root"

        self.db_pass = ""          # 필요 시 .env 값 사용 가능

        self.db_name = "kakao"



    # ------------------------------------------------------

    # *** 핵심 패치 ***

    #  bid_no = lhNo+"-00" 형태로 DB 정확히 저장

    # ------------------------------------------------------

    def _insert_send_log(

        self,

        bid_no,

        bid_name,

        tpl_code,

        phone,

        send_type,

        send_result,

        send_msg,

    ):

        """senddata 테이블 insert — bid_no 를 “XXXXXXX-00” 규칙으로 저장"""

        try:

            conn = pymysql.connect(

                host=self.db_host,

                user=self.db_user,

                password=self.db_pass,

                database=self.db_name,

                charset="utf8mb4",

            )

            cur = conn.cursor()



            # ★ 핵심: bid_no 강제 정규화

            # 2503218 → 2503218-00

            # 2503218-00 → 그대로 유지

            bno = str(bid_no).strip()

            if bno and "-" not in bno:

                bno = bno + "-00"



            q = """

                INSERT INTO senddata

                (bid_no, bidNtceCode, bid_name, regDate,

                 tpl_code, phone, send_type, send_result, send_msg, created_at)

                VALUES (%s, %s, %s, NOW(),

                        %s, %s, %s, %s, %s, NOW())

            """



            cur.execute(

                q,

                (

                    bno,          # bid_no

                    bno,          # bidNtceCode 동일하게 저장

                    bid_name,     # bid_name

                    tpl_code,

                    phone,

                    send_type,

                    send_result,

                    send_msg,

                ),

            )



            conn.commit()

            cur.close()

            conn.close()



            logging.info(f"[DB] insert senddata OK — {bno}")

        except Exception as e:

            logging.error(f"[DB] insert error: {e}")



    # ------------------------------------------------------

    # 알리고 발송 함수

    # ------------------------------------------------------

    def sendTalk(self, bid_code, tpl_code, sender, msgHead, message, receiverList):

        """

        실제 알리고 API 발송 (축약 버전)

        """

        # 여기서 bid_code = 공고번호

        # DB에는 bid_no 로 들어감

        send_results = {"sent_ok": 0, "skipped": 0}



        for phone in receiverList:

            # === 실제 발송은 생략 ===

            api_res = {"result_code": "OK", "message": "SKIPPED (stub)"}



            # === DB 기록 ===

            self._insert_send_log(

                bid_no=bid_code,

                bid_name=msgHead,

                tpl_code=tpl_code,

                phone=phone,

                send_type="KAKAO",

                send_result=api_res.get("result_code"),

                send_msg=message,

            )



            send_results["sent_ok"] += 1



        return send_results


