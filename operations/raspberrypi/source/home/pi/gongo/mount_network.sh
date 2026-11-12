#!/bin/bash
# /home/pi/result/mount_network.sh

WIN_IP="192.168.1.100"
WIN_SHARE="VOL1/bid/bid/result"
WIN_USER="REDACTED_PRIVATE_VALUE"
WIN_PASS="REDACTED_PRIVATE_VALUE"
MOUNT_POINT="/mnt/vol1_bid"

echo "=== 네트워크 폴더 마운트 설정 ==="

if ! dpkg -s cifs-utils > /dev/null 2>&1; then
    echo "cifs-utils 설치 중..."
    sudo apt-get update -qq
    sudo apt-get install -y cifs-utils
fi

sudo mkdir -p "$MOUNT_POINT"

if mountpoint -q "$MOUNT_POINT"; then
    echo "기존 마운트 해제..."
    sudo umount "$MOUNT_POINT"
fi

sudo mount -t cifs "//${WIN_IP}/${WIN_SHARE}" "$MOUNT_POINT" \
    -o username="REDACTED_PRIVATE_VALUE",password="REDACTED_PRIVATE_VALUE",uid=pi,gid=pi,iocharset=utf8,vers=3.0,file_mode=0664,dir_mode=0775

if mountpoint -q "$MOUNT_POINT"; then
    echo "✅ 마운트 성공!"
    df -h | grep vol1_bid

    FSTAB_LINE="//${WIN_IP}/${WIN_SHARE} ${MOUNT_POINT} cifs username=${WIN_USER},password=${WIN_PASS},uid=pi,gid=pi,iocharset=utf8,vers=3.0,_netdev 0 0"
    if grep -q "$MOUNT_POINT" /etc/fstab; then
        sudo sed -i "\|${MOUNT_POINT}|d" /etc/fstab
    fi
    echo "$FSTAB_LINE" | sudo tee -a /etc/fstab > /dev/null
    echo "✅ fstab 자동 마운트 등록 완료"
else
    echo "❌ 마운트 실패! IP/경로/계정 확인 필요"
    exit 1
fi

