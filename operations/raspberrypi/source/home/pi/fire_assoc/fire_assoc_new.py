import os

import re

import time

import pandas as pd

from datetime import datetime

from urllib.parse import urlencode

from urllib.request import Request, urlopen



BASE_URL = "https://freg.ekffa.or.kr/board/gongSiList.do"

PHONE_BASE_URL = "https://www.ekffa.or.kr/fe/member/NR_listCompany.do"

SAVE_DIR = "/mnt/vol1/소방협회"

CACHE_FILE = "/home/pi/fire_assoc/ekffa_company_phone_cache.csv"

MATCH_LOG = "/home/pi/fire_assoc/logs/phone_match_latest.csv"



FILTER_DATE = "2026-03-01"

FILTER_DATE_DT = datetime.strptime(FILTER_DATE, "%Y-%m-%d") if FILTER_DATE else None

MAX_PAGES = 500

PHONE_MAX_PAGES = 800

PHONE_CACHE_HOURS = 18



BASE_QUERY = {

    "menuId": "MW0505",

    "redirectYn": "N",

    "date": "12",

    "upKindcode": "",

    "searchGubun": "companyName",

    "searchText": "",

}



REGIONS = [

    "서울특별시", "부산광역시", "대구광역시", "인천광역시",

    "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",

    "경기도", "강원특별자치도", "강원도", "충청북도", "충청남도",

    "전북특별자치도", "전라북도", "전라남도",

    "경상북도", "경상남도", "제주특별자치도"

]

region_pattern = re.compile("|".join(re.escape(r) for r in REGIONS))





def build_url(page_no):

    q = BASE_QUERY.copy()

    q["currentPageNo"] = str(page_no)

    return BASE_URL + "?" + urlencode(q)





def fetch_html(url, retries=3):

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            req = Request(

                url,

                headers={

                    "User-Agent": "Mozilla/5.0",

                    "Accept-Language": "ko-KR,ko;q=0.9",

                },

            )

            with urlopen(req, timeout=40) as response:

                return response.read().decode("utf-8", errors="ignore")

        except Exception as exc:

            last_error = exc

            print("[HTTP][RETRY]", attempt, url, exc)

            time.sleep(attempt * 2)

    raise last_error





def extract_region(address):

    if not address:

        return ""

    addr = re.sub(r"\(.*?\)", " ", str(address))

    addr = re.sub(r"\s+", " ", addr).strip()

    match = region_pattern.search(addr)

    if match:

        return match.group(0)

    first = addr.split()[0] if addr else ""

    if any(x in first for x in ["도", "시"]):

        return first

    return ""





def safe_sheet_name(name):

    value = str(name)[:31]

    for char in [":", "\\", "/", "?", "*", "[", "]"]:

        value = value.replace(char, "_")

    return value.strip() or "기타"





def parse_page(page_no):

    url = build_url(page_no)

    print("[REQ]", page_no, url)

    tables = pd.read_html(fetch_html(url))

    if not tables:

        return []



    df = tables[0]

    df.columns = [str(column).strip() for column in df.columns]



    rename_map = {}

    for column in df.columns:

        text = str(column)

        if "번호" in text and "등록" not in text:

            rename_map[column] = "번호"

        elif "상호" in text:

            rename_map[column] = "상호"

        elif "대표" in text:

            rename_map[column] = "대표자"

        elif "주소" in text:

            rename_map[column] = "주소"

        elif "업종" in text:

            rename_map[column] = "업종"

        elif "등록번호" in text:

            rename_map[column] = "등록번호"

        elif "등록연월일" in text or "등록일" in text:

            rename_map[column] = "등록연월일"



    df = df.rename(columns=rename_map)

    need_cols = ["번호", "상호", "대표자", "주소", "업종", "등록번호", "등록연월일"]



    for column in need_cols:

        if column not in df.columns:

            df[column] = ""



    rows = []

    for _, row in df.iterrows():

        item = {column: str(row.get(column, "")).strip() for column in need_cols}



        if not item["상호"] or item["상호"] == "nan":

            continue



        if FILTER_DATE_DT:

            try:

                reg_dt = datetime.strptime(item["등록연월일"], "%Y-%m-%d")

                if reg_dt < FILTER_DATE_DT:

                    continue

            except Exception:

                pass



        item["지역"] = extract_region(item["주소"])

        rows.append(item)



    return rows





