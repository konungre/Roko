#!/bin/sh
# Requires the pinned llama.cpp checkout and workspace-local CMake/Ninja.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$ROOT/.venv/bin:$PATH"
cmake -S "$ROOT/build-src/llama.cpp" -B "$ROOT/build/llama" -G Ninja \
 -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DGGML_CUDA=OFF \
 -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
cmake --build "$ROOT/build/llama" --target llama --parallel 2
mkdir -p "$ROOT/runtime/granite"
g++ -O2 -std=c++17 -I "$ROOT/build-src/llama.cpp/include" -I "$ROOT/build-src/llama.cpp/ggml/include" \
 "$ROOT/integration/granite-infer.cpp" -L "$ROOT/build/llama/bin" \
 -Wl,-rpath,"$ROOT/build/llama/bin" -lllama -lggml -lggml-base \
 -o "$ROOT/runtime/granite/omega-granite-infer"
