#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import math
import os
import shutil
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


BASE_DIR = Path("/home/pi/bid_elec")
OUTPUT_DIR = Path("/mnt/vol1/bid/bid_elec")
LOG_DIR = BASE_DIR / "logs"

SEARCH_DAYS = 14
PAGE_SIZE = 100
MIN_AMOUNT = 30_000_000

KST = timezone(timedelta(hours=9))

INCLUDE_KEYWORDS = (
    "소화설비",
    "소방설비",
    "소방 설비",
    "소방시설",
    "소방 시설",
    "소방공사",
    "소방 공사",
    "기계설비",
    "기계 설비",
)

EXCLUDE_KEYWORDS = (
    "물품 구매",
    "물품구매",
    "구매",
    "납품",
    "제조",
    "제작 구매",
    "임대",
    "렌탈",
    "설계용역",
    "설계 용역",
    "감리용역",
    "감리 용역",
    "점검용역",
    "점검 용역",
)


def log(message):
    text = "[%s] %s" % (
        datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        message,
    )
    print(text, flush=True)


def make_driver():
    options = Options()
    options.binary_location = "REDACTED_PRIVATE_VALUE"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("REDACTED_PRIVATE_VALUE")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ko-KR")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux armv7l) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/92.0.4515.98 Safari/537.36"
    )
    return webdriver.Chrome(options=options)
def _click_text_once(driver, word):
    return driver.execute_script(
        r"""
        var word = arguments[0];
        var all = document.querySelectorAll('a,button,span,div,li');
        var exact = [];
        var partial = [];

        for (var i = 0; i < all.length; i++) {
            var e = all[i];
            var t = (e.innerText || e.textContent || '').trim();
            var r = e.getBoundingClientRect();

            if (!t || r.width <= 0 || r.height <= 0) continue;

            if (t === word) exact.push(e);
            else if (t.indexOf(word) >= 0 && t.length < 50) {
                partial.push(e);
            }
        }

        var target = exact.length ? exact[0] :
                     (partial.length ? partial[0] : null);

        if (!target) return null;

        target.scrollIntoView({block:'center'});
        target.click();

        return {
            tag:target.tagName,
            text:(target.innerText || target.textContent || '').trim(),
            id:target.id || ''
        };
        """,
        word,
    )


def click_text(driver, word, timeout=90):

    deadline = time.time() + timeout

    last_error = None



    while time.time() < deadline:

        try:

            result = _click_text_once(driver, word)



            if result:

                return result

        except Exception as e:

            last_error = e



        time.sleep(2)



    log(

        "메뉴 대기 시간 초과: %s, 마지막 오류=%r" %

        (word, last_error)

    )

    return None





def _find_component_once(driver):
    return driver.execute_script(
        r"""
        if (typeof Ext === 'undefined') return null;

        var all = Ext.ComponentQuery.query('*');

        for (var i = 0; i < all.length; i++) {
            var c = all[i];

            try {
                var vm = c.getViewModel ? c.getViewModel() : null;
                var ctl = c.getController ? c.getController() : null;

                if (
                    ctl &&
                    typeof ctl.search === 'function' &&
                    vm &&
                    vm.getStore &&
                    vm.getStore('JoinPublicAnnounceStore')
                ) {
                    window.__srm_list_component = c;

                    return {
                        id:c.getId ? c.getId() : '',
                        xtype:c.getXType ? c.getXType() : ''
                    };
                }
            } catch (e) {}
        }

        return null;
        """
    )


def find_component(driver, timeout=120):

    deadline = time.time() + timeout

    last_error = None



    while time.time() < deadline:

        try:

            result = _find_component_once(driver)



            if result:

                return result

        except Exception as e:

            last_error = e



        time.sleep(2)



    log(

        "목록 화면 대기 시간 초과, 마지막 오류=%r" %

        last_error

    )

    return None





