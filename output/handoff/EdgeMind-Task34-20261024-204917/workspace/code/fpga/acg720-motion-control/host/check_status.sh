#!/usr/bin/env bash

# 提前验证 sudo 权限，避免循环中反复提示输入密码
sudo -v || exit 1

while true; do
    sudo ./.venv/bin/python serial_control.py --port /dev/ttyUSB0 status
    sleep 0.5
done
