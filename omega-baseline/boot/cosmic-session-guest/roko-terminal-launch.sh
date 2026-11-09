#!/bin/sh
# Diagnostic entry executes the unchanged real terminal and preserves its logs.
exec >/dev/console 2>&1
echo ROKO_TERMINAL_LAUNCHED
/usr/bin/cosmic-term --help
echo "ROKO_TERMINAL_HELP_EXIT $?"
exec /usr/bin/cosmic-term --no-daemon -e /usr/bin/roko-terminal-shell
