#!/bin/sh
[ "$$" = 1 ] || exit 90
BB=/bin/busybox
finish() { echo ROKO_EGL_POWER_OFF; $BB sync; $BB poweroff -f; while :; do $BB sleep 1; done; }
fail() { echo "ROKO_EGL_GUEST_FAILED $1"; finish; }
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sysfs
$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs
exec </dev/console >/dev/console 2>&1
$BB mkdir -p /dev/shm /tmp /run/user/0
$BB mount -t tmpfs -o mode=1777 tmpfs /dev/shm || fail shm
$BB chmod 700 /run/user/0
export XDG_RUNTIME_DIR=/run/user/0
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export LIBGL_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
echo "ROKO_EGL_BUILD $($BB cat /etc/probe-id)"
( $BB sleep 45; fail watchdog ) &
watchdog=$!
/usr/bin/roko-egl-probe
rc=$?
$BB kill "$watchdog" 2>/dev/null
echo "ROKO_EGL_EXIT $rc"
[ "$rc" = 0 ] || fail probe
finish
