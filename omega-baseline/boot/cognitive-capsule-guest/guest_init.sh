#!/bin/sh
# Serial-only PID1; uses the current read-only COSMIC root, never starts desktop.
[ "$$" = 1 ] || exit 90
BB=/bin/busybox
export PATH=/usr/bin:/bin
export LANG=C.UTF-8
exec </dev/console >/dev/console 2>&1
(
    $BB sleep 240
    echo ROKO_COGNITIVE_GUEST_WATCHDOG
    $BB poweroff -f
) &
watchdog=$!
echo ROKO_COGNITIVE_GUEST_STARTED
/usr/bin/python3.13 -B /run/roko-cognitive-gate/guest_driver.py
code=$?
echo "ROKO_COGNITIVE_GUEST_EXIT $code"
$BB kill "$watchdog" 2>/dev/null || :
$BB sync
$BB poweroff -f
while :; do $BB sleep 1; done
