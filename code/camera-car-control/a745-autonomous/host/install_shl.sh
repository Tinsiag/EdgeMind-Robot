#!/bin/sh
# Install the T-Head SHL (csi-nn2) C920 runtime libraries.
#
# onnxruntime's ShlExecutionProvider needs these in the system library path.
# Without them it crashed the process with SIGILL on this board. Procedure is
# from the Sipeed LPi4A wiki, "8_application" / NPU section.
set -eu

DIR=/home/debian/shl-c920
rm -rf "$DIR"
mkdir -p "$DIR"
cd "$DIR"

URL=https://github.com/T-head-Semi/csi-nn2/releases/download/v2.4-beta.1/c920.tar.gz
echo "downloading $URL"
wget -q --show-progress -O c920.tar.gz "$URL"
ls -la c920.tar.gz

tar xf c920.tar.gz
echo "--- extracted:"
find . -name '*.so*' | head -20

echo "--- installing to /usr/lib/riscv64-linux-gnu/"
echo debian | sudo -S cp -rf c920/lib/* /usr/lib/riscv64-linux-gnu/
echo debian | sudo -S ldconfig
echo "--- installed:"
ls -la /usr/lib/riscv64-linux-gnu/ | grep -iE 'shl|csi' | head
