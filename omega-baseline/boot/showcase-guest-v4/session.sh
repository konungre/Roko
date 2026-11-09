#!/bin/sh
# Dedicated live PID 1. This replaces, and never calls, the qualification init.
[ "$$" = 1 ] || exit 90
BB=/bin/busybox
export PATH=/usr/bin:/bin:/usr/sbin
fail() { echo "ROKO_LIVE_SESSION_FAILED $1"; $BB sleep 15; $BB poweroff -f; while :; do $BB sleep 1; done; }
exec </dev/console >/dev/console 2>&1
$BB mkdir -p /dev/pts /dev/shm /run/udev /run/user/0/roko /run/roko-showcase /root/.cache /etc/roko-showcase-xdg
$BB mount -t devpts devpts /dev/pts || fail devpts
$BB mount -t tmpfs -o mode=1777,size=128m,nodev,nosuid tmpfs /dev/shm || fail shm
$BB chmod 700 /run/user/0 /run/user/0/roko /run/roko-showcase
printf 'roko-live-prototype-v1\n' >/run/roko-showcase/live-guest
export LANGUAGE=en_US:en LANG=C.UTF-8 LC_ALL=C.UTF-8 SHELL=/bin/sh TERM=xterm-256color
export HOME=/root XDG_RUNTIME_DIR=/run/user/0 XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=COSMIC XDG_SESSION_DESKTOP=COSMIC
# Dedicated empty autostart directory prevents a future feature-enabled session
# from launching a second pet. The supervisor is the sole launch owner.
export XDG_DATA_DIRS=/usr/share XDG_CONFIG_DIRS=/etc/roko-showcase-xdg:/etc
export XKB_CONFIG_ROOT=/usr/share/X11/xkb FONTCONFIG_FILE=/etc/fonts/fonts.conf
export LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock SEATD_VTBOUND=0
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=2
export LIBGL_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
export COSMIC_BACKEND=kms WGPU_BACKEND=gl GDK_BACKEND=wayland RUST_LOG=warn
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
unset DISPLAY WAYLAND_DISPLAY WAYLAND_SOCKET
/usr/lib/systemd/systemd-udevd --daemon || fail udevd
while read -r module; do
    if [ ! -d "/sys/module/$module" ]; then
        $BB insmod "/usr/lib/roko-showcase/modules/$module.ko" || echo "ROKO_LIVE_OPTIONAL_MODULE_FAILED $module"
    fi
done </etc/roko-showcase/late-module-order
/usr/bin/udevadm trigger --action=add || fail udev-trigger
/usr/bin/udevadm settle --timeout=20 || fail udev-settle
exec /usr/bin/python3.13 -I -B /usr/libexec/roko-showcase-supervisor.py
