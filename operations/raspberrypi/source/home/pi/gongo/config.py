
# =============================================

# /home/pi/gongo/config.py

# =============================================



API_SERVICE_KEY = "REDACTED_PRIVATE_VALUE"



# ✅ 로컬 저장 경로

LOCAL_RESULT_DIR = "/home/pi/gongo"



# ✅ NAS 저장 경로 (/mnt/vol1 = NAS bid 공유 = Z:\VOL1)

NETWORK_RESULT_DIR = "/mnt/vol1/bid/gongo"



BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"



ENDPOINTS = {

    "공사" : "getBidPblancListInfoCnstwk",

    "물품" : "getBidPblancListInfoThng",

}



NUM_OF_ROWS         = 999

DATA_TYPE           = "json"

LOG_FILE            = "/home/pi/gongo/logs/bid_collector.log"

CSV_FILENAME_FORMAT = "{category}_{date}.csv"