def start_search(driver, search_days):
    return driver.execute_script(
        r"""
        var days = arguments[0];
        var c = window.__srm_list_component;

        if (!c) return {ok:false, error:'component missing'};

        try {
            var vm = c.getViewModel();
            var ctl = c.getController();
            var now = new Date();
            var from = new Date(now.getTime() - days * 86400000);
            var value = vm.get('searchValue') || {};

            value.searchDateType = 'NoticeDateTime';
            value.searchType = '';
            value.searchKeyword = '';
            value.fromSearchDate = from;
            value.toSearchDate = now;

            vm.set('searchValue', value);

            var store = vm.getStore('JoinPublicAnnounceStore');
            store.setPageSize(100);

            ctl.search();

            return {
                ok:true,
                from:from.toISOString(),
                to:now.toISOString()
            };
        } catch (e) {
            return {
                ok:false,
                error:String(e),
                stack:e.stack || ''
            };
        }
        """,
        search_days,
    )
def store_status(driver):
    return driver.execute_script(
        r"""
        var c = window.__srm_list_component;
        if (!c) return {found:false};

        try {
            var store = c.getViewModel().getStore(
                'JoinPublicAnnounceStore'
            );

            return {
                found:true,
                loading:store.isLoading(),
                count:store.getCount(),
                total:store.getTotalCount(),
                currentPage:store.currentPage,
                pageSize:store.getPageSize()
            };
        } catch (e) {
            return {found:false, error:String(e)};
        }
        """
    )


def wait_store(driver, expected_page=None, timeout=90):
    deadline = time.time() + timeout
    last = None

    while time.time() < deadline:
        time.sleep(1)
        last = store_status(driver)

        if not last.get("found"):
            continue

        if last.get("loading"):
            continue

        if expected_page is not None:
            if int(last.get("currentPage") or 0) != int(expected_page):
                continue

        return last

    raise RuntimeError(
        "SRM 목록 로딩 시간 초과: %r" % last
    )


def load_page(driver, page_no):
    result = driver.execute_script(
        r"""
        var page = arguments[0];
        var c = window.__srm_list_component;

        if (!c) return {ok:false, error:'component missing'};

        try {
            var vm = c.getViewModel();
            var store = vm.getStore('JoinPublicAnnounceStore');
            var params = vm.get('searchValue') || {};

            store.loadPage(page, {params:params});

            return {ok:true};
        } catch (e) {
            return {ok:false, error:String(e)};
        }
        """,
        page_no,
    )

    if not result.get("ok"):
        raise RuntimeError(
            "페이지 %s 요청 실패: %r" % (page_no, result)
        )

    return wait_store(driver, expected_page=page_no)


def read_records(driver):
    return driver.execute_script(
        r"""
        var c = window.__srm_list_component;
        var out = [];

        if (!c) return out;

        var store = c.getViewModel().getStore(
            'JoinPublicAnnounceStore'
        );

        store.each(function(rec) {
            var d = {};

            for (var key in rec.data) {
                if (!rec.data.hasOwnProperty(key)) continue;

                var value = rec.data[key];

                if (value instanceof Date) {
                    value = value.toISOString();
                }

                d[key] = value;
            }

            out.push(d);
        });

        return out;
        """
    )


def to_int(value):
    if value is None:
        return 0

    text = str(value).replace(",", "").replace("원", "").strip()

    if not text:
        return 0

    try:
        return int(float(text))
    except Exception:
        return 0


def iso_to_kst(value):
    if not value:
        return ""

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(
                text[:-1] + "+00:00"
            )
        else:
            dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return text


def classify_industry(title):
    text = str(title or "")

    if "기계설비" in text or "기계 설비" in text:
        return "6202", "기계설비공사업"

    if "소방" in text or "소화설비" in text:
        return "0040", "전문소방시설공사업"

    return "", ""


