#!/bin/sh
# Actual guest session environment for authentic D-Bus activation, no host service.
BB=/bin/busybox
i=0
while [ "$i" -lt 120 ]; do
 for socket in "$XDG_RUNTIME_DIR"/wayland-*; do
  if [ -S "$socket" ]; then
   export WAYLAND_DISPLAY="${socket##*/}"
   [ -n "$WAYLAND_DISPLAY" ] && [ -n "$XDG_RUNTIME_DIR" ] && [ -n "$XDG_CURRENT_DESKTOP" ] || exit 92
   /usr/bin/dbus-update-activation-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR XDG_CURRENT_DESKTOP || exit 93
   echo "ROKO_PORTAL_ACTIVATION_ENV $WAYLAND_DISPLAY $XDG_RUNTIME_DIR $XDG_CURRENT_DESKTOP"
   case " $($BB cat /proc/cmdline) " in
    *" roko.files_fixture=1 "*)
     : >/run/roko-files-portals-guest
     echo ROKO_FILES_DIRECT_TERMINAL_FIXTURE
     /usr/bin/roko-terminal-launch >/dev/console 2>&1 &
     ;;
   esac
   exit 0
  fi
 done
 $BB sleep 1;i=$((i+1))
done
echo ROKO_PORTAL_ACTIVATION_ENV_TIMEOUT
exit 94
