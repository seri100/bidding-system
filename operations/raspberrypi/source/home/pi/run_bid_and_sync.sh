
#!/bin/bash

set -euo pipefail



LOG_DIR="/home/pi/logs"

mkdir -p "$LOG_DIR"



echo "[$(date '+%F %T')] START run_bid_and_sync"



# 1. 엑셀 자동생성

/usr/bin/python3 /home/pi/bid_collector/main.py



# 2. final_insert 적재

/bin/bash /home/pi/bidsync/run_cnstwk.sh

/bin/bash /home/pi/bidsync/run_thng.sh



echo "[$(date '+%F %T')] END run_bid_and_sync"