def clean_value(value):

    value = "" if value is None else str(value)

    if value.lower() == "nan":

        return ""

    return re.sub(r"\s+", " ", value).strip()





def normalize_company(value):

    value = clean_value(value)

    for token in ["주식회사", "유한회사", "합자회사", "합명회사", "㈜", "(주)", "（주）"]:

        value = value.replace(token, "")

    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).lower()





def normalize_address(value):

    value = clean_value(value)

    value = re.sub(r"^\s*\(?\d{5}\)?\s*", "", value)

    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(

        r"전남광주통합특별시\s*(?=광양시|화순군|여수시|장흥군)",

        "전라남도", value

    )

    value = value.replace("강원특별자치도", "강원도")

    value = value.replace("전북특별자치도", "전라북도")

    value = value.replace("제주특별자치도", "제주도")

    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).lower()





def find_member_table(html):

    tables = pd.read_html(html)

    for table in tables:

        columns = [str(column).strip() for column in table.columns]

        joined = "|".join(columns)

        if "상호" in joined and "주소" in joined and "전화번호" in joined:

            table.columns = columns

            return table

    return None





def member_rows_from_html(html):

    table = find_member_table(html)

    if table is None:

        return []



    colmap = {}

    for column in table.columns:

        text = str(column)

        if "상호" in text:

            colmap[column] = "상호"

        elif "주소" in text:

            colmap[column] = "주소"

        elif "전화" in text:

            colmap[column] = "전화번호"

        elif "등록업종" in text or text == "업종":

            colmap[column] = "등록업종"

        elif text == "번호":

            colmap[column] = "번호"



    table = table.rename(columns=colmap)

    required = ["상호", "주소", "전화번호"]

    if any(column not in table.columns for column in required):

        return []



    rows = []

    for _, row in table.iterrows():

        item = {

            "상호": clean_value(row.get("상호", "")),

            "주소": clean_value(row.get("주소", "")),

            "전화번호": clean_value(row.get("전화번호", "")),

            "등록업종": clean_value(row.get("등록업종", "")),

            "번호": clean_value(row.get("번호", "")),

        }

        if item["상호"] and item["번호"].isdigit():

            rows.append(item)

    return rows





def member_url(page_param, page_no):

    query = {

        "upKindcode": "10",

        "_m": "41",

        page_param: str(page_no),

        "recordCountPerPage": "100",

    }

    return PHONE_BASE_URL + "?" + urlencode(query)







def fetch_member_html(page_param, page_no, retries=3):

    query = {

        "upKindcode": "10",

        "_m": "41",

        page_param: str(page_no),

        "recordCountPerPage": "100",

        "pageUnit": "100",

        "searchGubun": "",

        "searchText": "",

    }



    post_data = urlencode(query).encode("utf-8")

    last_error = None



    for attempt in range(1, retries + 1):

        try:

            request = Request(

                PHONE_BASE_URL + "?upKindcode=10&_m=41",

                data=post_data,

                headers={

                    "User-Agent": "Mozilla/5.0",

                    "Accept-Language": "ko-KR,ko;q=0.9",

                    "Content-Type": "application/x-www-form-urlencoded",

                    "Referer": PHONE_BASE_URL + "?upKindcode=10&_m=41",

                },

            )

            with urlopen(request, timeout=40) as response:

                return response.read().decode("utf-8", errors="ignore")

        except Exception as exc:

            last_error = exc

            print("[PHONE][HTTP][RETRY]", attempt, page_no, exc)

            time.sleep(attempt * 2)



    raise last_error





