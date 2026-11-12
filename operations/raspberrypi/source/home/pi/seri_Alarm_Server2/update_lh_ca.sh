
#!/usr/bin/env bash

set -euo pipefail



LOG="/home/pi/seri_Alarm_Server2/update_lh_ca.log"

exec >>"$LOG" 2>&1

echo "===== $(date '+%F %T') update_lh_ca START ====="



SRC="/home/pi/seri_Alarm_Server2/ca_bundle.pem"

DST="/etc/ssl/seri/ca_bundle.pem"



sudo -n true 2>/dev/null || { echo "[ERR] sudo needs password. Run: sudo -v then retry."; exit 1; }



sudo cp "$SRC" "$DST"

sudo chmod 644 "$DST"

sudo systemctl restart lh-main.service



echo "[OK] updated $DST and restarted lh-main.service"

echo "===== $(date '+%F %T') update_lh_ca END ====="

