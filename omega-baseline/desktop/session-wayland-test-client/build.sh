#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)
STAGE=${COSMIC_STAGE:-$ROOT/build-src/cosmic-comp-stage}
SYSROOT=$STAGE/sysroot
OUT=$HERE/build
# Read-only use of the sibling's verified official stage. No install or download.
SCANNER=$SYSROOT/usr/bin/wayland-scanner
XML=${XDG_SHELL_XML:-$SYSROOT/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml}
if [ ! -f "$XML" ]; then
    set -- "$STAGE"/cargo-home/registry/src/*/wayland-protocols-0.32.13/protocols/stable/xdg-shell/xdg-shell.xml
    [ "$#" -eq 1 ] || { echo 'Set XDG_SHELL_XML to one verified pinned source XML' >&2; exit 1; }
    XML=$1
fi
[ -x "$SCANNER" ] && [ -f "$XML" ] && [ -f "$SYSROOT/usr/include/wayland-client.h" ] || {
    echo 'Official staged Wayland development dependencies are not ready' >&2; exit 1;
}
mkdir -p "$OUT"
# Limit staging LD_LIBRARY_PATH to scanner subprocess, not host compiler.
LD_LIBRARY_PATH="$SYSROOT/usr/lib/x86_64-linux-gnu" "$SCANNER" client-header "$XML" "$OUT/xdg-shell-client-protocol.h"
LD_LIBRARY_PATH="$SYSROOT/usr/lib/x86_64-linux-gnu" "$SCANNER" private-code "$XML" "$OUT/xdg-shell-protocol.c"
/usr/bin/cc -std=c11 -O2 -Wall -Wextra -Werror -march=x86-64 -mtune=generic \
    -I"$OUT" -I"$SYSROOT/usr/include" \
    "$HERE/main.c" "$OUT/xdg-shell-protocol.c" \
    -L"$SYSROOT/usr/lib/x86_64-linux-gnu" -Wl,-rpath-link,"$SYSROOT/usr/lib/x86_64-linux-gnu" \
    -lwayland-client -o "$OUT/roko-session-wayland-test"
sha256sum "$HERE/main.c" "$HERE/pattern.h" "$XML" "$OUT/roko-session-wayland-test" > "$OUT/build.sha256"
printf '%s\n' "$OUT/roko-session-wayland-test"
