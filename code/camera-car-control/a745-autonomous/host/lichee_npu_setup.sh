#!/bin/sh
set -eu
# RevyOS 6.6 keeps the TH1520 NPU modules in the in-tree driver directory;
# the packaged insmod.sh still points at the old /extra layout.
sudo /sbin/modprobe img_mem
sudo /sbin/modprobe vha onchipmem_phys_start=0xffe0001000 onchipmem_size=0x100000 freq_khz=792000
sudo /sbin/modprobe vha_info
sudo chmod a+rw /dev/vha0 /dev/vha_scope 2>/dev/null || true
lsmod | grep -E '^(img_mem|vha|vha_info) ' || true
ls -l /dev/vha0 /dev/vha_scope
