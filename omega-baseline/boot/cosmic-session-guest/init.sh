#!/bin/sh
# Guest PID 1 only. No Roko service/autonomy, host devices, or networking.
[ "$$" = 1 ] || exit 90
export PATH=/bin:/usr/bin:/usr/sbin
BB=/bin/busybox
finish() {
    echo ROKO_SESSION_POWER_OFF
    $BB sync
    $BB poweroff -f
    while :; do $BB sleep 1; done
}
fail() { echo "ROKO_SESSION_FAILED $1"; finish; }
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sysfs
$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs
exec </dev/console >/dev/console 2>&1
$BB mkdir -p /dev/pts /dev/shm /run/udev /run/user/0 /tmp /root/.config /root/.cache
$BB mount -t devpts devpts /dev/pts || fail devpts
$BB mount -t tmpfs -o mode=1777 tmpfs /dev/shm || fail shm
$BB chmod 700 /run/user/0
$BB chmod 1777 /tmp
export LANGUAGE=en_US:en
export LANG=C.UTF-8 LC_ALL=C.UTF-8 SHELL=/bin/sh TERM=xterm-256color
export HOME=/root XDG_RUNTIME_DIR=/run/user/0 XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=COSMIC XDG_SESSION_DESKTOP=COSMIC
export XDG_DATA_DIRS=/usr/share XDG_CONFIG_DIRS=/etc
export XKB_CONFIG_ROOT=/usr/share/X11/xkb FONTCONFIG_FILE=/etc/fonts/fonts.conf
export LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock SEATD_VTBOUND=0
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe LP_NUM_THREADS=1
export LIBGL_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
export RUST_LOG=info COSMIC_BACKEND=kms WGPU_BACKEND=gl
unset DISPLAY WAYLAND_DISPLAY WAYLAND_SOCKET
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus
echo "ROKO_SESSION_BUILD $($BB cat /etc/probe-id)"
[ "$($BB uname -r)" = "$($BB cat /etc/kernel-release)" ] || fail kernel-release
/usr/lib/systemd/systemd-udevd --daemon || fail udevd
while read -r module; do
    $BB insmod "/modules/$module.ko" || fail "insmod-$module"
done </etc/module-order
/usr/bin/udevadm trigger --action=add || fail udev-trigger
/usr/bin/udevadm settle --timeout=15 || fail udev-settle
for event in /dev/input/event*; do
    echo "ROKO_SESSION_INPUT_DEVICE $event"
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
echo ROKO_SESSION_SERVICES_READY
# Real session creates compositor/panel/notification sockets. No kiosk child.
/usr/bin/pipewire >/run/pipewire.log 2>&1 &
pipewire_pid=$!
/usr/bin/wireplumber >/run/wireplumber.log 2>&1 &
wireplumber_pid=$!
( $BB sleep 300; echo ROKO_SESSION_FAILED guest-watchdog; finish ) &
watchdog_pid=$!
/usr/bin/cosmic-session cosmic-comp --no-xwayland &
session_pid=$!
(
    while $BB kill -0 "$session_pid" 2>/dev/null; do
        echo ROKO_SESSION_PROCESS_SNAPSHOT_BEGIN
        for task in /proc/[0-9]*/comm; do
            name=$($BB cat "$task" 2>/dev/null)
            case "$name" in cosmic-*|pop-launcher*|pipewire|wireplumber)
                echo "ROKO_SESSION_PROCESS ${task%/comm} $name" ;;
            esac
            if [ "$name" = cosmic-term ]; then
                echo "ROKO_TERMINAL_PROC_BEGIN ${task%/comm}"
                $BB cat "${task%/comm}/status"
                $BB ls -l "${task%/comm}/fd"
                for thread in "${task%/comm}"/task/*; do
                    echo "ROKO_TERMINAL_THREAD $thread"
                    for child in $($BB cat "$thread/children"); do
                        echo "ROKO_TERMINAL_CHILD $child"
                        $BB cat "/proc/$child/status" "/proc/$child/stat"
                        $BB ls -l "/proc/$child/fd"
                    done
                    $BB cat "$thread/stat" "$thread/wchan" "$thread/syscall" "$thread/stack" 2>&1
                done
                echo ROKO_TERMINAL_PROC_END
            fi
        done
        echo ROKO_SESSION_PROCESS_SNAPSHOT_END
        $BB sleep 5
    done
) &
monitor_pid=$!
wait "$session_pid"
rc=$?
$BB kill "$watchdog_pid" "$monitor_pid" "$pipewire_pid" "$wireplumber_pid" 2>/dev/null
for file in /run/pipewire.log /run/wireplumber.log; do
    echo "ROKO_SESSION_SERVICE_LOG $file"
    $BB tail -n 40 "$file"
done
echo "ROKO_SESSION_EXIT $rc"
[ "$rc" = 0 ] || fail session-exit
finish
