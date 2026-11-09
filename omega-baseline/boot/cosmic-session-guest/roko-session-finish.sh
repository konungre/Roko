#!/bin/sh
# Uses the real upstream session interface, not kill-as-success.
exec >/dev/console 2>&1
echo ROKO_SESSION_EXIT_REQUEST
exec /usr/bin/dbus-send --session --type=method_call --print-reply --dest=com.system76.CosmicSession /com/system76/CosmicSession com.system76.CosmicSession.Exit
