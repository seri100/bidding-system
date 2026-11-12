
#!/bin/bash

set -euo pipefail



BASE="REDACTED_PRIVATE_VALUE/exports"

DAILY="$BASE/daily"



# run별 CSV 삭제

find "$BASE" -maxdepth 1 -type f -name "LH_*.csv" -mtime +30 -print -delete || true



# daily (wd/we) CSV 삭제

find "$DAILY" -type f -name "LH_*.csv" -mtime +30 -print -delete || true

