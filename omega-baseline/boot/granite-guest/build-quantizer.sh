#!/bin/sh
# Compile only the official quantizer sources against existing pinned host libs.
set -eu
case "${1:-}" in --build-after-lane-grant) ;; *) echo 'Explicit --build-after-lane-grant required'; exit 2;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
test "$(git -C "$ROOT/build-src/llama.cpp" rev-parse HEAD)" = f7591a6a01f9273de03331732bdc0b39721168be
test -z "$(git -C "$ROOT/build-src/llama.cpp" status --porcelain --untracked-files=no)"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);lock=json.loads((root/'granite-runtime.lock.json').read_text())
for name,digest in lock['files'].items():
 if name.startswith('build/llama/bin/') and hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
  raise ValueError('Pinned existing host runtime changed: '+name)
PY
export PATH="$ROOT/.venv/bin:$PATH"
cmake -S "$ROOT/boot/granite-guest/quantizer" -B "$ROOT/build/qwen-quantizer" -G Ninja \
  -DLLAMA_SOURCE="$ROOT/build-src/llama.cpp" -DEXISTING_RUNTIME="$ROOT/build/llama/bin"
cmake --build "$ROOT/build/qwen-quantizer" --target llama-quantize --parallel 1
