
#!/usr/bin/env bash

set -euo pipefail



FTP_HOST="REDACTED_PRIVATE_VALUE"

FTP_USER="REDACTED_PRIVATE_VALUE"

FTP_PASS="REDACTED_PRIVATE_VALUE"

FTP_DIR="REDACTED_PRIVATE_VALUE"



if [ $# -lt 1 ]; then

  echo "[ERR] usage: $0 /path/to/file.xlsx"

  exit 2

fi



FILE="$1"

if [ ! -f "$FILE" ]; then

  echo "[ERR] not a file: $FILE"

  exit 3

fi



# 업로드 (한 파일 put, 한글파일명도 안전)

lftp -u "${FTP_USER},${FTP_PASS}" -p 21 "${FTP_HOST}" <<LFTP

set xfer:clobber on

set ftp:charset UTF-8

set file:charset UTF-8

cd ${FTP_DIR}

put -O ${FTP_DIR} "$FILE"

bye

LFTP



echo "[OK] FTP uploaded: $(basename "$FILE") -> ${FTP_HOST}:${FTP_DIR}"

