#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KISCON 73000 신규등록 업체를 수집하고 KMCCA 정보로 보완한다.

Python 3.7+ / Raspberry Pi. 결과는 날짜별 파일과 누적 파일에 저장한다.
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


KISCON_LIST = "https://www.kiscon.net/cis/coad_disposenotice_02.asp"
KISCON_DETAIL = "https://www.kiscon.net/cis/coad_disposenotice_view_02.asp?seqno={}"
KMCCA_WORK_LIST = "https://www.kmcca.or.kr/ks/workRecord/workRecordList.do"
KMCCA_WORK_DETAIL = "https://www.kmcca.or.kr/ks/workRecord/workRecord.do"
KMCCA_DISCLOSURE = "https://www.kmcca.or.kr/ks/construct/disclosureList.do"

HEADERS = [
    "수집일시", "공고일자", "공고번호", "상호", "대표자", "소재지", "지역구분",
    "업종", "등록번호", "주력분야", "등록일자", "전화번호", "FAX",
    "시공능력(천원)", "시공능력 평가년도", "KISCON 상세URL",
    "협회 공사실적URL", "협회 시공능력URL", "매칭상태", "KISCON seqno"
]


def norm_company(value):
    s = re.sub(r"\([^)]*\)", "", value or "")
    s = re.sub(r"주식회사|유한회사|합자회사|합명회사|㈜|\(주\)|\(유\)", "", s)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()


def norm_license(value):
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", value or "").lower()
    return re.sub(r"호$", "", normalized)


def region_from_address(address):

    text = clean_text(address)

    regions = [

        ("서울특별시", "서울"), ("부산광역시", "부산"),

        ("대구광역시", "대구"), ("인천광역시", "인천"),

        ("광주광역시", "광주"), ("대전광역시", "대전"),

        ("울산광역시", "울산"), ("세종특별자치시", "세종"),

        ("경기도", "경기"), ("강원특별자치도", "강원"), ("강원도", "강원"),

        ("충청북도", "충북"), ("충청남도", "충남"),

        ("전북특별자치도", "전북"), ("전라북도", "전북"),

        ("전라남도", "전남"), ("경상북도", "경북"),

        ("경상남도", "경남"), ("제주특별자치도", "제주"),

        ("제주도", "제주")

    ]

    for prefix, region in regions:

        if text.startswith(prefix):

            return region

    return ""





def clean_text(value):
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def find_value(text, label, next_labels):
    end = "|".join(re.escape(x) for x in next_labels)
    m = re.search(re.escape(label) + r"\s*:\s*(.*?)(?=\s*(?:" + end + r")\s*:|$)", text, re.S)
    return clean_text(m.group(1)) if m else ""


