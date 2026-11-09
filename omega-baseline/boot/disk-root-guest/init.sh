#!/bin/sh
# Tiny initramfs PID1. Root disk is always read-only at both host and guest layers.
[ "$$" = 1 ] || exit 90
export PATH=/bin
BB=/bin/busybox
fail() { echo "ROKO_DISK_ROOT_FAILED $1"; $BB poweroff -f; while :; do $BB sleep 1; done; }
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sysfs
$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs
exec </dev/console >/dev/console 2>&1
[ "$($BB uname -r)" = "$($BB cat /etc/kernel-release)" ] || fail kernel
while read -r module; do $BB insmod "/modules/$module.ko" || fail "module-$module"; done </etc/module-order
for n in 1 2 3 4 5; do [ -b /dev/vda ] && break; $BB sleep 1; done
[ "$($BB cat /sys/block/vda/serial)" = roko-readonly-root ] || fail root-serial
[ "$($BB cat /sys/block/vda/size)" = 6291456 ] || fail root-size
[ "$($BB cat /sys/block/vda/ro)" = 1 ] || fail root-not-readonly
$BB mkdir -p /newroot
$BB mount -t ext4 -o ro,noload,nodev,nosuid /dev/vda /newroot || fail mount-root
expected=$($BB cat /etc/root-build-id)
[ "$expected" = "$($BB cat /newroot/etc/root-build-id)" ] || fail root-build-identity
for d in run tmp root var; do
    case "$d" in run) options=mode=0755,size=128m;; tmp) options=mode=1777,size=128m;; root) options=mode=0700,size=256m;; var) options=mode=0755,size=256m;; esac
    $BB mount -t tmpfs -o "$options",nodev,nosuid tmpfs "/newroot/$d" || fail "tmpfs-$d"
done
$BB cp -a /newroot/usr/share/roko/root-seed/. /newroot/root/ || fail seed-home
$BB mkdir -p /newroot/var/tmp /newroot/var/cache /newroot/var/log /newroot/var/lib/roko
$BB chmod 1777 /newroot/var/tmp
$BB chmod 700 /newroot/var/lib/roko
# Move pseudo filesystems, not static root files. switch_root releases bootstrap RAM.
$BB mount -o move /proc /newroot/proc || fail move-proc
$BB mount -o move /sys /newroot/sys || fail move-sys
$BB mount -o move /dev /newroot/dev || fail move-dev
exec /bin/busybox switch_root /newroot /usr/libexec/roko-session-init
