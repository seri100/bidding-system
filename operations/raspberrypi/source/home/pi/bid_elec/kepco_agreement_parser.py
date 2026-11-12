# -*- coding: utf-8 -*-

import re

import subprocess

from pathlib import Path



HWP5TXT = "/home/pi/.local/bin/hwp5txt"





def extract_hwp_text(hwp_path):

    hwp_path = Path(hwp_path)

    result = subprocess.run(

        [HWP5TXT, str(hwp_path)],

        stdout=subprocess.PIPE,

        stderr=subprocess.PIPE,

    )

    if result.returncode != 0:

        raise RuntimeError(

            result.stderr.decode("utf-8", errors="replace")

        )



    text = result.stdout.decode("utf-8", errors="replace")

    txt_path = hwp_path.with_suffix(".txt")

    txt_path.write_text(text, encoding="utf-8")

    return text, txt_path





def extract_joint_clause(text):

    for raw_line in text.splitlines():

        line = re.sub(r"\s+", " ", raw_line).strip()

        if re.search(

            r"공동(?:도급|수급|계약).{0,30}(?:사항|방법|여부)",

            line,

        ):

            return line

    return ""





def extract_agreement_deadline(text):

    normalized = re.sub(r"\s+", " ", text)



    date_time = (

        r"(20\d{2}\s*[./년-]\s*\d{1,2}\s*[./월-]\s*"

        r"\d{1,2}\s*(?:일|\.)?\s*"

        r"(?:\([^)]+\)\s*)?\d{1,2}\s*:\s*\d{2})"

    )



    patterns = (

        r"공동수급협정서.{0,100}?(?:접수|제출)?"

        r"\s*마감(?:일시)?\s*[:：]?\s*" + date_time,



        r"협정서.{0,100}?(?:접수|제출)?"

        r"\s*마감(?:일시)?\s*[:：]?\s*" + date_time,



        r"공동수급협정.{0,100}?(?:까지|기한)"

        r"\s*[:：]?\s*" + date_time,

    )



    for pattern in patterns:

        match = re.search(pattern, normalized)

        if match:

            return re.sub(r"\s+", " ", match.group(1)).strip()



    return ""





def analyze_hwp(hwp_path):

    text, txt_path = extract_hwp_text(hwp_path)

    clause = extract_joint_clause(text)

    deadline = extract_agreement_deadline(text)



    no_joint = bool(

        clause

        and re.search(r"해당(?:\s*사항)?\s*없음|비대상|불가|불허", clause)

    )



    if no_joint:

        joint_yn = "아니오"

        deadline = ""

        status = "공동도급 해당없음"

        next_action = "참가신청 후 투찰"

    elif deadline:

        joint_yn = "예"

        status = "공식 원문 확인완료"

        next_action = "협정 제출 후 투찰"

    elif re.search(

        r"공동수급협정서|공동도급|공동수급|공동계약",

        text,

    ):

        joint_yn = "확인필요"

        status = "원문에 정확한 협정마감 미확인"

        next_action = "공고문 원문에서 협정 적용 여부·마감 확인"

    else:

        joint_yn = "미기재"

        status = "공동수급 정보 미기재"

        next_action = "공고문 원문 확인"



    return {

        "공동수급여부": joint_yn,

        "공동수급방식": clause,

        "협정마감일시": deadline,

        "협정정보출처": "한전 SRM 공식 입찰공고문",

        "협정확인상태": status,

        "다음행동": next_action,

        "원문텍스트경로": str(txt_path),

    }

