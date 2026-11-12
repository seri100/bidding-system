
from datetime import datetime

from app.lh_collector import run_lh_crawling



print("[MAIN] start:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))



rows = run_lh_crawling()



print(f"[MAIN] LH rows count: {len(rows)}")



for i, row in enumerate(rows[:3]):

    print(f"[SAMPLE {i+1}] {row}")



print("[MAIN] end")

