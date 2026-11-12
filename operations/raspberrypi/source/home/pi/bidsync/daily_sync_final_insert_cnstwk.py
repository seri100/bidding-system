
# -*- coding: utf-8 -*-

import sys

from datetime import datetime, timedelta



import collect_award_db_fixed as base





# =========================================================

# 실행 설정

# =========================================================

LOOKBACK_DAYS = 2

NOW = datetime.now()

YESTERDAY = datetime(NOW.year, NOW.month, NOW.day) - timedelta(days=1)



START_DATE = YESTERDAY - timedelta(days=LOOKBACK_DAYS - 1)

END_DATE = YESTERDAY



MAX_CALL_DAYS = 30

CHUNK_DAYS = 1



BID_TYPES = ("공사",)



# 특정 공고번호만 복구할 때 사용

# 예: ONLY_BID_NO = "R26BK01617844"

ONLY_BID_NO = None



ROWS_PER_PAGE = 100

SLEEP_SEC = 2.0

RETRY_PER_PAGE = 5



# 기본 운영은 등록일시 기준

DEFAULT_INQRY_DIV = base.InqryDiv.REG_DATE



# 필요 시 후처리 조건 사용

POST_FILTER = base.PostFilter(

    exact_bid_no=None,

    exact_agency_name=None,

    title_contains=None,

    participant_count=None,

    winner_name=None,

)





def main():

    rc = base.run_sync(

        script_name="daily_sync_final_insert_cnstwk",

        bid_types=BID_TYPES,

        start_date=START_DATE,

        end_date=END_DATE,

        chunk_days=CHUNK_DAYS,

        only_bid_no=ONLY_BID_NO,

        inqry_div=DEFAULT_INQRY_DIV,

        post_filter=POST_FILTER,

        rows_per_page=ROWS_PER_PAGE,

        retry_per_page=RETRY_PER_PAGE,

        sleep_sec=SLEEP_SEC,

        max_call_days=MAX_CALL_DAYS,

    )

    sys.exit(rc)





if __name__ == "__main__":

    main()

