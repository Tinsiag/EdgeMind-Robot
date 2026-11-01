#!/bin/sh
# Start the FPGA EV10 video + YOLO web service detached from this SSH session.
# usage: start_video.sh [YOLO_ENABLE] [YOLO_MODEL]
set -eu
cd /home/debian/fpga

pkill -f fpga_video_yolo_web.py 2>/dev/null || true
sleep 2

YOLO_ENABLE="${1:-1}"
YOLO_MODEL="${2:-/home/debian/fpga/yolov5n_cpu_fp32.onnx}"
export YOLO_ENABLE YOLO_MODEL
export VIDEO_HTTP_PORT="${VIDEO_HTTP_PORT:-8090}"

setsid nohup ./venv-system/bin/python -u fpga_video_yolo_web.py \
    < /dev/null > video.log 2>&1 &

sleep 8
echo "pid: $(pgrep -f 'python -u fpga_video_yolo_web.py' | head -1)"
echo "YOLO_ENABLE=$YOLO_ENABLE YOLO_MODEL=$YOLO_MODEL"
echo "--- log ---"
head -3 video.log
