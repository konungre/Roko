#!/bin/sh
set -eu
BB=/bin/busybox
if $BB grep -q '^/dev/vdb /var/lib/roko ext4 ' /proc/mounts; then
    $BB umount /var/lib/roko
    echo ROKO_DESKTOP_STORAGE_UNMOUNTED
else
    echo ROKO_ROOT_CONTROLLER_EPHEMERAL
fi
