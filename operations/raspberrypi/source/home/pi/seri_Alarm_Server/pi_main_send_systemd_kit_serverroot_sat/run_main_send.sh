#!/usr/bin/env bash
set -euo pipefail

# --- Paths ---
WORKDIR="/home/pi/seri_Alarm_Server"
LOGDIR="/mnt/vol1/seri_Alarm_Server/logs"
VENV="$WORKDIR/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
REQ="$WORKDIR/requirements.txt"

mkdir -p "$LOGDIR"

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
stdout_log="$LOGDIR/main_send.stdout.log"
stderr_log="$LOGDIR/main_send.stderr.log"

# --- Ensure venv & deps ---
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
"$PIP" install --upgrade pip >/dev/null 2>&1 || true
if [[ -f "$REQ" ]]; then
  "$PIP" install -r "$REQ" >/dev/null 2>&1 || true
fi

# --- Env ---
export PYTHONIOENCODING=utf-8
export TZ=Asia/Seoul

# --- Acquire lock to avoid overlap ---
LOCK="/run/lock/seri-main-send.lock"
mkdir -p /run/lock

cd "$WORKDIR"
/usr/bin/flock -n "$LOCK" bash -lc '{
  echo "['"${timestamp}"'] === main_send run ==="
  "'"$PY"'" -u "'"$WORKDIR"'/main_send.py"
}' 1>>"$stdout_log" 2>>"$stderr_log" || exit 0
