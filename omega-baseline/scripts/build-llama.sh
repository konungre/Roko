#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$ROOT/.venv/bin:$PATH"
cmake -S "$ROOT/build-src/llama.cpp" -B "$ROOT/build/llama" -G Ninja \
 -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DGGML_CUDA=OFF \
 -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=ON
cmake --build "$ROOT/build/llama" --target llama-cli llama-server --parallel 2