def detect_page_parameter():

    first_rows = member_rows_from_html(fetch_html(member_url("currentPage", 1)))

    if not first_rows:

        raise RuntimeError("협회 회원사 첫 페이지 표를 찾지 못했습니다.")



    first_signature = tuple(row["상호"] for row in first_rows[:5])



    for parameter in ["currentPage", "currentPageNo", "pageIndex", "pageNo"]:

        second_rows = member_rows_from_html(fetch_html(member_url(parameter, 2)))

        second_signature = tuple(row["상호"] for row in second_rows[:5])

        if second_rows and second_signature != first_signature:

            print("[PHONE] 페이지 변수 확인:", parameter)

            return parameter, first_rows



    raise RuntimeError("협회 회원사 페이지 이동 변수를 확인하지 못했습니다.")





def cache_is_valid():

    if not os.path.exists(CACHE_FILE):

        return False

    age_seconds = time.time() - os.path.getmtime(CACHE_FILE)

    return age_seconds < PHONE_CACHE_HOURS * 3600





def collect_phone_rows():

    if cache_is_valid():

        cached = pd.read_csv(CACHE_FILE, dtype=str).fillna("")

        if len(cached) >= 5000:

            print("[PHONE][CACHE] 사용:", len(cached))

            return cached.to_dict("records")



    page_param, first_rows = detect_page_parameter()

    all_rows = []

    seen_signatures = set()



    for page_no in range(1, PHONE_MAX_PAGES + 1):

        if page_no == 1:

            rows = first_rows

        else:

            html = fetch_html(member_url(page_param, page_no))

            rows = member_rows_from_html(html)



        if not rows:

            print("[PHONE][STOP] 빈 페이지:", page_no)

            break



        signature = tuple(

            (row["상호"], row["주소"], row["전화번호"]) for row in rows

        )

        if signature in seen_signatures:

            print("[PHONE][STOP] 반복 페이지:", page_no)

            break



        seen_signatures.add(signature)

        all_rows.extend(rows)

        print("[PHONE][PAGE]", page_no, "added=", len(rows), "total=", len(all_rows))



        # 전화번호 공란 수로 마지막 페이지를 판단하지 않습니다.

        time.sleep(0.08)



    unique = {}

    for row in all_rows:

        key = (

            clean_value(row.get("상호")),

            clean_value(row.get("주소")),

            clean_value(row.get("전화번호")),

        )

        unique[key] = row



    result = list(unique.values())

    if len(result) < 5000:

        raise RuntimeError(

            "협회 전화번호 수집 건수가 너무 적습니다: %d건" % len(result)

        )



    pd.DataFrame(result).to_csv(CACHE_FILE, index=False, encoding="REDACTED_PRIVATE_VALUE")

    print("[PHONE][CACHE] 저장:", CACHE_FILE, "건수=", len(result))

    return result





def apply_phone_numbers(df, phone_rows):

    index = {}

    for row in phone_rows:

        company_key = normalize_company(row.get("상호", ""))

        address_key = normalize_address(row.get("주소", ""))

        phone = clean_value(row.get("전화번호", ""))



        if not company_key or not address_key or not phone:

            continue

        postcode = re.findall(

            r"^\s*\(?(\d{5})\)?", clean_value(row.get("주소", ""))

        )

        index.setdefault(company_key, []).append((address_key, phone, postcode))



    phones = []

    logs = []

    matched = 0

    ambiguous = 0



    for _, row in df.iterrows():

        company = clean_value(row.get("상호", ""))

        address = clean_value(row.get("주소", ""))

        company_key = normalize_company(company)

        address_key = normalize_address(address)



        candidates = []

        source_postcode = re.findall(r"^\s*\(?(\d{5})\)?", address)

        for member_address, phone, member_postcode in index.get(company_key, []):

            if (

                address_key == member_address

                or (

                    (

                        min(len(address_key), len(member_address)) >= 10

                        or (

                            min(len(address_key), len(member_address)) >= 6

                            and len(source_postcode) == 1

                            and source_postcode == member_postcode

                        )

                    )

                    and (

                        address_key.startswith(member_address)

                        or member_address.startswith(address_key)

                    )

                )

            ):

                candidates.append(phone)



        candidates = sorted(set(candidates))



        if len(candidates) == 1:

            phone = candidates[0]

            status = "MATCH"

            matched += 1

        elif len(candidates) > 1:

            phone = ""

            status = "AMBIGUOUS"

            ambiguous += 1

        else:

            phone = ""

            status = "NO_MATCH"



        phones.append(phone)

        logs.append({

            "상호": company,

            "주소": address,

            "전화번호": phone,

            "결과": status,

        })



    result = df.copy()

    result["전화번호"] = phones



    os.makedirs(os.path.dirname(MATCH_LOG), exist_ok=True)

    pd.DataFrame(logs).to_csv(MATCH_LOG, index=False, encoding="REDACTED_PRIVATE_VALUE")



    print(

        "[PHONE][MATCH] 전체=", len(result),

        "매칭=", matched,

        "중복후보=", ambiguous,

        "미매칭=", len(result) - matched - ambiguous,

    )

    return result





