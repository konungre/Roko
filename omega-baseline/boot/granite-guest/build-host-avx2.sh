#!/bin/sh
# Host-only experiment. Never package this absolute-RPATH target into a guest.
set -eu
case "${1:-}" in --build-after-lane-grant) ;; *) echo 'Explicit --build-after-lane-grant required; nothing built'; exit 2;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
OUT="$ROOT/build/granite-host-avx2"
test ! -e "$OUT"
python3 - "$ROOT" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);lock=json.loads((root/'granite-runtime.lock.json').read_text())
if lock['commit']!='f7591a6a01f9273de03331732bdc0b39721168be':raise ValueError('Wrong host runtime source')
for name,digest in lock['files'].items():
 if name.startswith('build/llama/bin/') and hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
  raise ValueError('Pinned existing host runtime changed: '+name)
flags=set(next(x.split(':',1)[1] for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('flags')).split())
if not {'avx','avx2','fma','f16c','bmi2','sse4_2'}<=flags:raise ValueError('Host lacks required AVX2 runtime features')
PY
mkdir -m 700 "$OUT"
g++ -O2 -std=c++17 -march=x86-64 -mtune=generic \
  -I "$ROOT/build-src/llama.cpp/include" -I "$ROOT/build-src/llama.cpp/ggml/include" \
  "$ROOT/boot/granite-guest/granite-guest.cpp" -L "$ROOT/build/llama/bin" \
  -Wl,-rpath,"$ROOT/build/llama/bin" -lllama -lggml -lggml-base \
  -o "$OUT/omega-granite-host-avx2"
readelf -d "$OUT/omega-granite-host-avx2"
echo 'Built a HOST-ONLY candidate; actual measurement is a separate coordinated action.'
