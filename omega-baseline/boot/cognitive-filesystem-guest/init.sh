#!/bin/sh
export PATH=/bin
b=/bin/busybox
fail() { echo ROKO_EXT4_CONTROLLER_FAILED; $b poweroff -f; while :; do $b sleep 1; done; }
$b mount -t proc proc /proc || fail
$b mount -t sysfs sysfs /sys || fail
$b mount -t devtmpfs devtmpfs /dev || fail
exec </dev/console >/dev/console 2>&1
set -eu
trap fail EXIT
phase=
for arg in $($b cat /proc/cmdline); do
    case "$arg" in roko.controller=write) phase=write;; roko.controller=read) phase=read;; esac
done
[ -n "$phase" ] || fail
echo "ROKO_EXT4_CONTROLLER_BUILD $($b cat /etc/probe-id)"
[ "$($b uname -r)" = "$($b cat /etc/kernel-release)" ] || fail
while read -r module; do $b insmod "/modules/$module.ko" || fail; done </etc/module-order
for n in 1 2 3 4 5; do [ -b /dev/vda ] && break; $b sleep 1; done
[ "$($b cat /sys/block/vda/serial)" = roko-cognitive-state ] || fail
[ "$($b cat /sys/block/vda/size)" = 131072 ] || fail
options=rw,nodev,nosuid,noexec
[ "$phase" = write ] || options=ro,noload,nodev,nosuid,noexec
$b mount -t ext4 -o "$options" /dev/vda /data || fail
export PYTHONHOME=/opt/roko/python
/opt/roko/python/bin/python3.12 /opt/roko/ext4-check.py "$phase" || fail
$b umount /data || fail
echo ROKO_EXT4_CONTROLLER_UNMOUNTED
trap - EXIT
$b poweroff -f
