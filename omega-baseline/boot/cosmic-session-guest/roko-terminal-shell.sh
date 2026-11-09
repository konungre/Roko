#!/bin/sh
# Trace actual terminal PTY setup, then replace this wrapper with BusyBox ash.
echo "ROKO_TERMINAL_SHELL_READY pid=$$ parent=$PPID tty=$(/bin/busybox tty)" >/dev/console
exec /bin/sh -i
