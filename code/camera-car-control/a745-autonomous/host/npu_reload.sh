#!/bin/sh
# Reload the TH1520 NPU kernel modules with the on-chip-memory parameters.
#
# At boot the modules come up without them, and imgdnn then fails with
#   WARNING: Mapping to the on chip ram failed (128 > 0)
#   FATAL: Importing N bytes of CPU memory has failed (wrong memory alignment)
# modprobe will not re-apply parameters to an already-loaded module, so the
# stack has to be removed first. Also installs a udev rule so /dev/vha* stays
# world-accessible across reboots.
set -eu
PW=debian
s() { echo "$PW" | sudo -S "$@"; }

echo "--- before:"
lsmod | grep -E '^(img_mem|vha|vha_info) ' || echo "(none loaded)"

s rmmod vha_info 2>/dev/null || true
s rmmod vha      2>/dev/null || true
s rmmod img_mem  2>/dev/null || true

s modprobe img_mem
s modprobe vha onchipmem_phys_start=0xffe0001000 onchipmem_size=0x100000 freq_khz=792000
s modprobe vha_info

printf 'KERNEL=="vha*", MODE="0666"\n' > /tmp/99-vha.rules
s cp /tmp/99-vha.rules /etc/udev/rules.d/99-vha.rules
s chmod a+rw /dev/vha0 /dev/vha_scope 2>/dev/null || true

echo "--- after:"
lsmod | grep -E '^(img_mem|vha|vha_info) '
ls -l /dev/vha0 /dev/vha_scope
cat /etc/udev/rules.d/99-vha.rules