class Collector:
    def __init__(self, output_dir, timeout=45):
        self.output_dir = Path(output_dir)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
        })

    def request(self, method, url, **kwargs):
        last = None
        for attempt in range(3):
            try:
                r = self.session.request(method, url, timeout=self.timeout, **kwargs)
                r.raise_for_status()
                if not r.encoding or r.encoding.lower() == "iso-8859-1":
                    r.encoding = r.apparent_encoding or "utf-8"
                return r
            except Exception as exc:
                last = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last

    def kiscon_rows(self, target_date):
        y, m, d = target_date.strftime("%Y"), target_date.strftime("%m"), target_date.strftime("%d")
        base = {
            "mode": "1", "GotoPage": "1", "fromYear": y, "toYear": y,
            "fromMonth": m, "toMonth": m, "fromDay": d, "toDay": d,
            "level": "1", "area": "", "areadetail": "", "decode": "",
            "mattercode": "", "accept": "", "kname": "", "item": "73000"
        }
        found = []
        page = 1
        while True:
            base["GotoPage"] = str(page)
            r = self.request("GET", KISCON_LIST, params=base)
            soup = BeautifulSoup(r.text, "lxml")
            rows = soup.select("tr[onclick*='f_go_location']")
            for tr in rows:
                onclick = tr.get("onclick", "")
                mm = re.search(r"f_go_location\((\d+)\)", onclick)
                cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
                if not mm or len(cells) < 7:
                    continue
                if "기계설비" not in cells[5] or "가스공사업" not in cells[5] or cells[6] != "신규":
                    continue
                found.append({"seqno": mm.group(1), "list_cells": cells})
            page_links = soup.select("a[href*='GotoPage=']")
            max_page = max([int(x) for a in page_links for x in re.findall(r"GotoPage=(\d+)", a.get("href", ""))] or [1])
            if page >= max_page:
                break
            page += 1
        return found

    def kiscon_detail(self, item):
        url = KISCON_DETAIL.format(item["seqno"])
        r = self.request("GET", url)
        soup = BeautifulSoup(r.text, "lxml")
        text = clean_text(soup.get_text(" ", strip=True))

        labels = ["상호명", "대표자", "소재지", "등록업종 및 등록번호", "등록일자"]

        company = find_value(text, "상호명", labels[1:])

        ceo = find_value(text, "대표자", labels[2:])



        address_match = re.search(

            r"소재지\s*[-:：]?\s*(.*?)\s*(?=등록업종\s*및\s*등록번호)",

            text

        )

        address = clean_text(address_match.group(1)) if address_match else ""



        lic_matches = re.findall(

            r"등록번호\s*[:：]\s*([^)）]+)",

            text

        )

        main_matches = re.findall(

            r"주력분야\s*[:：]\s*([^)）]+)",

            text

        )

        license_no = clean_text(lic_matches[-1]) if lic_matches else ""

        main_field = clean_text(main_matches[-1]) if main_matches else ""



        date_matches = re.findall(

            r"등록일자\s*[-:：]?\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",

            text

        )

        if date_matches:

            yy, mm, dd = date_matches[-1]

            reg_date = "%04d-%02d-%02d" % (int(yy), int(mm), int(dd))

        else:

            reg_date = ""

        list_cells = item.get("list_cells", [])
        notice_no = list_cells[1] if len(list_cells) > 1 else ""
        notice_date = list_cells[2] if len(list_cells) > 2 else ""
        return {
            "seqno": item["seqno"], "notice_no": notice_no, "notice_date": notice_date,
            "company": company or (list_cells[3] if len(list_cells) > 3 else ""),
            "ceo": ceo, "address": address, "region": region_from_address(address), "industry": "기계설비·가스공사업",
            "license_no": license_no,
            "main_field": main_field,
            "registration_date": reg_date,
            "kiscon_url": url,
        }

    def work_record(self, row):
        qname = norm_company(row["company"])
        payload = {"pageIndex": "1", "searchSidoho": "", "searchKsangho": qname, "jsonView": "Y"}
        data = self.request("POST", KMCCA_WORK_LIST, data=payload).json()
        candidates = data.get("resultList") or []
        exact = [c for c in candidates if norm_company(c.get("ksanghoName")) == qname]
        if row["ceo"]:
            ceo_exact = [c for c in exact if clean_text(c.get("korName")) == clean_text(row["ceo"])]
            if ceo_exact:
                exact = ceo_exact
        if len(exact) != 1:
            return {}, "협회 업체매칭 {}건".format(len(exact))
        c = exact[0]
        detail = self.request("POST", KMCCA_WORK_DETAIL, data={"memberNo": c["memberNo"], "sidohoCode": c["sidohoCode"]})
        soup = BeautifulSoup(detail.text, "lxml")
        values = {}
        for th in soup.select("table.notice0401 th"):
            td = th.find_next_sibling("td")
            if td:
                values[clean_text(th.get_text())] = clean_text(td.get_text(" ", strip=True))
        work_license = values.get("기계설비 가스공사업 등록번호", "")
        if row["license_no"] and work_license and norm_license(row["license_no"]) != norm_license(work_license):
            return {}, "등록번호 불일치"
        return {
            "phone": values.get("전화번호", ""), "fax": values.get("FAX", ""),
            "work_url": KMCCA_WORK_DETAIL + "?memberNo={}&sidohoCode={}".format(c["memberNo"], c["sidohoCode"]),
            "member_no": c["memberNo"], "sidoho_code": c["sidohoCode"],
        }, "협회 연락처 매칭"

    def disclosure(self, row, year):
        payload = {
            "pageIndex": "1", "searchSidoho": "", "searchKsangho": norm_company(row["company"]),
            "searchSingoYear": str(year), "searchUpjong": "73", "searchStrPrice": "",
            "searchEndPrice": "", "searchOrder": "1", "searchBunya": "",
            "searchGongjong": "", "jsonView": "Y"
        }
        data = self.request("POST", KMCCA_DISCLOSURE, data=payload).json()
        candidates = [c for c in (data.get("resultList") or []) if norm_company(c.get("ksanghoName")) == norm_company(row["company"])]
        license_exact = [c for c in candidates if norm_license(c.get("licenseNo")) == norm_license(row["license_no"])]
        if license_exact:
            candidates = license_exact
        if len(candidates) != 1:
            return {}, "시공능력 {}건".format(len(candidates))
        c = candidates[0]
        amount = c.get("valuateAmt", "")
        return {"capacity": amount, "capacity_year": year, "disclosure_url": KMCCA_DISCLOSURE}, "시공능력 매칭"


def init_db(path):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE IF NOT EXISTS processed (seqno TEXT PRIMARY KEY, processed_at TEXT NOT NULL)")
    con.commit()
    return con


