#!/bin/sh
# Source from cosmic-desktop-stage; reuse verified compiler/cache without changing them.
DESKTOP_STAGE=$(pwd)
cd ../cosmic-comp-stage
. ./env.sh
cd "$DESKTOP_STAGE"
export PKG_CONFIG_LIBDIR="$DESKTOP_STAGE/sysroot/usr/lib/x86_64-linux-gnu/pkgconfig:$DESKTOP_STAGE/sysroot/usr/lib/pkgconfig:$DESKTOP_STAGE/sysroot/usr/share/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$DESKTOP_STAGE/sysroot"
export LD_LIBRARY_PATH="$DESKTOP_STAGE/sysroot/usr/lib/x86_64-linux-gnu:$DESKTOP_STAGE/sysroot/usr/lib/llvm-19/lib"
export LIBCLANG_PATH="$DESKTOP_STAGE/sysroot/usr/lib/llvm-19/lib"
export CMAKE="$DESKTOP_STAGE/sysroot/usr/bin/cmake"
# Supported gettext-sys option: GNU libc already exports gettext/libintl APIs.
export GETTEXT_SYSTEM=1
# Relocated libclang needs its pinned builtin headers and target multiarch includes.
export BINDGEN_EXTRA_CLANG_ARGS="--sysroot=$DESKTOP_STAGE/sysroot -resource-dir=$DESKTOP_STAGE/sysroot/usr/lib/llvm-19/lib/clang/19 -I$DESKTOP_STAGE/sysroot/usr/include/x86_64-linux-gnu"
