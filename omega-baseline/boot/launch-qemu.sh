#!/bin/sh
# Workspace-only QEMU runtime; no host install, daemon, KVM or automatic networking.
set -eu
BOOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="$BOOT/tooling/root"
export QEMU_MODULE_DIR="$ROOT/usr/lib/x86_64-linux-gnu/qemu"
exec "$ROOT/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2" \
 --library-path "$ROOT/usr/lib/x86_64-linux-gnu:$ROOT/lib/x86_64-linux-gnu" \
 "$ROOT/usr/bin/qemu-system-x86_64" -L "$ROOT/usr/share/qemu" \
 -bios "$ROOT/usr/share/seabios/bios-256k.bin" "$@"
