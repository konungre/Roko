#!/bin/sh
exec >/dev/console 2>&1
export GDK_BACKEND=wayland
echo ROKO_AVATAR_LAUNCHED
exec /usr/bin/python3.13 -u /usr/libexec/roko-avatar-observe.py /usr/share/roko/basilisk --overlay --events /run/user/0/roko/avatar.json
