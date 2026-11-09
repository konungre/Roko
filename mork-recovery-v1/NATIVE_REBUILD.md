# Native rebuild candidate — 2026-11-09

Subsequent integration: the actual bounded PeTTa/Omega/Granite host path now
passes durable restart/recall and inference-cancellation checks. See
`../components/conversation/DURABLE_MORK.md`. The following sections record the
initial standalone rebuild qualification and its unchanged limitations.

Actual native MORK now executes in this private workspace. Ten genuine bounded
query/integration probes pass through Rust MORK, the C FFI bridge and SWI-Prolog.
These include exact/wildcard/empty/absent queries, duplicate facts, maximum
arity/count, durable evidence reopen, and conversation history/index reopen.
No Python matching fallback or native test double is used in those ten probes.
The existing Python completeness checker independently validates every result.

This is a separately identified replacement build, not reproduction of the
historical binaries and not production admission. The default native adapter's
hash pins remain unchanged and its missing historical runtime still fails closed.
At this initial rebuild checkpoint, the live PeTTa/Omega conversational loop had
not yet been executed; the later integration is linked above.

## Exact host interface

```python
from rebuilt_mork import RebuiltMORKCandidate
from conversation_store import ConversationStore
from durable_memory import DurableMemory

runtime = RebuiltMORKCandidate(
    '/workspace/native-mork-build/proof/runtime-manifest.json',
    expected_manifest_sha256=
        'b480e3973455b2b6bedc903ec245b5cd0e7a8fd0e9b30a85a7a6329d54aef7d2')
history = ConversationStore(private_history_path, native_backend=runtime)
evidence = DurableMemory(private_evidence_path, native_backend=runtime)
```

Only a trusted host may select the backend, manifest and digest. Do not accept
these from model output. Omitting `native_backend` retains historical behavior.
The backend exposes `query_facts(facts, query, timeout=3)` and reports
`implementation='native-mork-rebuild-bounded-facts'`, the manifest digest, and
`runtime_status='explicit-private-rebuild-candidate'`. It has no automatic
download, build, runtime selection, fallback or action dispatch.

Use the same `prepare_omega_request`, `append`, `prepare`, `accept_response`,
`snapshot` and `forget` interfaces described in CONVERSATION_INTEGRATION.md.
The host's main thread must own native supervision. Query execution uses the
unchanged hash-checked worker, network-denial helper, limits and cleanup code.
There are at most 16 native facts, 1–3 arguments, lowercase ASCII identifiers
of 1–16 bytes, 2048 request bytes, and a 1–5 second execution deadline. Raw
conversation text is never parsed as native code. The complete 32-message,
64-KiB transcript remains SQLite-owned; only its latest 16 turn-role entries
form the derived native index. There is no automatic semantic fact extraction,
general rule execution, persistent native graph, model inference, or authority
to execute a remembered instruction.

The runtime manifest inventories 568 installed SWI files and observed ELF
dependencies plus the entrypoints. The host Python environment is trusted.
Hashes detect changed listed bytes; this is not a hostile-filesystem sandbox,
an authenticated provenance service, a complete OS closure, or protection
against concurrent replacement between verification and execution. Use private,
host-owned runtime directories. The upstream parser/FFI remains unsafe native
code; bounded typed input and process limits do not repair every upstream bug.

## Build identity and compatibility decision

- MORK: `1c44f70f34db6305c3ba7bdb2e1434db3387778b` (unchanged source).
- mork_ffi: `f6553aa4559142895c5547f56e490d29e29469f1` (unchanged Rust/C source).
- PathMap: `5f2118c1d61d782a7590bac8874dcb3c94c1e0fb`.
- Git gxhash: `55bde471dc2e395dd17eb4e7055f323c0c29c19d`.
- tracking-allocator: `8d1e79b025011e5b8d445856eb51ab98ee915b6c`.
- SWI-Prolog official V9.3.34: `fc9a88533662f0505dc6fe626b33195c3488231c`,
  with the tag's pinned clib, plunit and sgml submodules.
- Official nightly-2026-11-01: rustc 1.101.0-nightly `f9ceb4a4d`,
  Cargo 1.101.0-nightly `31d3246e0`.
- Rebuilt libmork_ffi.so SHA-256:
  `54d446d2da1af22e9a3289b3e23c928130f33b17d8a6f5cafce6ffb0995c1362`.

The first PathMap selection, `70d3dd3d1194121e5cb9c3af968f3773c7a9bbf8`,
failed compilation with 18 API errors. Upstream commit `5866a4e` changed
`fork_read_zipper` to return `Option`; pinned MORK expects a direct zipper.
The selected revision is that change's parent. Consequently this candidate does
not include that commit's zipper bug fix or subsequent PathMap fixes. No claim
is made that arbitrary MORK workloads are safe or correct on this combination.
The ten bounded probes establish only the exercised adapter contract. The failed
build log and exact selection record remain in the private proof directory.

The FFI Cargo manifest has explicit local overrides for its two otherwise
unpinned Git dependencies. The new lock covers 129 dependencies (130 packages
including the root). It is not the lost historical lock. Registry versions and
checksums, Git pins, local override patch, compiler component hashes/sizes and
build flags are retained in the checkpoint. Build used `--locked --offline
--release -p mork_ffi`, one Cargo job, debug information disabled and
`RUSTFLAGS='-C target-cpu=native'`; this binary is host-CPU-specific.

SWI was built with CMake 3.31.6/Ninja 1.11.1, documentation disabled, and the
clib/plunit/sgml package set. Initial core-only tests failed because plunit was
absent; restoring the exact tagged submodules produced 50/50 upstream passes.
FFI upstream tests pass 2/2. Authored repository tests pass 69/69. The private
build directory occupies approximately 2.4 GiB, including retained toolchain
archives, extraction, sources, registry cache and build outputs.

## Evidence and reproduction scope

Private working build: `/workspace/native-mork-build`.
`proof/native-probe.json` records ten actual native calls and zero dispatched
external actions. `proof/build-receipt.json`, `source-pins.json`, `Cargo.lock`,
`toolchain-components.json`, `toolchain-sizes.json`, `ffi-build.patch`,
`dependency-licenses.json` and `runtime-manifest.json` preserve build identity.
The authored `inventory_rebuild.py` and `probe_rebuild.py` can inventory and
exercise a reviewed local build; neither builds or admits it automatically.

MORK/FFI and their internal crates have no declared redistribution license in
the inspected pinned sources. Their source and binaries are kept private and
excluded from the checkpoint. PathMap/gxhash declare MIT, tracking-allocator
MPL-2.0, and SWI carries its BSD license. No upstream source or native binary is
included in the source-only handoff. Full compiler logs remain local because
they contain upstream source excerpts; diagnostic summaries and hashes are saved.

The Library 401 operation was not retried or bypassed. The independent official
source rebuild was explicitly authorized. The separate conversation-hook archive
remains uninspected, so the parent must reconcile that hook and run actual
PeTTa/Omega/provider integration before claiming the complete loop. No push,
commit, installation into system directories, or historical-pin change occurred.
