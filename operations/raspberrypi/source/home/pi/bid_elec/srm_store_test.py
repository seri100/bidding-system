#!/usr/bin/env python3

# -*- coding: utf-8 -*-



from selenium import webdriver

from selenium.webdriver.chrome.options import Options

import json

import time

import traceback





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





def click_text(driver, word):

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

            else if (t.indexOf(word) >= 0 && t.length < 50) partial.push(e);

        }



        var target = exact.length ? exact[0] :

                     (partial.length ? partial[0] : null);



        if (!target) return null;



        target.scrollIntoView({block: 'center'});

        target.click();



        return {

            tag: target.tagName,

            text: (target.innerText || target.textContent || '').trim(),

            id: target.id || '',

            cls: target.className || ''

        };

        """,

        word

    )





def find_list_component(driver):

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

                        id: c.getId ? c.getId() : '',

                        xtype: c.getXType ? c.getXType() : '',

                        controller: ctl.$className || ''

                    };

                }

            } catch (e) {}

        }



        return null;

        """

    )





def start_search(driver):

    return driver.execute_script(

        r"""

        var c = window.__srm_list_component;

        if (!c) return {ok:false, error:'component missing'};



        try {

            var ctl = c.getController();

            ctl.search();

            return {ok:true};

        } catch (e) {

            return {

                ok:false,

                error:String(e),

                stack:e.stack || ''

            };

        }

        """

    )





def store_status(driver):

    return driver.execute_script(

        r"""

        var c = window.__srm_list_component;

        if (!c) return {found:false};



        try {

            var store = c.getViewModel().getStore('JoinPublicAnnounceStore');



            return {

                found:true,

                loading:store.isLoading(),

                count:store.getCount(),

                total:store.getTotalCount()

            };

        } catch (e) {

            return {

                found:false,

                error:String(e)

            };

        }

        """

    )





def read_records(driver):

    return driver.execute_script(

        r"""

        var c = window.__srm_list_component;

        var out = [];



        if (!c) return out;



        var store = c.getViewModel().getStore('JoinPublicAnnounceStore');



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





def main():

    driver = None



    try:

        driver = make_driver()

        driver.set_page_load_timeout(60)



        print("[STEP] SRM 접속")

        driver.get("https://srm.kepco.net/index.do")

        time.sleep(8)



        print("[STEP] 정보공개:", click_text(driver, "정보공개"))

        time.sleep(3)



        print("[STEP] 통합공고:", click_text(driver, "통합공고"))

        time.sleep(10)



        component = find_list_component(driver)

        print("[COMPONENT]", component)



        if not component:

            raise RuntimeError("통합공고 목록 컴포넌트를 찾지 못했습니다.")



        result = start_search(driver)

        print("[SEARCH]", result)



        if not result.get("ok"):

            raise RuntimeError("조회 실행 실패: %s" % result)



        last_status = None



        for _ in range(60):

            time.sleep(1)

            status = store_status(driver)

            last_status = status



            if (

                status.get("found")

                and not status.get("loading")

                and (

                    status.get("count", 0) > 0

                    or status.get("total", 0) == 0

                )

            ):

                break



        print("[STORE]", last_status)



        records = read_records(driver)

        print("[PAGE_RECORDS]", len(records))



        target_words = (

            "소방", "소화", "화재",

            "기계설비", "기계 설비",

            "가스시설", "가스 시설"

        )



        matched = []



        for row in records:

            title = str(row.get("announceName") or "")

            if any(word in title for word in target_words):

                matched.append(row)



        print("[MATCHED]", len(matched))



        for no, row in enumerate(matched[:30], 1):

            print(

                "%02d | %s | %s | 지역=%s | 추정가격=%s | 마감=%s" % (

                    no,

                    row.get("announceNo", ""),

                    row.get("announceName", ""),

                    row.get("areaCodeName", ""),

                    row.get("presumedprice", ""),

                    row.get("endProposalDate", ""),

                )

            )



        result_path = "/home/pi/bid_elec/srm_store_test_result.json"



        with open(result_path, "w", encoding="utf-8") as f:

            json.dump(

                {

                    "store": last_status,

                    "records": records,

                    "matched": matched,

                },

                f,

                ensure_ascii=False,

                indent=2,

                default=str,

            )



        print("[OK] 결과 저장:", result_path)



    except Exception:

        traceback.print_exc()

        raise



    finally:

        if driver is not None:

            driver.quit()





if __name__ == "__main__":

    main()

