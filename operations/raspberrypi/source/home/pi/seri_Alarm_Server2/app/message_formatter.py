
# -*- coding: utf-8 -*-



def render_template_text(template_text: str, variables: dict) -> str:

    """

    알리고 알림톡은 메시지 본문에 #{var} 형태로 변수를 넣으면 치환됨.

    여기서는 "미리보기"를 위해 실제 문자열로 치환해주는 용도(선택).

    실제 전송은 #{lhNo} 형태 그대로 보내도 됨.

    """

    msg = template_text

    for k, v in variables.items():

        msg = msg.replace(f"#{{{k}}}", str(v))

    return msg





def build_lh_message_preview(vars_dict: dict) -> str:

    # 템플릿 본문을 우리가 직접 만들어서 보내는 방식 (가장 단순)

    # (템플릿 심사된 문구와 달라도, 보통은 tpl_code 기준으로 검수된 형식이 적용됨)

    return (

        f"[세리공영]\n"

        f"LH 공고번호 : {vars_dict.get('lhNo','')}\n"

        f"유형 : {vars_dict.get('lhType','')}\n"

        f"공고명 : {vars_dict.get('lhNm','')}\n"

        f"금액 : {vars_dict.get('lhAmount','')}\n"

        f"지역 : {vars_dict.get('lhLoc','')}\n"

        f"접수시작 : {vars_dict.get('lhStartDate','')}\n"

        f"접수마감 : {vars_dict.get('lhEndDate','')}"

    )

