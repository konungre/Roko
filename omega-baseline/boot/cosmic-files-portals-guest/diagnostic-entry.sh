#!/bin/sh
# Place alongside unchanged probe.py and diagnose.py in guest /run test delta.
set -eu
[ -f /run/roko-files-portals-guest ] || { echo 'Guest marker absent' >&2; exit 1; }
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
  prepare|inspect|processes|bus-owners|assert-copy|assert-rename|assert-trash)
    exec /usr/bin/python3.13 "$HERE/diagnose.py" "$1" ;;
  files-debug)
    # Original executable; log redirection belongs to the test harness.
    export WAYLAND_DEBUG=client ICED_BACKEND=tiny-skia
    exec /usr/bin/cosmic-files /root/.local/share/roko-portal-fixture ;;
  chooser-cancel|chooser-select|settings|show-items)
    exec /usr/bin/python3.13 "$HERE/probe.py" "$1" --timeout 90 ;;
  *) echo 'Expected fixture/evidence mode, files-debug, or existing portal probe mode' >&2; exit 2 ;;
esac
