#!/bin/bash

set -eu

(set -o pipefail) 2>/dev/null || true



SHARE="//192.168.0.250/bid"

MNT="/mnt/vol1"

CREDS="/root/.smbcredentials-bid"

OPTS_BASE="credentials=$CREDS,sec=ntlmssp,uid=1000,gid=1000,dir_mode=0755,file_mode=0644,iocharset=utf8,cache=strict"

VERS=("3.11" "3.0" "2.1" "2.0" "1.0")



echo "[INFO] Preparing mountpoint: $MNT"

mkdir -p "$MNT"



echo "[INFO] Unmounting previous mount (if any)"

fuser -vm "$MNT" 2>/dev/null || true

umount "$MNT" 2>/dev/null || true

umount -l "$MNT" 2>/dev/null || true



modprobe cifs || true



CHOSEN=""

for v in "${VERS[@]}"; do

  echo "[TRY] vers=$v"

  if mount -t cifs "$SHARE" "$MNT" -o "$OPTS_BASE,vers=$v"; then

    CHOSEN="$v"

    echo "[OK] Mounted with vers=$v"

    break

  else

    echo "[NG] vers=$v failed"

  fi

done



if [[ -z "$CHOSEN" ]]; then

  echo "[ERR] All SMB versions failed."

  exit 1

fi



echo "[INFO] Update /etc/fstab"

cp /etc/fstab /etc/fstab.bak.$(date +%F_%H%M%S)

sed -i "\|$SHARE $MNT |d" /etc/fstab

echo "$SHARE  $MNT  cifs  $OPTS_BASE,vers=$CHOSEN,x-systemd.automount,_netdev,nofail  0  0" >> /etc/fstab

systemctl daemon-reload



# quick write test

mkdir -p "$MNT/road"

echo "hello $(date)" > "$MNT/road/_conn_test3.txt"

ls -l "$MNT/road/_conn_test3.txt"