def filter_reason(row):
    title = str(row.get("announceName") or "").strip()
    rfx_type = str(row.get("rfxType") or "").strip()
    amount = to_int(row.get("presumedprice"))

    if rfx_type != "ServiceBid":
        return False, "공사·용역 입찰 아님"

    if "공사" not in title:
        return False, "공사 문구 없음"

    if not any(word in title for word in INCLUDE_KEYWORDS):
        return False, "대상 업종 문구 없음"

    if any(word in title for word in EXCLUDE_KEYWORDS):
        return False, "구매·용역 제외 문구"

    # 단순 건축물 명칭에 소방이 들어간 경우는 소방시설공사로 보지 않는다.
    if (
        "소방차고" in title
        and not any(word in title for word in (
            "소방시설", "소방 시설",
            "소방설비", "소방 설비",
            "소방공사", "소방 공사",
        ))
    ):
        return False, "소방차고 건축공사"

    if amount < MIN_AMOUNT:
        return False, "추정가격 3천만원 미만"

    # 이미 입찰이 끝난 공고는 엑셀과 알림 대상에서 제외한다.
    close_value = row.get("endProposalDate")

    if close_value:
        try:
            close_text = str(close_value).strip()

            if close_text.endswith("Z"):
                close_dt = datetime.fromisoformat(
                    close_text[:-1] + "+00:00"
                )
            else:
                close_dt = datetime.fromisoformat(close_text)

            if close_dt.tzinfo is None:
                close_dt = close_dt.replace(tzinfo=timezone.utc)

            if close_dt <= datetime.now(timezone.utc):
                return False, "입찰마감 경과"
        except Exception:
            pass

    return True, "대상"
def convert_row(row):
    title = str(row.get("announceName") or "").strip()
    code, industry = classify_industry(title)
    area = str(row.get("areaCodeName") or "").strip()

    if not area or area.lower() in ("none", "null", "nan"):
        area = "전국"

    return {
        "공고번호": str(row.get("announceNo") or "").strip(),
        "차수": "000",
        "공고명": title,
        "공고업종코드": code,
        "공고업종명": industry,
        "발주기관": str(
            row.get("departmentFullPath")
            or row.get("departmentName")
            or ""
        ).strip(),
        "입찰종류": str(row.get("rfxType") or "").strip(),
        "계약방법": str(row.get("bidType") or "").strip(),
        "공고일시": iso_to_kst(row.get("announceDate")),
        "입찰참가신청마감": iso_to_kst(
            row.get("endRequestDate")
        ),
        "입찰시작일시": iso_to_kst(
            row.get("startProposalDate")
        ),
        "입찰마감일시": iso_to_kst(
            row.get("endProposalDate")
        ),
        "대표지역": area,
        "local_region": area,
        "scope": "전국" if area == "전국" else "지역",
        "추정가격": to_int(row.get("presumedprice")),
        "기초금액": 0,  # 공식 기초금액 미확인: 추정가격 대입 금지
        "기초금액출처": "미확인",
        "진행상태": str(row.get("progressStatus") or "").strip(),
        "제한경쟁유형": str(row.get("limitedType") or "").strip(),
        "제한사유": str(
            row.get("limitedReasonCode") or ""
        ).strip(),
        "SRM_ID": str(row.get("id") or "").strip(),
        "detail_url": "https://srm.kepco.net/index.do",
        "수집시각": datetime.now(KST).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }


def collect(search_days):
    driver = None

    try:
        driver = make_driver()
        driver.set_page_load_timeout(60)

        log("SRM 접속")
        driver.get("https://srm.kepco.net/index.do")
        time.sleep(8)

        if not click_text(driver, "정보공개"):
            raise RuntimeError("정보공개 메뉴를 찾지 못했습니다.")

        time.sleep(3)

        if not click_text(driver, "통합공고"):
            raise RuntimeError("통합공고 메뉴를 찾지 못했습니다.")

        time.sleep(10)

        component = find_component(driver)

        if not component:
            raise RuntimeError(
                "통합공고 목록 컴포넌트를 찾지 못했습니다."
            )

        log("통합공고 화면 확인: %s" % component)

        started = start_search(driver, search_days)

        if not started.get("ok"):
            raise RuntimeError(
                "조회 시작 실패: %r" % started
            )

        log(
            "검색기간: %s ~ %s" %
            (started.get("from"), started.get("to"))
        )

        status = wait_store(driver, expected_page=1)
        total = int(status.get("total") or 0)
        page_size = int(status.get("pageSize") or PAGE_SIZE)
        pages = int(math.ceil(total / float(page_size))) if total else 0

        log(
            "조회 결과: total=%s pages=%s page_size=%s" %
            (total, pages, page_size)
        )

        all_records = []

        if pages:
            all_records.extend(read_records(driver))

        for page_no in range(2, pages + 1):
            load_page(driver, page_no)
            records = read_records(driver)
            all_records.extend(records)

            log(
                "페이지 %s/%s: %s건, 누적 %s건" %
                (page_no, pages, len(records), len(all_records))
            )

        unique = {}

        for row in all_records:
            key = str(
                row.get("announceNo")
                or row.get("id")
                or ""
            ).strip()

            if key:
                unique[key] = row

        return list(unique.values())

    finally:
        if driver is not None:
            driver.quit()


