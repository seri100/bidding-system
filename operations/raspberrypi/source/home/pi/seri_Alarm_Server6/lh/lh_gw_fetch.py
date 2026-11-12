
# -*- coding: utf-8 -*-

from __future__ import print_function



import argparse

import os

import xml.etree.ElementTree as ET

from datetime import datetime, timedelta

try:

    from urllib.parse import unquote

except ImportError:

    from urllib import unquote



import requests





GW_URL = "https://apis.data.go.kr/B552555/OpenBidInfoList/getOpenBidInfo"

DEFAULT_KEY_FILE = "/home/pi/n_data/bid_api_key.txt"





def clean(value):

    return " ".join(str(value or "").split()).strip()





def read_service_key(path=DEFAULT_KEY_FILE):

    env_key = clean(os.environ.get("LH_GW_SERVICE_KEY"))

    if env_key:

        return unquote(env_key)



    with open(path, "r") as f:

        key = clean(f.read())



    if not key:

        raise RuntimeError("공공데이터 인증키가 비어 있습니다: {}".format(path))



    return unquote(key)





def element_dict(element):

    return {

        child.tag: clean(child.text)

        for child in list(element)

    }





def api_item_to_detail(item):

    detail = {

        "공고번호": clean(item.get("bidNum")),

        "공고차수": clean(item.get("bidDegree")),

        "업무구분": clean(item.get("cstrtnJobGbNm")),

        "공고종류": clean(item.get("bidKind")),

        "입찰공고건명": clean(item.get("bidnmKor")),

        "담당지역본부": clean(item.get("zoneHqCd")),

        "입찰진행상태": clean(item.get("bidProgrsStatus")),

        "입찰계약방법": clean(item.get("tndrCtrctMedCd")),

        "입찰공고일": clean(item.get("tndrbidRegDt")),

        "추정가격": clean(item.get("presmtPrc")),

        "부가가치세": clean(item.get("addtTax")),

        "설계가격": clean(item.get("designPrc")),

        "기초금액": clean(item.get("fdmtlAmt")),

        "낙찰자선정방법": clean(item.get("sunjungNm")),

        "공동수급협정서 접수/구성 방식": clean(item.get("gongdongNm")),

        "공동수급협정서접수마감일시": clean(

            item.get("cooperdocAcptEndDtm")

        ),

        "입찰서접수개시일시": clean(item.get("tndrdocAcptBgninDtm")),

        "입찰서접수마감일시": clean(item.get("tndrdocAcptEndDtm")),

        "개찰일시": clean(item.get("openDtm")),

        "가격점수제외금액(A)": clean(item.get("prcscoreExclusAmt")),

    }



    region_limit = []

    region_joint = []



    for number in range(1, 5):

        limit_value = clean(item.get("zoneRstrct{}".format(number)))

        joint_value = clean(item.get("vndrrstrctNm{}".format(number)))



        detail["지역제한{}".format(number)] = limit_value

        detail["지역의무{}".format(number)] = joint_value



        # 기존 parser와의 호환: 참가지역1~4는 지역제한을 우선 적용

        detail["참가지역{}".format(number)] = limit_value



        if limit_value and limit_value not in region_limit:

            region_limit.append(limit_value)



        if joint_value and joint_value not in region_joint:

            region_joint.append(joint_value)



    detail["지역제한"] = ", ".join(region_limit)

    detail["지역의무"] = ", ".join(region_joint)



    combined = []

    for value in region_limit + region_joint:

        if value and value not in combined:

            combined.append(value)

    detail["참가지역"] = ", ".join(combined)



    licenses = []

    for group_no in range(1, 11):

        for license_no in range(1, 11):

            key = "req{}Reqlic{}Nm".format(group_no, license_no)

            value = clean(item.get(key))

            if value and value not in licenses:

                licenses.append(value)



    detail["요구면허"] = " / ".join(licenses)

    for index, value in enumerate(licenses[:10], 1):

        detail["요구면허{}".format(index)] = value



    return detail





