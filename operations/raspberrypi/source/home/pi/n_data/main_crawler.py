
import json

import os

import datetime

from api_crawler import fetch_bid_data

from kakao_sender import notify_kakao



SETTINGS_PATH = "/home/pi/n_data/settings.json"

API_KEY_FILE = "/home/pi/n_data/bid_api_key.txt"



def main():

    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:

        cfg = json.load(f)



    df = fetch_bid_data(

        api_key_file=API_KEY_FILE,

        industry_codes=cfg["industry_codes"],

        days_offset=cfg["days_offset"],

    )



    if df.empty:

        print("[INFO] 신규 공고 없음")

        return



    save_folder = cfg["save_folder"]

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    file_path = os.path.join(save_folder, f"입찰공고_{now_str}.xlsx")



    df.to_excel(file_path, index=False)

    print(f"[SAVE] 결과 저장: {file_path}")



    if cfg["kakao_enabled"]:

        notify_kakao(df, cfg["recipients"])

        print("[KAKAO] 알림톡 발송 완료")



if __name__ == "__main__":

    main()