def save_excel(rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(KST)
    stamp = now.strftime("%Y%m%d_%H%M%S")

    output = OUTPUT_DIR / (
        "KEPCO_SRM_공사공고_%s.xlsx" % stamp
    )
    latest = OUTPUT_DIR / "KEPCO_SRM_공사공고_LATEST.xlsx"

    columns = [
        "공고번호",
        "차수",
        "공고명",
        "공고업종코드",
        "공고업종명",
        "발주기관",
        "입찰종류",
        "계약방법",
        "공고일시",
        "입찰참가신청마감",
        "입찰시작일시",
        "입찰마감일시",
        "대표지역",
        "scope",
        "추정가격",
        "기초금액",
        "진행상태",
        "제한경쟁유형",
        "제한사유",
        "SRM_ID",
        "detail_url",
        "수집시각",

        "공동수급여부",

        "공동수급방식",

        "협정마감일시",

        "협정정보출처",

        "협정확인상태",

        "다음행동",

        "공고문파일명",

        "공고문저장경로",
        "알림톡상태",
        "첨부파일폴더",
        "첨부파일수",
        "첨부저장상태",
        "첨부파일목록",
    ]

    df = pd.DataFrame(rows)

    for column in columns:
        if column not in df.columns:
            df[column] = ""

    df = df[columns]

    if not df.empty:
        df = df.sort_values(
            by=["공고일시", "공고번호"],
            ascending=[False, True],
        )

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:
        df.to_excel(
            writer,
            sheet_name="한전SRM공사공고",
            index=False,
        )

        ws = writer.book["한전SRM공사공고"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        widths = {
            "A": 18, "B": 8, "C": 55, "D": 14,
            "E": 25, "F": 45, "G": 15, "H": 18,
            "I": 20, "J": 20, "K": 20, "L": 20,
            "M": 18, "N": 10, "O": 18, "P": 18,
            "Q": 18, "R": 18, "S": 15, "T": 38,
            "U": 35, "V": 20,
        }

        for column, width in widths.items():
            ws.column_dimensions[column].width = width

        for cell in ws["O"][1:]:
            cell.number_format = '#,##0"원"'

        for cell in ws["P"][1:]:
            cell.number_format = '#,##0"원"'

    shutil.copy2(str(output), str(latest))

    return output, latest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--days",
        type=int,
        default=SEARCH_DAYS,
    )
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="현재 버전은 항상 발송하지 않음",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log("한전 SRM 수집 시작")
    log(
        "조건: 최근 %s일, ServiceBid, 공사, "
        "소방/기계설비, 추정가격 %s원 이상" %
        (args.days, format(MIN_AMOUNT, ","))
    )

    records = collect(args.days)

    matched = []
    excluded = {}

    for row in records:
        ok, reason = filter_reason(row)

        if ok:
            matched.append(convert_row(row))
        else:
            excluded[reason] = excluded.get(reason, 0) + 1

    log("전체 수집: %s건" % len(records))
    log("조건 일치: %s건" % len(matched))
    log(
        "제외 내역: %s" %
        json.dumps(excluded, ensure_ascii=False)
    )

    for row in matched:
        log(
            "[MATCH] %s | %s | %s원 | %s" %
            (
                row["공고번호"],
                row["공고명"],
                format(row["추정가격"], ","),
                row["대표지역"],
            )
        )

    output, latest = save_excel(matched)

    log("엑셀 저장: %s" % output)
    log("최신 파일: %s" % latest)
    log("알림톡: 발송하지 않음")
    log("한전 SRM 수집 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
