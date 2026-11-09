#!/bin/sh
exec >/dev/console 2>&1
echo ROKO_AVATAR_FIXTURE_SESSION_EXIT_REQUEST
exec /bin/busybox timeout 5 /usr/bin/dbus-send --session --type=method_call --print-reply --dest=com.system76.CosmicSession /com/system76/CosmicSession com.system76.CosmicSession.Exit