def write_xlsx(path, rows):
    path = Path(path)
    if path.exists():
        wb = load_workbook(str(path))
        ws = wb["신규등록업체"] if "신규등록업체" in wb.sheetnames else wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "신규등록업체"
        ws.append(HEADERS)
        fill = PatternFill("solid", fgColor="1F4E78")
        for cell in ws[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = "A1:T1"



    if ws.cell(1, 7).value != "지역구분":

        if ws.cell(1, 7).value == "업종" and ws.cell(1, 19).value == "KISCON seqno":

            ws.insert_cols(7)

            ws.cell(1, 7).value = "지역구분"

            ws.cell(1, 7).font = Font(color="FFFFFF", bold=True)

            ws.cell(1, 7).fill = PatternFill("solid", fgColor="1F4E78")

            ws.cell(1, 7).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            for old_row_no in range(2, ws.max_row + 1):

                ws.cell(old_row_no, 7).value = region_from_address(ws.cell(old_row_no, 6).value)

        else:

            raise RuntimeError("예상하지 못한 엑셀 열 구조입니다.")



    ws.auto_filter.ref = "A1:T1"

    existing_rows = {}

    for row_no in range(2, ws.max_row + 1):

        seqno = ws.cell(row_no, 20).value

        if seqno in (None, ""):

            continue

        seqno = str(seqno)

        if seqno in existing_rows:

            raise RuntimeError("엑셀에 중복 seqno가 있습니다: " + seqno)

        existing_rows[seqno] = row_no



    for r in rows:

        values = [

            r["collected_at"], r["notice_date"], r["notice_no"], r["company"], r["ceo"], r["address"],

            r.get("region", region_from_address(r["address"])), r["industry"], r["license_no"], r["main_field"], r["registration_date"], r.get("phone", ""),

            r.get("fax", ""), r.get("capacity", ""), r.get("capacity_year", ""), r["kiscon_url"],

            r.get("work_url", ""), r.get("disclosure_url", KMCCA_DISCLOSURE), r.get("match_status", ""), r["seqno"]

        ]



        seqno = str(r["seqno"])

        row_no = existing_rows.get(seqno)



        if row_no is None:

            ws.append(values)

            row_no = ws.max_row

            existing_rows[seqno] = row_no

        else:

            for col_no, value in enumerate(values, 1):

                ws.cell(row_no, col_no).value = value



    widths = [20, 12, 28, 25, 12, 48, 12, 24, 22, 18, 12, 16, 16, 18, 15, 45, 45, 45, 32, 14]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    tmp = path.with_suffix(".tmp.xlsx")
    wb.save(str(tmp))
    load_workbook(str(tmp), read_only=True).close()
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="공고일 YYYY-MM-DD, 기본값 오늘")
    ap.add_argument("--output-dir", default="/mnt/vol1/kiscon")
    ap.add_argument("--days-back", type=int, default=3, help="누락 복구를 위해 최근 N일 재조회")
    args = ap.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(str(out / "logs" / "kiscon_daily.log"), encoding="utf-8"), logging.StreamHandler()])
    today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    collector = Collector(out)
    state_dir = Path(__file__).resolve().parent / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    con = init_db(state_dir / "kiscon_state.sqlite3")
    all_rows = []
    for offset in range(max(1, args.days_back)):
        target = today - timedelta(days=offset)
        logging.info("KISCON 조회일=%s 업종=73000 종류=신규", target)
        for item in collector.kiscon_rows(target):
            try:
                row = collector.kiscon_detail(item)
                work, s1 = collector.work_record(row)
                row.update(work)
                capacity = {}
                s2 = ""
                for year in (today.year, today.year - 1):
                    capacity, s2 = collector.disclosure(row, year)
                    if capacity:
                        break
                row.update(capacity)
                row["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row["match_status"] = s1 + " / " + s2
                all_rows.append(row)
            except Exception:
                logging.exception("seqno=%s 처리 실패", item["seqno"])
    if all_rows:
        daily = out / "KISCON_73000_신규등록_{}.xlsx".format(today.strftime("%Y%m%d"))
        master = out / "KISCON_73000_신규등록_누적.xlsx"
        write_xlsx(daily, all_rows)
        write_xlsx(master, all_rows)
        for row in all_rows:
            con.execute("INSERT OR REPLACE INTO processed(seqno,processed_at) VALUES(?,?)", (row["seqno"], row["collected_at"]))
        con.commit()
        logging.info("완료 신규=%d 일자별=%s 누적=%s", len(all_rows), daily, master)
    else:
        logging.info("신규 또는 미처리 대상 없음")
    con.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("치명적 오류")
        sys.exit(1)
