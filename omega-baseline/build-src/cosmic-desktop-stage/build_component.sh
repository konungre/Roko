#!/bin/sh
set -eu
cd "$(dirname "$0")"
. ./env.sh
component=$1
shift
[ -f debian-files.lock.json ] || { echo 'Native sysroot not ready' >&2; exit 1; }
exec cargo build --locked --offline --manifest-path "sources/$component/Cargo.toml" -j1 "$@"