class LHGatewayClient(object):

    def __init__(self, key_file=DEFAULT_KEY_FILE, timeout=(10, 60)):

        self.service_key = read_service_key(key_file)

        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update({

            "User-Agent": "LHAuto-GW/1.0"

        })



    def fetch_page(self, start_date, end_date, page_no=1, num_rows=100):

        params = {

            "serviceKey": self.service_key,

            "pageNo": str(page_no),

            "numOfRows": str(num_rows),

            "tndrbidRegDtStart": start_date,

            "tndrbidRegDtEnd": end_date,

        }



        response = self.session.get(

            GW_URL,

            params=params,

            timeout=self.timeout,

        )

        response.raise_for_status()



        xml_text = response.content.decode("cp949")
        xml_text = xml_text.replace("encoding=\"EUC-KR\"", "encoding=\"UTF-8\"", 1)
        root = ET.fromstring(xml_text.encode("utf-8"))

        result_code = clean(root.findtext("./header/resultCode"))

        result_message = clean(root.findtext("./header/resultMsg"))



        if result_code != "00":

            raise RuntimeError(

                "LH GW API 오류: {} {}".format(result_code, result_message)

            )



        body = root.find("./body")

        if body is None:

            raise RuntimeError("LH GW API 응답에 body가 없습니다.")



        items = [

            element_dict(node)

            for node in body.findall("./item")

        ]



        return {

            "items": items,

            "total_count": int(clean(body.findtext("totalCount")) or 0),

            "page_no": int(clean(body.findtext("pageNo")) or page_no),

            "num_rows": int(clean(body.findtext("numOfRows")) or num_rows),

        }



    def fetch_all(self, start_date, end_date, num_rows=100):

        rows = []

        page_no = 1



        while True:

            page = self.fetch_page(

                start_date,

                end_date,

                page_no=page_no,

                num_rows=num_rows,

            )

            rows.extend(page["items"])



            print(

                "[LH_GW] page={} rows={} total={}".format(

                    page_no,

                    len(rows),

                    page["total_count"],

                )

            )



            if len(rows) >= page["total_count"] or not page["items"]:

                break



            page_no += 1



        return rows





def main():

    today = datetime.now().date()

    parser = argparse.ArgumentParser()

    parser.add_argument(

        "--start",

        default=(today - timedelta(days=14)).strftime("%Y%m%d"),

    )

    parser.add_argument(

        "--end",

        default=today.strftime("%Y%m%d"),

    )

    parser.add_argument("--show", type=int, default=10)

    args = parser.parse_args()



    client = LHGatewayClient()

    raw_rows = client.fetch_all(args.start, args.end)

    details = [api_item_to_detail(row) for row in raw_rows]



    facility_rows = [

        row for row in details

        if "시설공사" in row.get("업무구분", "")

    ]



    target_words = (

        "소방", "기계설비", "가스시설",

        "기계가스설비", "기계설비·가스",

    )

    target_rows = [

        row for row in facility_rows

        if any(

            word in "{} {}".format(

                row.get("입찰공고건명", ""),

                row.get("요구면허", ""),

            )

            for word in target_words

        )

    ]



    print("[LH_GW] 기간={}~{}".format(args.start, args.end))

    print("[LH_GW] 전체={} 시설공사={} 대상후보={}".format(

        len(details), len(facility_rows), len(target_rows)

    ))



    for row in target_rows[:max(args.show, 0)]:

        print(

            "[LH_GW_ITEM] {}-{} | {} | 추정가격={} | 지역제한={} | 지역의무={} | 면허={}".format(

                row.get("공고번호"),

                row.get("공고차수"),

                row.get("입찰공고건명"),

                row.get("추정가격"),

                row.get("지역제한") or "없음",

                row.get("지역의무") or "없음",

                row.get("요구면허") or "없음",

            )

        )





if __name__ == "__main__":

    main()

