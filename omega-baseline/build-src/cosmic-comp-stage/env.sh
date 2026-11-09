#!/bin/sh
# Source from this directory only; never changes host profiles or services.
COSMIC_STAGE=$(pwd)
unset LD_PRELOAD CARGO_ENCODED_RUSTFLAGS CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS
unset HOST_CFLAGS HOST_CXXFLAGS LDFLAGS
export CFLAGS="-march=x86-64 -mtune=generic"
export CXXFLAGS="$CFLAGS"
export CMAKE="$COSMIC_STAGE/sysroot/usr/bin/cmake"
export CARGO_HOME="$COSMIC_STAGE/cargo-home"
export CARGO_TARGET_DIR="$COSMIC_STAGE/target"
export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export CARGO_PROFILE_DEV_DEBUG=0
export CARGO_PROFILE_DEV_INCREMENTAL=false
export PATH="$COSMIC_STAGE/rust-1.93.0/bin:$PATH"
export PKG_CONFIG=/usr/bin/pkg-config
export PKG_CONFIG_LIBDIR="$COSMIC_STAGE/sysroot/usr/lib/x86_64-linux-gnu/pkgconfig:$COSMIC_STAGE/sysroot/usr/lib/pkgconfig:$COSMIC_STAGE/sysroot/usr/share/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$COSMIC_STAGE/sysroot"
export PKG_CONFIG_ALLOW_SYSTEM_LIBS=1
export PKG_CONFIG_ALLOW_SYSTEM_CFLAGS=1
export LIBCLANG_PATH="$COSMIC_STAGE/sysroot/usr/lib/llvm-19/lib"
export LD_LIBRARY_PATH="$COSMIC_STAGE/sysroot/usr/lib/x86_64-linux-gnu:$COSMIC_STAGE/sysroot/usr/lib/llvm-19/lib"
export RUSTFLAGS="-C target-cpu=x86-64 -L native=$COSMIC_STAGE/sysroot/usr/lib/x86_64-linux-gnu -C link-arg=-Wl,-rpath-link,$COSMIC_STAGE/sysroot/usr/lib/x86_64-linux-gnu"
export CC=/usr/bin/cc
export AR=/usr/bin/ar
export CXX=/usr/bin/c++
