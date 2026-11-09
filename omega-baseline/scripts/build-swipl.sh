#!/bin/sh
# Build already-acquired official sources into this workspace; no downloads.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$ROOT/.venv/bin:$PATH"
cmake -S "$ROOT/build-src/swipl-10.0.2" -B "$ROOT/build/swipl" -G Ninja \
 -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ROOT/runtime/swipl" \
 -DINSTALL_DOCUMENTATION=OFF -DSWIPL_PACKAGE_LIST='clib;plunit;utf8proc;swipy;pcre' \
 -DPython_EXECUTABLE="$(command -v python3)"
cmake --build "$ROOT/build/swipl" --parallel 2
cmake --install "$ROOT/build/swipl"
