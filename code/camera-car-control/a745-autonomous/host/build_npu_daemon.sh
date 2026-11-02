#!/bin/sh
# Build on the 4A using headers compatible with its HHB 2.4.5 runtime.
set -eu
cd /home/debian/fpga
INCLUDE="${CSINN_INCLUDE:-/home/debian/shl-c920/c920/include}"
gcc -O2 -march=rv64gc -mabi=lp64d -Wall -Wextra -Werror \
    -I"$INCLUDE" yolov5_npu_daemon.c -o npu/yolov5_npu_daemon.new \
    -Wl,-l:libshl_th1520.so.2 -lm
mv npu/yolov5_npu_daemon.new npu/yolov5_npu_daemon
sha256sum npu/yolov5_npu_daemon npu/shl.hhb.bm
