#!/bin/sh
# usage: sh start_video.sh [0|1] [npu|cpu]
# Manage one service/cgroup so daemon children cannot outlive the web server.
set -eu
cd /home/debian/fpga
ENABLE="${1:-1}"
BACKEND="${2:-npu}"
case "$ENABLE" in 0|1) ;; *) echo 'enable must be 0 or 1' >&2; exit 2;; esac
case "$BACKEND" in npu|cpu) ;; *) echo 'backend must be npu or cpu' >&2; exit 2;; esac
mkdir -p "$HOME/.config/systemd/user"
cp fpga-video.service "$HOME/.config/systemd/user/fpga-video.service"
printf 'YOLO_ENABLE=%s\nYOLO_BACKEND=%s\n' "$ENABLE" "$BACKEND" > video.env.new
mv video.env.new video.env
systemctl --user daemon-reload
systemctl --user enable fpga-video.service
systemctl --user restart fpga-video.service
systemctl --user --no-pager status fpga-video.service
