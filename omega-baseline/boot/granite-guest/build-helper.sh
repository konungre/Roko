#!/bin/sh
# Source preparation only until the coordinated heavy lane is explicitly held.
set -eu
case "${1:-}" in --build-after-lane-grant) ;; *) echo 'Explicit --build-after-lane-grant required; nothing built'; exit 2;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SOURCE="$ROOT/build-src/llama.cpp"
PIN=f7591a6a01f9273de03331732bdc0b39721168be
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$PIN"
test -z "$(git -C "$SOURCE" status --porcelain --untracked-files=no)"
export PATH="$ROOT/.venv/bin:$PATH"
cmake -S "$ROOT/boot/granite-guest" -B "$ROOT/build/granite-guest-helper" -G Ninja \
  -DLLAMA_SOURCE="$SOURCE"
cmake --build "$ROOT/build/granite-guest-helper" --target omega-granite-guest --parallel 1
# Only system ABI dependencies are allowed. No workspace library search path.
readelf -d "$ROOT/build/granite-guest-helper/omega-granite-guest"
if readelf -d "$ROOT/build/granite-guest-helper/omega-granite-guest" | grep -Eq 'RPATH|RUNPATH|libllama|libggml'; then
  echo 'Guest binary is not relocation safe' >&2; exit 1
fi
