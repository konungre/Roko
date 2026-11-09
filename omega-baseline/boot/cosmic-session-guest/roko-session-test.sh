#!/bin/sh
# Installed only as a trusted diagnostic application. Not autostarted.
exec >/dev/console 2>&1
echo "ROKO_SESSION_TEST_LAUNCHED pid=$$ parent=$PPID"
exec /usr/bin/roko-wayland-client
