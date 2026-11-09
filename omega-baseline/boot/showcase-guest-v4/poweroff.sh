#!/bin/sh
# Only the dedicated live guest has this marker. No host power action.
[ -f /run/roko-showcase/live-guest ] || exit 90
[ "$(/bin/busybox id -u)" = 0 ] || exit 90
/bin/busybox kill -TERM 1
