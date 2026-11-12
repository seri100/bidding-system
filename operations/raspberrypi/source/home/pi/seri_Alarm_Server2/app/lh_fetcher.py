
# -*- coding: utf-8 -*-

from pathlib import Path

import pandas as pd



BASE_DIR = Path("REDACTED_PRIVATE_VALUE")



def fetch_lh_from_excel():

    files = sorted(BASE_DIR.glob("LH_*.xlsx"), reverse=True)

    if not files:

        return []



    df = pd.read_excel(files[0], dtype=str)

    items = []



    for _, r in df.iterrows():

        items.append({

            "lhNo": r.get("공고번호") or r.get("lhNo"),

            "lhType": r.get("공사종류") or "공사",

            "lhNm": r.get("공고명"),

            "lhAmount": r.get("기초금액"),

            "lhLoc": r.get("지역"),

            "lhStartDate": r.get("입찰시작일"),

            "lhEndDate": r.get("입찰마감일"),

        })



    return items

