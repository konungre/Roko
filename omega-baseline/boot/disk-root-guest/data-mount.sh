#!/bin/sh
# Separate optional private controller disk. No-data mode stays explicitly ephemeral.
set -eu
BB=/bin/busybox
phase=none
for arg in $($BB cat /proc/cmdline); do
    case "$arg" in roko.root-data=none) phase=none;; roko.root-data=read) phase=read;; roko.root-data=write) phase=write;; esac
done
if [ "$phase" = none ]; then
    echo ROKO_ROOT_CONTROLLER_EPHEMERAL
    exit 0
fi
[ "$($BB cat /sys/block/vdb/serial)" = roko-root-controller ]
[ "$($BB cat /sys/block/vdb/size)" = 131072 ]
options=rw,nodev,nosuid,noexec
[ "$phase" = write ] || options=ro,noload,nodev,nosuid,noexec
$BB mount -t ext4 -o "$options" /dev/vdb /var/lib/roko
if [ "$phase" = write ]; then
    [ "$($BB ls -A /var/lib/roko)" = lost+found ]
    $BB chmod 700 /var/lib/roko
    echo ROKO_DESKTOP_STORAGE_BLANK
fi
[ "$($BB stat -c %u:%a /var/lib/roko)" = 0:700 ]
echo "ROKO_DESKTOP_STORAGE_MOUNTED $phase"
