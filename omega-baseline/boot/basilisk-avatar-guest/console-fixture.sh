#!/bin/sh
/usr/bin/cosmic-term --no-daemon -e /usr/bin/python3.13 /opt/roko/scripts/roko.py --state-dir /root/.local/state/roko --avatar-events /run/user/0/roko/avatar.json console
rc=$?
echo "ROKO_AVATAR_CONSOLE_EXIT $rc" >/dev/console
case " $(/bin/busybox cat /proc/cmdline) " in
 *" roko.avatar_fixture=1 "*)
  [ "$rc" = 0 ] && /usr/bin/roko-avatar-finish
  ;;
esac
exit "$rc"
