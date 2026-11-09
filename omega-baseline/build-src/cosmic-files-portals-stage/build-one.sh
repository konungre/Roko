#!/bin/bash
# One approved component only. Caller must reserve the shared heavy-work lane.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
[[ ${2:-} == --build ]] || { echo 'Usage: build-one.sh files|files-applet|portal --build (reserve resource lane first)'; exit 2; }
cd "$HERE/../cosmic-desktop-stage"
. ./env.sh
unset CARGO_PROFILE_DEV_DEBUG_ASSERTIONS CARGO_PROFILE_DEV_OPT_LEVEL
cd "$HERE"
case "$1" in
 files) manifest=../cosmic-desktop-stage/sources/cosmic-files/Cargo.toml; args=(-p cosmic-files --no-default-features --features dbus-config,desktop,gvfs,notify,wayland --bin cosmic-files);;
 files-applet) manifest=../cosmic-desktop-stage/sources/cosmic-files/Cargo.toml; args=(-p cosmic-files-applet --no-default-features --bin cosmic-files-applet);;
 portal) manifest=sources/xdg-desktop-portal-cosmic/Cargo.toml; args=(--no-default-features --bin xdg-desktop-portal-cosmic);;
 *) echo 'Unknown component' >&2; exit 2;;
esac
printf 'SOURCE=%s\nGENERIC_CPU=x86-64\nONE_JOB=1\n' "$manifest" > "logs/$1-build-command.txt"
printf '%q ' cargo build --locked --offline --manifest-path "$manifest" -j1 "${args[@]}" >> "logs/$1-build-command.txt"
exec timeout 3600 python3 ../../scripts/no-internet.py "$CARGO_HOME/../rust-1.93.0/bin/cargo" build --locked --offline --manifest-path "$manifest" -j1 "${args[@]}"
