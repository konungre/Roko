#!/bin/sh
# Guest PID 1 only. No Roko service/autonomy, host devices, or networking.
[ "$$" = 1 ] || exit 90
export PATH=/bin:/usr/bin:/usr/sbin
BB=/bin/busybox
finish() {
    echo ROKO_COSMIC_POWER_OFF
    $BB sync
    $BB poweroff -f
    while :; do $BB sleep 1; done
}
fail() { echo "ROKO_COSMIC_FAILED $1"; finish; }
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sysfs
$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs
exec </dev/console >/dev/console 2>&1
$BB mkdir -p /dev/pts /dev/shm /run/udev /run/user/0 /tmp /root/.config /root/.cache
$BB mount -t devpts devpts /dev/pts || fail devpts
$BB mount -t tmpfs -o mode=1777 tmpfs /dev/shm || fail shm
$BB chmod 700 /run/user/0
$BB chmod 1777 /tmp
export HOME=/root XDG_RUNTIME_DIR=/run/user/0 XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=COSMIC XDG_SESSION_DESKTOP=COSMIC
export XDG_DATA_DIRS=/usr/share XDG_CONFIG_DIRS=/etc
export XKB_CONFIG_ROOT=/usr/share/X11/xkb FONTCONFIG_FILE=/etc/fonts/fonts.conf
export LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock SEATD_VTBOUND=0
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export LIBGL_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
export RUST_LOG=info COSMIC_BACKEND=kms
unset DISPLAY WAYLAND_DISPLAY WAYLAND_SOCKET
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
echo "ROKO_COSMIC_BUILD $($BB cat /etc/probe-id)"
[ "$($BB uname -r)" = "$($BB cat /etc/kernel-release)" ] || fail kernel-release
/usr/lib/systemd/systemd-udevd --daemon || fail udevd
while read -r module; do
    $BB insmod "/modules/$module.ko" || fail "insmod-$module"
done </etc/module-order
/usr/bin/udevadm trigger --action=add || fail udev-trigger
/usr/bin/udevadm settle --timeout=15 || fail udev-settle
for event in /dev/input/event*; do
    echo "ROKO_COSMIC_INPUT_DEVICE $event"
    /usr/bin/udevadm info --query=property --name="$event"
done
/usr/bin/dbus-daemon --config-file=/etc/dbus-1/roko-session.conf --fork || fail dbus
/usr/sbin/seatd -u root -g root &
seat_pid=$!
i=0
while [ ! -S /run/seatd.sock ] && [ "$i" -lt 20 ]; do
    $BB kill -0 "$seat_pid" || fail seatd-exit
    $BB sleep 1
    i=$((i + 1))
done
[ -S /run/seatd.sock ] || fail seatd-socket
echo ROKO_COSMIC_SERVICES_READY
( $BB sleep 120; echo ROKO_COSMIC_FAILED guest-watchdog; finish ) &
watchdog_pid=$!
/usr/bin/cosmic-comp --no-xwayland /usr/bin/roko-wayland-client
rc=$?
$BB kill "$watchdog_pid" 2>/dev/null
echo "ROKO_COSMIC_EXIT $rc"
[ "$rc" = 0 ] || fail compositor-or-client-exit
finish
