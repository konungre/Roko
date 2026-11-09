# Resource-aware boot diagnostics without model activation

The startup diagnostic now reads the shared, bounded memory observer used by the
VM controllers. The authoritative helper lives in `distro/nix/memory_budget.py`;
the integration import is a compatibility shim. The declarative image packages
both Python files together in a pinned Nix derivation so the runtime import does
not depend on the repository being installed. The fixture guest builder likewise
copies both files. This introduces another unrealized image closure component;
no build, VM or host service was started to test it here.

The report adds a timestamped `resources` object from MemAvailable and the visible
cgroup memory.max/current. The minimum observed headroom is compared to an
explicit 6144MiB model-headroom diagnostic threshold. It is a provisional resource
requirement, not measured peak model memory or a promise of inference success.
Input reads are bounded. No cache reclaim, allocations to simulate pressure,
cgroup writes, process killing, mounts or network calls occur.

Behavior for valid boot policy is graceful and advisory:

- Low headroom adds `optional-model-deferred-low-memory` and recommends `defer`.
  The diagnostic still completes successfully with overall `unqualified`; an
  optional model shortage must not become a diagnostic login dependency.
- Missing, malformed or oversized memory data reports `unknown` and recommends
  `defer`. It adds `memory-observation-unavailable` without logging input contents
  or silently reusing a previous optimistic resource report.
- A later explicit rerun with adequate observed headroom reports
  `resource-check-only-passed`. That clears the low-memory issue but does not
  qualify the model, declare system readiness or authorize any execution.

Every report remains bound to a boot identity; memory sampling has its own
monotonic timestamp. Samples can become stale immediately and are not reservations.
The observer sees only the mounted cgroup boundary, does not prove hidden ancestor
limits and deliberately does not count charged file cache as guaranteed reclaimable
capacity. Consumers must re-observe at the real action boundary under the owner
protocol; neither policy flags nor AtomSpace facts grant execution authority.
There is no automatic model start, retry, memory monitor daemon or activation API.

The proposed image unit also declares MemoryAccounting, MemoryHigh=64M,
MemoryMax=96M, OOMPolicy=stop and Restart=no. These bound the small diagnostic,
not an inference worker. If the diagnostic is actually OOM-killed, systemd failure
and its existing OnFailure message must take precedence over an old status file;
consumers check current unit state and current boot identity. No automatic restart
storm or repair is added. As before, the target Wants/ordering relationship does
not make a failed diagnostic a Requires gate for an otherwise provisioned login.
These new cgroup directives are source declarations, not tested OOM behavior.

The bounded fixture collector `integration/qualify_boot_resources.py` ran low,
invalid and recovery transitions through the actual diagnostic program using tiny
synthetic meminfo/cgroup files. All returned exit0, remained unqualified and did
not start a model. A passive current-memory sample with fixture policy/boot ID
reported low headroom; it is not a real boot report. Missing-file and policy/error
unit tests also passed. Full OS suite: **127 tests passed**. No VM was launched
while admission remained insufficient. Guest inference remains unqualified.

Nix 2.26.3 syntax parsing succeeded with the existing explicit workspace store.
An initial parser invocation unexpectedly attempted the default `/nix/store` and
failed on the read-only filesystem; it created no host store. Only the parser was
then directed to the already-authorized workspace store, not retried against the
host path. No full module evaluation/build or systemd execution was attempted
under current memory pressure. `qualify_startup_ordering.py` is extended to check
the new unit settings when an adequately provisioned builder evaluates it; those
new assertions have not yet passed natively. Earlier four-case evaluation and
systemd guest receipts describe their historical, uncapped diagnostic versions.

Evidence: `../integration/evidence/resource-boot-001/`. The newly packaged module,
cgroup limits, low-memory boot progress and OOM failure path still need evaluation
and real systemd VM qualification on an adequately provisioned builder. The full
Nix/COSMIC image remains unbooted. Legacy bindings/defaults, licensing/notice
limitations, PR #22 draft status and pending metadata approval remain unchanged.

## Fresh-process bounded package-layout fixture

A subsequent six-process qualification used an isolated copy of exactly the two
runtime Python files, with before/after source hashes and verified import paths.
No repository integration helper was available to mask a missing packaged module.
Each new process had a 96MiB address-space rlimit, 2 CPU seconds, 5 wall seconds,
32 descriptors, disabled core dumps and a 64KiB regular-file size limit. These are
host fixture process limits, **not** the systemd MemoryMax cgroup limit, and are
not evidence that a Nix derivation was realized. The measured maximum RSS across
the six host processes was 9,984KiB; another interpreter/guest may differ.

Low headroom, wrong units, duplicate MemAvailable values, one byte below the
threshold, exact threshold and a new boot with low memory all passed. Every step
replaced the report atomically, retained 0640 permissions with no temporary files,
and remained unqualified with authority/readiness false. Valid sample monotonic
timestamps advanced across fresh processes. The new boot identity replaced the
prior report's identity, so a prior boot's optimistic resource sample was not
silently retained. These boot identities and memory inputs are fixtures, not boots.

This exposed a genuine parser gap: earlier code accepted the first of multiple
MemAvailable fields and ignored its unit. The shared observer now requires one
ASCII decimal MemAvailable value explicitly in kB, ASCII decimal cgroup counters
(or exact `max`), and bounded input sizes. It opens inputs O_NOFOLLOW/O_NONBLOCK
and requires regular files before reading; malformed, symlink and FIFO inputs
cannot become an optimistic budget or block a read indefinitely. Boot diagnostics
turn these observation failures into unknown/defer; VM admission still fails
before launch. A FIFO regression test runs in a separate process with a timeout.

Full OS suite: **129 tests passed**. A passive current admission observation still
refused a 512MiB guest plus reserve, and **no VM was launched**. New systemd cgroup
limits, full Nix module evaluation/build, actual low-memory boot/oom progress and
guest inference remain unqualified. No host limits/settings, services or metadata
were changed. Legacy defaults and all draft/licensing/approval holds persist.

Reproduce the fixture only, with a fresh private output directory:

```
python3 distro/integration/qualify_boot_resource_processes.py <new-output-directory>
```

Receipts: `../integration/evidence/resource-boot-processes-001/`.
