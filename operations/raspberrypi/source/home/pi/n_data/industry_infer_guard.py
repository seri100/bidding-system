
# -*- coding: utf-8 -*-

"""

업종코드 없는 공고 안전 분류 모듈

- 강한 키워드만 업종 추정

- 애매하면 분류하지 않음

"""



from pathlib import Path

from datetime import datetime

import pandas as pd





def _txt(v):

    return str(v or "").strip()





def infer_industry_safe(row):

    raw = row.get("원문") or row



    title = _txt(raw.get("bidNtceNm") or row.get("공고명"))

    files = " ".join(

        _txt(raw.get(f"ntceSpecFileNm{i}"))

        for i in range(1, 11)

    )



    blob = f"{title} {files}"



    # 강한 키워드만 인정

    if "전문소방시설공사업" in blob or "소방설비공사" in blob or "소방공사" in blob:

        return "0038", "소방", "strong"



    if "전기공사" in blob or "(전기)" in blob:

        return "0037", "전기", "strong"



    if "정보통신공사" in blob or "통신공사" in blob:

        return "0039", "정보통신", "strong"



    if "기계설비공사" in blob or "(기계설비)" in blob:

        return "6202", "기계설비", "strong"



    # 단순 '기계', '건축,기계'는 위험하므로 미분류

    return "", "", "unknown"





def apply_industry_infer_guard(rows, out_dir="/mnt/vol1/bid/n_data/review"):

    Path(out_dir).mkdir(parents=True, exist_ok=True)



    review = []

    changed = 0



    for row in rows:

        raw = row.get("원문") or row



        ind = _txt(

            raw.get("indstrytyCd")

            or row.get("공고업종코드")

            or row.get("indstrytyCd")

        )



        if ind:

            continue



        guessed, name, confidence = infer_industry_safe(row)



        bid_no = _txt(raw.get("bidNtceNo") or row.get("공고번호"))

        bid_ord = _txt(raw.get("bidNtceOrd") or row.get("차수") or "000")

        title = _txt(raw.get("bidNtceNm") or row.get("공고명"))



        review.append({

            "공고번호": bid_no,

            "차수": bid_ord,

            "공고명": title,

            "추정업종코드": guessed,

            "추정업종명": name,

            "확신도": confidence,

            "게시일시": _txt(raw.get("bidNtceDt") or row.get("게시일시")),

            "마감일시": _txt(raw.get("bidClseDt") or row.get("입찰마감일시")),

            "파일명1": _txt(raw.get("ntceSpecFileNm1")),

            "파일명2": _txt(raw.get("ntceSpecFileNm2")),

            "파일명3": _txt(raw.get("ntceSpecFileNm3")),

        })



        if guessed and confidence == "strong":

            row["공고업종코드"] = guessed

            row["공고업종명"] = name

            row["_industry_inferred"] = "1"

            row["_industry_infer_confidence"] = confidence

            changed += 1



    if review:

        fn = Path(out_dir) / f"업종미확정_검토_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        pd.DataFrame(review).to_excel(fn, index=False)



    return rows, changed, len(review)

