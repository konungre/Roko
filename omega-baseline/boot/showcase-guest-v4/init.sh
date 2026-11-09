#!/bin/sh
# Live prototype bootstrap, guest PID 1 only. Never a host setup script.
[ "$$" = 1 ] || exit 90
export PATH=/bin
BB=/bin/busybox
fail() {
    echo "ROKO_LIVE_BOOT_FAILED $1"
    $BB sleep 15
    $BB poweroff -f
    while :; do $BB sleep 1; done
}
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sysfs
$BB mount -t devtmpfs devtmpfs /dev || fail devtmpfs
exec </dev/console >/dev/console 2>&1
[ "$($BB uname -r)" = "$($BB cat /etc/kernel-release)" ] || fail kernel
$BB mount -t tmpfs -o mode=0755,size=192m,nodev,nosuid tmpfs /run || fail runtime
while read -r module; do
    [ -d "/sys/module/$module" ] || $BB insmod "/modules/$module.ko" || fail "module-$module"
done </etc/early-module-order
$BB mkdir -p /run/roko-live-media /run/roko-live-lower /run/roko-live-cow /newroot
# Only ISO9660 with the fixed label is admissible. Never mount another disk.
# Repeated matching labels are rejected, not silently chosen.
chosen=
n=0
while [ "$n" -lt 30 ]; do
    chosen=
    matches=0
    for entry in /sys/class/block/*; do
        name=${entry##*/}
        [ ! -f "$entry/partition" ] || continue
        case "$name" in sd[a-z]|sd[a-z][a-z]|sd[a-z][0-9]*|sr[0-9]*|vd[a-z]|vd[a-z][0-9]*|nvme[0-9]*n[0-9]*|mmcblk[0-9]*) ;;
            *) continue;;
        esac
        [ -b "/dev/$name" ] || continue
        # The pinned BusyBox lacks blkid. Read only the 7-byte ISO9660
        # primary-volume signature and 32-byte volume ID, never a root guess.
        # The packager's xorriso image contract puts the primary descriptor at LBA16.
        signature=$($BB dd if="/dev/$name" bs=1 skip=32768 count=7 2>/dev/null | $BB od -An -tx1 | $BB tr -d ' \n')
        [ "$signature" = 01434430303101 ] || continue
        label=$($BB dd if="/dev/$name" bs=1 skip=32808 count=32 2>/dev/null | $BB sed 's/ *$//')
        [ "$label" = ROKO_SHOWCASE ] || continue
        matches=$((matches + 1))
        chosen="/dev/$name"
    done
    [ "$matches" -le 1 ] || fail ambiguous-media
    [ "$matches" = 1 ] && break
    $BB sleep 1
    n=$((n + 1))
done
[ -n "$chosen" ] || fail media-not-found
$BB mount -t iso9660 -o ro,nodev,nosuid,noexec "$chosen" /run/roko-live-media || fail mount-media
manifest=/run/roko-live-media/roko/media-manifest.json
[ -f "$manifest" ] && [ ! -L "$manifest" ] || fail manifest-missing
[ "$($BB sha256sum "$manifest" | $BB cut -d ' ' -f 1)" = "$($BB cat /etc/media-manifest.sha256)" ] || fail manifest-hash
root=/run/roko-live-media/roko/root.ext4
[ -f "$root" ] && [ ! -L "$root" ] || fail root-missing
[ "$($BB stat -c %s "$root")" = 3221225472 ] || fail root-size
echo ROKO_LIVE_VERIFY_ROOT
[ "$($BB sha256sum "$root" | $BB cut -d ' ' -f 1)" = b7770c5352b5a38cbe5f9825133e381ba5e2772874d81e991ce04c1c2152e933 ] || fail root-hash
# BusyBox mount's read-only loop option opens the backing image read-only.
$BB mount -t ext4 -o loop,ro,noload,nodev,nosuid "$root" /run/roko-live-lower || fail mount-root
$BB mount -t tmpfs -o mode=0700,size=768m,nodev,nosuid tmpfs /run/roko-live-cow || fail cow
$BB mkdir -p /run/roko-live-cow/upper /run/roko-live-cow/work
$BB mount -t overlay -o lowerdir=/run/roko-live-lower,upperdir=/run/roko-live-cow/upper,workdir=/run/roko-live-cow/work,nodev,nosuid overlay /newroot || fail overlay
$BB cp -a /payload/root/. /newroot/ || fail copy-overlay
$BB cp -a /payload/run/. /run/ || fail copy-runtime
$BB mkdir -p /newroot/usr/lib/roko-showcase/modules
$BB cp -a /modules/. /newroot/usr/lib/roko-showcase/modules/ || fail copy-modules
# Seed only cosmetic user config, never the historical protected state.
$BB mkdir -p /newroot/root/.config
$BB cp -a /newroot/usr/share/roko/root-seed/. /newroot/root/ || fail seed-config
$BB cp /newroot/etc/roko-showcase/background.ron /newroot/root/.config/cosmic/com.system76.CosmicBackground/v1/all || fail wallpaper
# Eliminate old AI/fixture launchers in RAM only; original root stays unchanged.
for name in roko roko-corner com.roko.Terminal com.roko.GraphicsTest; do
    $BB rm -f "/newroot/usr/share/applications/$name.desktop" || fail old-launcher
 done
$BB mkdir -p /newroot/root/.config/cosmic/com.system76.CosmicAppList/v1
printf '["com.system76.CosmicFiles", "com.system76.CosmicTerm"]\n' >/newroot/root/.config/cosmic/com.system76.CosmicAppList/v1/favorites
$BB mkdir -p /newroot/var/lib/roko/live-requests /newroot/var/log /newroot/var/cache /newroot/var/tmp /newroot/tmp
$BB chmod 700 /newroot/var/lib/roko /newroot/var/lib/roko/live-requests /newroot/root
$BB chmod 1777 /newroot/tmp /newroot/var/tmp
$BB mount -o move /proc /newroot/proc || fail move-proc
$BB mount -o move /sys /newroot/sys || fail move-sys
$BB mount -o move /dev /newroot/dev || fail move-dev
$BB mount -o move /run /newroot/run || fail move-run
exec /bin/busybox switch_root /newroot /usr/libexec/roko-showcase-session
