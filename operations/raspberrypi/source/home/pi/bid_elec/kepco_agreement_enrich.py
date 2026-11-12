# -*- coding: utf-8 -*-

import shutil

import tempfile

import time

from pathlib import Path



from selenium.webdriver.common.by import By



import kepco_srm_collect as collector

from kepco_agreement_parser import analyze_hwp





ARCHIVE_DIR = Path("/mnt/vol1/bid/bid_elec/agreement_docs")





def open_srm(driver):

    driver.set_page_load_timeout(60)

    driver.get("https://srm.kepco.net/index.do")

    time.sleep(8)



    if not collector.click_text(driver, "정보공개"):

        raise RuntimeError("정보공개 메뉴 진입 실패")



    time.sleep(3)



    if not collector.click_text(driver, "통합공고"):

        raise RuntimeError("통합공고 메뉴 진입 실패")



    time.sleep(10)



    if not collector.find_component(driver):

        raise RuntimeError("통합공고 컴포넌트 확인 실패")





def open_detail(driver, announce_no):

    driver.execute_script(

        r'''

        var c = window.__srm_list_component;

        var vm = c.getViewModel();

        var ctl = c.getController();



        var combo = c.query("combobox").filter(function(f) {

            return f.valueField === "field1"

                && f.getStore()

                && f.getStore().findRecord(

                    "field1", "AnnounceNo"

                );

        })[0];



        var text = c.query("textfield").filter(function(f) {

            return f.getXType()

                && f.getXType() === "textfield";

        })[0];



        if (!combo || !text) {

            throw "검색 입력 컴포넌트 없음";

        }



        combo.setValue("AnnounceNo");

        text.setValue(arguments[0]);



        var value = Ext.clone(vm.get("searchValue") || {});

        value.searchType = "AnnounceNo";

        value.searchKeyword = arguments[0];

        value.searchText = arguments[0];



        vm.set("searchValue", value);

        ctl.search();

        ''',

        announce_no,

    )



    collector.wait_store(

        driver,

        expected_page=1,

        timeout=90,

    )



    result = driver.execute_script(

        r'''

        var c = window.__srm_list_component;

        var store = c.getViewModel().getStore(

            "JoinPublicAnnounceStore"

        );



        var record = store.findRecord(

            "announceNo",

            arguments[0],

            0,

            false,

            true,

            true

        );



        if (!record) {

            return {ok:false};

        }



        c.getController().onGridCellClick(record);



        return {

            ok:true,

            id:record.get("id")

        };

        ''',

        announce_no,

    )



    if not result or not result.get("ok"):

        raise RuntimeError(

            "{} 상세공고 검색 실패".format(announce_no)

        )



    time.sleep(15)





def find_notice_element(driver):

    elements = driver.find_elements(

        By.XPATH,

        '//*[contains(normalize-space(text()),'

        '"공고문") and '

        'contains(normalize-space(text()),".hwp")]',

    )



    candidates = []



    for element in elements:

        if not element.is_displayed():

            continue



        name = element.text.strip()



        if "담당자 안내" in name:

            continue



        score = 0



        if "[공고용]" in name:

            score += 100

        if "입찰공고문(" in name:

            score += 30



        candidates.append(

            (score, -len(name), element, name)

        )



    if not candidates:

        return None, ""



    candidates.sort(

        key=lambda item: (item[0], item[1]),

        reverse=True,

    )



    return candidates[0][2], candidates[0][3]





def wait_download(directory, timeout=40):

    deadline = time.time() + timeout

    previous = None

    stable_count = 0



    while time.time() < deadline:

        partial = list(directory.glob("*.crdownload"))

        files = [

            path for path in directory.iterdir()

            if path.is_file()

            and not path.name.endswith(".crdownload")

        ]



        if files and not partial:

            file_path = max(

                files,

                key=lambda path: path.stat().st_mtime,

            )

            current = (

                str(file_path),

                file_path.stat().st_size,

            )



            if current == previous:

                stable_count += 1

            else:

                stable_count = 0



            previous = current



            if stable_count >= 2 and current[1] > 0:

                return file_path



        time.sleep(1)



    raise RuntimeError("공고문 다운로드 시간 초과")





def download_notice_hwp(driver, announce_no):

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)



    archive_path = ARCHIVE_DIR / (

        "{}_입찰공고문.hwp".format(announce_no)

    )



    if (
        archive_path.exists()
        and archive_path.stat().st_size > 0
    ):

        return archive_path, "기존 공식 공고문"



    temp_dir = Path(

        tempfile.mkdtemp(prefix="kepco_agreement_")

    )



    try:

        driver.execute_cdp_cmd(

            "Page.setDownloadBehavior",

            {

                "behavior": "allow",

                "downloadPath": str(temp_dir),

            },

        )



        open_detail(driver, announce_no)



        element, original_name = find_notice_element(

            driver

        )



        if element is None:

            raise RuntimeError(

                "입찰공고문 HWP 첨부파일 없음"

            )



        driver.execute_script(

            'arguments[0].scrollIntoView('

            '{block:"center"});',

            element,

        )

        driver.execute_script(

            "arguments[0].click();",

            element,

        )



        downloaded = wait_download(temp_dir)



        shutil.copy2(

            str(downloaded),

            str(archive_path),

        )



        return archive_path, original_name



    finally:

        shutil.rmtree(

            str(temp_dir),

            ignore_errors=True,

        )





def failure_result(message):

    return {

        "공동수급여부": "확인실패",

        "공동수급방식": "",

        "협정마감일시": "",

        "협정정보출처": "한전 SRM 공식 입찰공고문",

        "협정확인상태": message,

        "다음행동": "공고문 원문에서 협정정보 직접 확인",

    }





def enrich_rows(rows, log=print):

    if not rows:

        return rows



    driver = collector.make_driver()



    try:

        open_srm(driver)



        for row in rows:

            announce_no = str(

                row.get("공고번호") or ""

            ).strip()



            if not announce_no:

                row.update(

                    failure_result("공고번호 없음")

                )

                continue



            try:

                hwp_path, attachment_name = (

                    download_notice_hwp(

                        driver,

                        announce_no,

                    )

                )



                result = analyze_hwp(hwp_path)

                result["공고문파일명"] = attachment_name

                result["공고문저장경로"] = str(hwp_path)

                row.update(result)



                log(

                    "[AGREEMENT] {} | 여부={} | "

                    "마감={} | 상태={}".format(

                        announce_no,

                        row.get("공동수급여부", ""),

                        row.get("협정마감일시", ""),

                        row.get("협정확인상태", ""),

                    )

                )



            except Exception as exc:

                row.update(

                    failure_result(

                        "{}: {}".format(

                            type(exc).__name__,

                            exc,

                        )

                    )

                )



                log(

                    "[AGREEMENT][WARN] {} | {}".format(

                        announce_no,

                        exc,

                    )

                )



        return rows



    finally:

        driver.quit()