def save_excel_atomic(df, grouped, filename):

    temp_file = filename + ".tmp.xlsx"



    if os.path.exists(temp_file):

        os.remove(temp_file)



    with pd.ExcelWriter(temp_file, engine="openpyxl") as writer:

        df.to_excel(writer, sheet_name="전체", index=False)

        for business_type, rows in grouped.items():

            pd.DataFrame(rows).to_excel(

                writer,

                sheet_name=safe_sheet_name(business_type),

                index=False,

            )



    from openpyxl import load_workbook



    workbook = load_workbook(temp_file, read_only=True, data_only=False)

    if "공사업(전문)" not in workbook.sheetnames:

        workbook.close()

        os.remove(temp_file)

        raise RuntimeError("'공사업(전문)' 시트가 생성되지 않았습니다.")



    sheet = workbook["공사업(전문)"]

    header_i = sheet["I1"].value

    rows = sheet.max_row

    workbook.close()



    if header_i != "전화번호":

        os.remove(temp_file)

        raise RuntimeError("I1 검증 실패: %r" % header_i)



    os.replace(temp_file, filename)

    print("[VERIFY]", filename, "공사업(전문) 행=", rows, "I1=", header_i)





def main():

    all_rows = []



    for page_no in range(1, MAX_PAGES + 1):

        try:

            rows = parse_page(page_no)

        except Exception as exc:

            print("[ERR]", page_no, exc)

            break



        if not rows:

            print("[STOP] 수집 행 없음 page=", page_no)

            break



        all_rows.extend(rows)

        print("[PAGE]", page_no, "added=", len(rows), "total=", len(all_rows))



    if not all_rows:

        raise RuntimeError("신규공시 수집 데이터가 없습니다.")



    source_df = pd.DataFrame(all_rows)

    phone_rows = collect_phone_rows()

    df = apply_phone_numbers(source_df, phone_rows)



    expected_columns = [

        "번호", "상호", "대표자", "주소", "업종",

        "등록번호", "등록연월일", "지역", "전화번호"

    ]

    df = df.reindex(columns=expected_columns)



    os.makedirs(SAVE_DIR, exist_ok=True)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")

    latest_file = os.path.join(SAVE_DIR, "소방시설업_신규공시_최신.xlsx")

    history_file = os.path.join(

        SAVE_DIR,

        "소방시설업_신규공시_%s.xlsx" % now,

    )



    grouped = {}

    for _, row in df.iterrows():

        key = row["업종"] if row["업종"] else "기타"

        grouped.setdefault(key, []).append(row)



    save_excel_atomic(df, grouped, latest_file)

    save_excel_atomic(df, grouped, history_file)



    print("[OK] 최신 저장:", latest_file)

    print("[OK] 이력 저장:", history_file)

    print("[OK] 총 건수:", len(df))





if __name__ == "__main__":

    main()

