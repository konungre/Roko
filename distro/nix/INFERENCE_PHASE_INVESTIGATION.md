# Guest inference timeout: phase evidence and bounded next run

The prior real-model guest trial is a completed failure, not an uncertain action:
its runner reaped QEMU after 504.74 seconds. Kernel/init serial records reached
read-only source/model mounts around guest kernel seconds 13.01/13.16, UID/GID1000
and `ROKO_NATIVE_STARTED`. The outer driver then reported its 480-second deadline.
No native model-load/context/decode phase was preserved. Repeating that whole run
with a longer deadline would not establish where it stalled.

Inspection of the retained guest source shows inner native supervision at 150
seconds and communicate timeout 165 seconds. Those did not surface as an observed
phase-specific timeout in the retained outer log. The log cannot establish whether
the delay was supervisor startup, dynamic loading, native model loading/repacking,
context creation, token decoding, process cleanup or guest scheduling. No root-cause
claim is justified. The old guest source does not disable extra buffer/repacking;
the current conversation source and new probe do. This is a candidate difference
for a controlled comparison, not proof of the old binary's timeout cause.

## Current measured admission blocker

A fresh observation found ~17.99GB MemAvailable but only ~455MB remaining under the
visible 16GiB cgroup memory.max. Later actual controller admission observed
448,950,272 bytes remaining and refused before launching QEMU. This is a
**conservative policy rejection**, not evidence that all charged memory is
unreclaimable or that memory caused the historical timeout/disconnect. No caches,
limits, swap, other agents' processes or host settings were changed.

`memory_budget.py` reads both host and visible cgroup values and uses their minimum.
The service-manager fixture requires 512MiB guest plus 1GiB reserve; the older
10GiB conversation guest requires a 2GiB reserve. Both recheck immediately before
launch, and both monitor the visible headroom floor while running. No model
verification/cache warmup can silently bypass the second check. This observes a
racy shared budget, not a reservation or proof about hidden ancestor cgroups;
it does not assume reclaimable cache can be safely allocated. Missing/invalid
observations fail rather than changing limits. The existing runtime/image/disk
hash and child-reaping checks remain in place. No new model guest ran this turn.

## Native phase probe

`integration/inference_phase_probe.cpp` is a separate read-only diagnostic, not a
change to the conversation agent's runtime. It compiles against existing pinned
llama.cpp `f7591a6a01f9273de03331732bdc0b39721168be` headers/libraries. It emits
flushed stderr JSON with monotonic elapsed milliseconds, peak RSS and UID around
backend initialization, model load, tokenization, context creation, one forward
decode and cleanup. Modes are `vocab`, `load`, `decode-one`; vocabulary-only sets
vocab_only, all modes keep GPU layers zero and extra buffer/repacking disabled.
The last mode does one bounded prompt forward pass, not a conversation, sampled
reply or model-quality/health qualification. Stdout never grants action authority.

Build in an owned workspace with the trusted local runtime:

```
g++ -std=c++17 -O2 -I <llama-source>/include -I <llama-source>/ggml/include distro/integration/inference_phase_probe.cpp -L <portable>/lib -Wl,-rpath,<portable>/lib -l:libllama.so.0.9.0 -lggml -lggml-base -o <new-local-probe>
python3 distro/integration/qualify_inference_phase_probe.py <probe> <new-negative-controls-directory>
```

The actual native negative controls passed as UID1000 under 256MiB address space,
5 CPU seconds and 10 wall seconds: bad arguments exited2; missing model exited3.
Backend initialization completed in ~2.16ms in the missing-model host case,
followed by a measured model-load-begin and explicit load failure. This validates
flushed phase instrumentation only for these host negative paths, **not real model
load timing, TCG performance or the successful decode modes**. The binary hash and
native stderr are committed as receipts; native binaries/libraries are not vendored.

## Next appropriately provisioned trial

Use a disposable adapted guest with enough *observed* cgroup/host headroom, the
held read-only admitted model disk, explicit non-root user and no NIC. Preserve
all input hashes and distinguish it from the still-unbooted Nix/COSMIC image.
Instrument parent spawn-begin/return, first native phase receipt and teardown using
host and guest monotonic clocks separately; never compare those clocks as one.
Stream stdout/stderr continuously into bounded evidence so an outer timeout cannot
discard the useful native phases. The C++ entered timestamp excludes loader work
before main, so parent spawn-to-first-phase measurements are essential.

Begin with separately bounded vocabulary-only (30s) and load-only (60s) trials;
only after those succeed consider one-forward-decode (120s) with a budget sized
for the actual model/context. These are proposed diagnostic budgets, not measured
performance promises or unilaterally increased conversation deadlines. Use existing
supervision/subreaping with shorter inner limits than outer controller deadlines,
output/memory limits and explicit phase-at-timeout receipts; clean/reap descendants
before classifying failure. Never convert timeout into a canned reply or extend it
automatically. A completed phase-mode run still does not qualify full conversation.

All 125 OS tests pass, including cgroup-vs-host discrepancy, unlimited/malformed
budget cases and reserve protection. CLI compilation and actual no-launch rejection
were checked separately. The current blocker is insufficient headroom under the
new conservative admission policy; no real-model timing/inference conclusion was
manufactured. Legacy defaults, licensing/notice caveats, PR #22 draft status and
pending metadata approval remain unchanged. No host activation or metadata retry.
