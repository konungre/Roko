#!/bin/sh
set -eu
BB=/bin/busybox
phase=
for arg in $($BB cat /proc/cmdline); do
    case "$arg" in roko.desktop-storage=write) phase=write;; roko.desktop-storage=read) phase=read;; esac
done
[ -n "$phase" ]
echo "ROKO_DESKTOP_STORAGE_BUILD $($BB cat /etc/storage-probe-id)"
while read -r module; do
    [ -d "/sys/module/$module" ] || $BB insmod "/storage-modules/$module.ko"
done </etc/storage-module-order
for n in 1 2 3 4 5; do [ -b /dev/vda ] && break; $BB sleep 1; done
[ "$($BB cat /sys/block/vda/serial)" = roko-desktop-state ]
[ "$($BB cat /sys/block/vda/size)" = 131072 ]
$BB mkdir -p /var/lib/roko
options=rw,nodev,nosuid,noexec
[ "$phase" = write ] || options=ro,noload,nodev,nosuid,noexec
$BB mount -t ext4 -o "$options" /dev/vda /var/lib/roko
if [ "$phase" = write ]; then
    # Never reuse a populated data disk for a fresh desktop proof.
    [ "$($BB ls -A /var/lib/roko)" = lost+found ]
    $BB chmod 700 /var/lib/roko
    echo ROKO_DESKTOP_STORAGE_BLANK
else
    [ "$($BB stat -c %a /var/lib/roko)" = 700 ]
fi
[ "$($BB stat -c %u /var/lib/roko)" = 0 ]
echo "ROKO_DESKTOP_STORAGE_MOUNTED $phase"
