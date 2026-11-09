#!/bin/sh
# Guest-only PID 1. Never run this file on the host.
[ "$$" = 1 ] || exit 90
export PATH=/bin
BB=/bin/busybox
finish() {
    echo ROKO_GRAPHICS_POWER_OFF
    $BB sync
    $BB poweroff -f
    while :; do $BB sleep 1; done
}
fail() {
    echo "ROKO_GRAPHICS_FAILED $1"
    finish
}
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sysfs
$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs
exec </dev/console >/dev/console 2>&1
echo "ROKO_GRAPHICS_BUILD $( $BB cat /etc/probe-id )"
release=$($BB uname -r)
[ "$release" = "$( $BB cat /etc/kernel-release )" ] || fail kernel-release
echo "ROKO_GRAPHICS_KERNEL $release"
while read -r module; do
    $BB insmod "/modules/$module.ko" || fail "insmod-$module"
done </etc/module-order
for card in /sys/class/drm/card[0-9]*; do
    echo "ROKO_GRAPHICS_DIAGNOSTIC $card"
    $BB ls -l "$card/device" "$card/device/driver" "$card/device/driver/module" /dev/dri 2>/dev/null
done
found=0
attempt=0
while [ "$attempt" -lt 10 ]; do
    for card in /sys/class/drm/card[0-9]*; do
        [ -e "$card/device/driver" ] || continue
        name=${card##*/}
        case "$name" in *-*) continue ;; esac
        [ -c "/dev/dri/$name" ] || continue
        # DRM's device points at the PCI transport on this kernel; the GPU
        # driver binds its virtio child, not the virtio-pci parent itself.
        gpu=0
        for driverpath in "$card/device/driver" "$card/device"/virtio*/driver; do
            [ -e "$driverpath" ] || continue
            driver=$($BB readlink -f "$driverpath")
            [ "${driver##*/}" = virtio_gpu ] && gpu=1
        done
        [ "$gpu" = 1 ] || continue
        for connector in "$card"/"$name"-* /sys/class/drm/"$name"-*; do
            [ -f "$connector/status" ] || continue
            [ "$( $BB cat "$connector/status" )" = connected ] || continue
            mode=$($BB head -n 1 "$connector/modes")
            [ -n "$mode" ] || continue
            dev=$($BB cat "$card/dev")
            echo "ROKO_GRAPHICS_CARD $name $dev virtio_gpu"
            echo "ROKO_GRAPHICS_CONNECTOR ${connector##*/} connected $mode"
            found=1
            break
        done
        [ "$found" = 1 ] && break
    done
    [ "$found" = 1 ] && break
    attempt=$((attempt + 1))
    $BB sleep 1
done
[ "$found" = 1 ] || fail no-connected-virtio-output
inputs=0
for event in /sys/class/input/event*; do
    name=${event##*/}
    [ -c "/dev/input/$name" ] || continue
    label=$($BB cat "$event/device/name")
    case "$label" in
        *[Vv]irtio*)
            echo "ROKO_GRAPHICS_INPUT $name $label"
            inputs=$((inputs + 1))
            ;;
    esac
done
[ "$inputs" -ge 2 ] || fail missing-virtio-inputs
echo ROKO_GRAPHICS_PLUMBING_PASSED
finish
