
# -*- coding: utf-8 -*-

from pathlib import Path



try:

    from alligo import Alligo

except ImportError:

    Alligo = None





class LHNotifier:

    """

    LH 크롤링 결과 중 조건에 맞는 공고들을 알림톡으로 발송하는 모듈

    템플릿: TZ_4492

    """



    def __init__(self,

                 tpl_code="TZ_4492",

                 sender="REDACTED_PRIVATE_VALUE",

                 receivers=None):

        # 기본 수신번호 4명

        default_receivers = [

            "REDACTED_PRIVATE_VALUE",  # 2060

            "REDACTED_PRIVATE_VALUE",  # 3560

            "REDACTED_PRIVATE_VALUE",  # 0340

            "REDACTED_PRIVATE_VALUE",  # 2051

        ]

        self.tpl_code = tpl_code

        self.sender = sender

        self.receivers = receivers or default_receivers



        print(f"[LHNotifier] init tpl_code={self.tpl_code}, sender={self.sender}, receiver_count={len(self.receivers)}")



        if Alligo is None:

            print("[LHNotifier] alligo module not found. Notification disabled.")



        self.alligo = Alligo() if Alligo is not None else None



    def _build_region_text(self, row):

        """

        승인 템플릿의 고정 문구 '참가지역 :'은 유지하고,

        변수 값에 지역제한/지역의무 의미를 포함한다.

        """

        def collect(prefix):

            values = []



            aggregate = str(

                row.get(prefix)

                or ""

            ).strip()



            if aggregate:

                for item in aggregate.split(","):

                    item = item.strip()



                    if item and item not in values:

                        values.append(item)



            for region_no in range(1, 5):

                value = str(

                    row.get(

                        "{}{}".format(

                            prefix,

                            region_no,

                        )

                    )

                    or ""

                ).strip()



                if value and value not in values:

                    values.append(value)



            return values



        parts = []



        for value in collect("지역제한"):

            parts.append("지역제한_{}".format(value))



        for value in collect("지역의무"):

            parts.append("지역의무_{}".format(value))



        if not parts:

            # 과거 pending 자료 등 새 필드가 없는 행과 호환

            legacy_values = []



            for key in (

                "참가지역1",

                "참가지역2",

                "참가지역3",

                "참가지역4",

                "참가지역",

            ):

                value = str(

                    row.get(key)

                    or ""

                ).strip()



                if value and value not in legacy_values:

                    legacy_values.append(value)



            parts.extend(legacy_values)



        return ", ".join(parts) if parts else "없음"



    def make_notice_message(self, row):

        """

        TZ_4492 템플릿 구조에 맞는 본문 생성

        """

        bid_no = (row.get("공고번호") or "").strip()

        ind_type = (row.get("업종유형") or "").strip()

        title = (row.get("입찰공고건명") or "").strip()

        base_amt = (row.get("기초금액") or "").strip()

        recv_open = (row.get("입찰서접수개시일시") or "").strip()

        recv_close = (row.get("입찰서접수마감일시") or "").strip()

        region_text = self._build_region_text(row)



        lines = [

            "[세리공영]",

            "LH 입찰공고",

            f"공고번호 : {bid_no}",

            f"업종유형 : {ind_type}",

            f"입찰공고건명 : {title}",

            f"기초금액 : {base_amt}",

            f"참가지역 : {region_text}",

            f"입찰서접수개시일시 : {recv_open}",

            f"입찰서접수마감일시 : {recv_close}",

        ]

        if row.get("시공능력 제한 요약"):
            lines.append("시공능력 제한 : {}".format(row["시공능력 제한 요약"]))

        return "\n".join(lines)



    # __LH_FAILURE_SMS_CALLBACK_V1_BEGIN__
    def _notify_failure(self, message):
        """
        알림톡 오류 발생 시 lh_main.send_error_sms를 호출한다.
        실제 오류 SMS 수신자는 REDACTED_PRIVATE_VALUE이다.
        """
        callback = getattr(
            self,
            "error_callback",
            None,
        )

        if not callable(callback):
            print(
                "[LHNotifier][ERROR_ALERT] "
                "error_callback is unavailable: {}".format(
                    message
                )
            )
            return False

        try:
            result = callback(message)

            print(
                "[LHNotifier][ERROR_ALERT] "
                "SMS requested to REDACTED_PRIVATE_VALUE result={}".format(
                    result
                )
            )

            return result is not False

        except Exception as exc:
            print(
                "[LHNotifier][ERROR_ALERT] "
                "SMS request failed: {}: {}".format(
                    type(exc).__name__,
                    exc,
                )
            )

            return False
    # __LH_FAILURE_SMS_CALLBACK_V1_END__


    def send_notices(self, rows):

        """

        조건에 맞는 공고 목록(rows)을 받아서

        각 공고당 한 건씩 알림톡 발송

        """

        if self.alligo is None:

            print("[LHNotifier] alligo module missing. Send skipped.")

            # __LH_FAILURE_SMS_MODULE_MISSING_V1__
            self._notify_failure(
                "LH AlimTalk FAILED: alligo module missing"
            )

            return 0



        if not self.receivers:

            print("[LHNotifier] no receivers. Send skipped.")

            # __LH_FAILURE_SMS_NO_RECEIVER_V1__
            self._notify_failure(
                "LH AlimTalk FAILED: no receivers configured"
            )

            return 0



        if not rows:

            print("[LHNotifier] no target rows to send.")

            return 0



        print("[LHNotifier] getToken() called")

        # __LH_FAILURE_SMS_TOKEN_CHECK_V1__
        failed_bid_nos = []
        token_result = self.alligo.getToken()

        if (
            not token_result
            or not getattr(self.alligo, 'token', None)
        ):
            bid_nos = [
                str(row.get('공고번호') or '').strip()
                for row in rows
            ]

            bid_text = ','.join(
                value
                for value in bid_nos[:10]
                if value
            ) or 'unknown'

            alert_text = (
                'LH AlimTalk FAILED token/auth bids={}'
            ).format(bid_text)

            print(
                '[LHNotifier] token issuance failed: {}'.format(
                    bid_text
                )
            )

            self._notify_failure(alert_text)

            return 0



        subject = "REDACTED_PRIVATE_VALUE"



        sent_count = 0

        for row in rows:

            msg = self.make_notice_message(row)

            bid_no = row.get("공고번호")



            print(f"[LHNotifier] sendTalk tpl={self.tpl_code}, receiver_count={len(self.receivers)}, bid_no={bid_no}")

            result = self.alligo.sendTalk(

                self.tpl_code,

                self.sender,

                subject,

                msg,

                self.receivers,

            )



            ok = False

            if isinstance(result, bool):

                ok = result

            elif isinstance(result, dict):

                code = result.get("code") or result.get("result") or result.get("res_cd")

                print("[LHNotifier] result code:", code)

                ok = str(code) in ("1", "0000", "OK")



            if ok:

                print(f"[LHNotifier] Notification sent successfully for bid_no={bid_no}")

                sent_count += 1

            else:

                print(
                    f"[LHNotifier] Notification send failed for bid_no={bid_no}"
                )

                # __LH_FAILURE_SMS_ROW_TRACK_V1__
                if bid_no:
                    failed_bid_nos.append(
                        str(bid_no).strip()
                    )



        # __LH_FAILURE_SMS_BATCH_ALERT_V1__
        if failed_bid_nos:
            bid_text = ','.join(
                failed_bid_nos[:10]
            ) or 'unknown'

            alert_text = (
                'LH AlimTalk FAILED bids={} sent={}/{}'
            ).format(
                bid_text,
                sent_count,
                len(rows),
            )

            self._notify_failure(alert_text)

        print(
            "[LHNotifier] total sent (logical ok) =",
            sent_count,
        )

        return sent_count

