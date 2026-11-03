#!/bin/sh
# Start the FPGA EV10 video + YOLO web service, safely and detached.
# Uses a PID file instead of pattern-matching kills, so the wrapper cannot
# kill itself (pkill -f matched its own ssh command line).
#
# usage: start_video.sh [0|1] [npu|cpu]
set -eu
cd /home/debian/fpga

ENABLE="${1:-1}"
BACKEND="${2:-npu}"
PID=/home/debian/fpga/.video.pid
DAEMON_PID=/home/debian/fpga/.npu.pid

# Stop any previous instance by recorded PID only.
if [ -f "$PID" ]; then
    kill "$(cat "$PID")" 2>/dev/null || true
    sleep 2
fi
if [ -f "$DAEMON_PID" ]; then
    kill "$(cat "$DAEMON_PID")" 2>/dev/null || true
fi
# Fall back to fuser only if a PID file is stale but the port is still held.
for P in 8090/tcp 6104/udp; do
    HOLDER=$(fuser "$P" 2>/dev/null | tr -d ' ' || true)
    if [ -n "$HOLDER" ]; then
        for H in $HOLDER; do kill -9 "$H" 2>/dev/null || true; done
        sleep 1
    fi
done

if [ "$ENABLE" = "1" ]; then
    export YOLO_BACKEND="$BACKEND"
    export YOLO_ENABLE=1
else
    export YOLO_BACKEND=npu
    export YOLO_ENABLE=0
fi
export VIDEO_HTTP_PORT="${VIDEO_HTTP_PORT:-8090}"

setsid nohup ./venv-system/bin/python -u fpga_video_yolo_web.py \
    < /dev/null > video.log 2>&1 &
NEWPID=$!
echo "$NEWPID" > "$PID"

sleep 2
echo "pid: $NEWPID"
echo "YOLO_ENABLE=$YOLO_ENABLE YOLO_BACKEND=$YOLO_BACKEND"
