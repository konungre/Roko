#!/bin/sh
# Explicit one-job offline compositor build; no installation or service startup.
set -eu
cd "$(dirname "$0")"
. ./env.sh
[ -f debian-files.lock.json ] || { echo 'Verified native sysroot is not ready' >&2; exit 1; }
[ -f rust-sources.lock.json ] || { echo 'Verified Rust source closure is not ready' >&2; exit 1; }
exec cargo build --locked --offline --no-default-features --bin cosmic-comp --manifest-path source/Cargo.toml -j 1
