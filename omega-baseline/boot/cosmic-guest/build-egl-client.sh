#!/bin/sh
# Workspace-only compilation, no host installation or guest execution.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SYSROOT="$ROOT/build-src/cosmic-comp-stage/sysroot"
mkdir -p "$ROOT/build/egl-probe"
cc -std=c11 -O2 -march=x86-64 -mtune=generic -Wall -Wextra -Werror \
  -I"$SYSROOT/usr/include" "$ROOT/boot/cosmic-guest/egl-probe.c" \
  -L"$SYSROOT/usr/lib/x86_64-linux-gnu" \
  -Wl,-rpath-link,"$SYSROOT/usr/lib/x86_64-linux-gnu" \
  -lEGL -lGLESv2 -o "$ROOT/build/egl-probe/roko-egl-probe"
