#!/bin/sh
set -eu
cd "$(dirname "$0")"
STAGE=$(pwd)
cd ../cosmic-comp-stage
. ./env.sh
cd "$STAGE"
for component in "$@"; do
    test -f "sources/$component/Cargo.lock"
    echo "Fetching locked source dependencies: $component"
    cargo fetch --locked --target x86_64-unknown-linux-gnu --manifest-path "sources/$component/Cargo.toml" >"logs/$component-fetch.log" 2>&1
    cargo metadata --locked --offline --no-default-features --filter-platform x86_64-unknown-linux-gnu --format-version 1 --manifest-path "sources/$component/Cargo.toml" >"logs/$component-metadata.json" 2>"logs/$component-metadata.log"
done
