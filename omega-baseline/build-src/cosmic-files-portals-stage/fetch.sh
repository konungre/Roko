#!/bin/sh
set -eu
cd "$(dirname "$0")/../cosmic-desktop-stage"
. ./env.sh
cd ../cosmic-files-portals-stage
cargo fetch --locked --manifest-path sources/xdg-desktop-portal-cosmic/Cargo.toml
cargo metadata --locked --offline --no-default-features --filter-platform x86_64-unknown-linux-gnu --format-version 1 --manifest-path sources/xdg-desktop-portal-cosmic/Cargo.toml > logs/portal-metadata.json
