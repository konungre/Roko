#!/bin/sh
export PATH=/bin
b=/bin/busybox
fail() { echo ROKO_FILES_FAILED; $b poweroff -f; while :; do $b sleep 1; done; }
$b mount -t proc proc /proc || fail
$b mount -t sysfs sysfs /sys || fail
$b mount -t devtmpfs devtmpfs /dev || fail
exec </dev/console >/dev/console 2>&1
set -eu
trap fail EXIT
phase=
for arg in $($b cat /proc/cmdline); do
    case "$arg" in roko.files=write) phase=write;; roko.files=read) phase=read;; esac
done
[ -n "$phase" ] || fail
echo "ROKO_FILES_BUILD $($b cat /etc/probe-id)"
[ "$($b uname -r)" = "$($b cat /etc/kernel-release)" ] || fail
while read -r module; do $b insmod "/modules/$module.ko" || fail; done </etc/module-order
for n in 1 2 3 4 5; do [ -b /dev/vda ] && break; $b sleep 1; done
[ "$($b cat /sys/block/vda/serial)" = roko-private-files ] || fail
[ "$($b cat /sys/block/vda/size)" = 131072 ] || fail
options=rw,nodev,nosuid,noexec
[ "$phase" = write ] || options=ro,noload,nodev,nosuid,noexec
$b mount -t ext4 -o "$options" /dev/vda /data || fail
/bin/files-probe "$phase" || fail
$b umount /data || fail
echo ROKO_FILES_UNMOUNTED
trap - EXIT
$b poweroff -f
