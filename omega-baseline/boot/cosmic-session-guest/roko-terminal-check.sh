#!/bin/sh
# Explicitly typed into the real terminal by the bounded diagnostic runner.
BB=/bin/busybox
pid=$PPID
found=0
for depth in 1 2 3 4 5 6; do
    [ -r "/proc/$pid/comm" ] || break
    name=$($BB cat "/proc/$pid/comm")
    case "$name" in cosmic-term*) found=1 ;; esac
    pid=$($BB awk '/^PPid:/ {print $2}' "/proc/$pid/status")
done
if [ "$found" != 1 ]; then
    echo ROKO_TERMINAL_FAILED no-real-terminal-ancestor >/dev/console
    exit 1
fi
printf '\nROKO_TERMINAL_INPUT_OK\n'
echo ROKO_TERMINAL_INPUT_OK >/dev/console
