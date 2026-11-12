#!/usr/bin/env bash
#!/bin/bash

set -e



cd /home/pi/seri_Alarm_Server2



# 가상환경 사용

. .venv/bin/activate



# 로그 디렉토리

mkdir -p logs



# 실행

python3 main.py >> logs/run_$(date +%Y%m%d).log 2>&1


