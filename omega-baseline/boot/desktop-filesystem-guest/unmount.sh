#!/bin/sh
set -eu
BB=/bin/busybox
if $BB grep -q '^/dev/vda /var/lib/roko ext4 ' /proc/mounts; then
    $BB umount /var/lib/roko
    echo ROKO_DESKTOP_STORAGE_UNMOUNTED
else
    echo ROKO_DESKTOP_STORAGE_NOT_MOUNTED
fi
