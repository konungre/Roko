# Desktop/optional-AI lifecycle isolation fixture

Five lightweight process cases passed, alongside native systemd 257 static unit
verification. This tests actual owned heartbeat processes and a proposed literal
two-unit graph, **not** COSMIC, inference or live systemd lifecycle propagation.
No VM, host service, model endpoint, request/history replay or inactive production
model worker was started. The existing `roko-model.service` remains unchanged and
must not be enabled as a shortcut around the conversation-owner contract.

The contract in CONVERSATION_INTERFACE.md requires explicit parent ownership,
cancellation and no silent background restart/replay. Accordingly this fixture
uses Restart=no; it does not simulate an automatic AI retry loop. The desktop
unit has no dependency/order/failure edge on AI. The optional AI unit has After
and BindsTo on the desktop owner, with no PartOf restart propagation and no Install
section. These are fixture units under `fixtures/isolation`, not installed units.
Their ExecStart is a harmless `/usr/bin/true` placeholder used only by static
verification, not the sentinel program or an AI runtime.

The proposed graph follows the documented distinction between ordering and
lifecycle dependencies: [systemd 257 unit documentation](https://www.freedesktop.org/software/systemd/man/257/systemd.unit.html).
BindsTo plus After makes the fixture AI depend on its desktop owner remaining
active; the inverse dependency is absent. Explicit AI start could pull in that
owner because BindsTo implies Requires; this is **not** a qualified activation
policy for the real application. Actual user-session ownership, parent death,
seat/display scope and broker design require the component owners' integration.

`qualify_session_isolation.py` performs two separate checks:

1. A narrow policy checker rejects desktop dependencies on AI, unexpected unit
   sections/edges, automatic restart, incomplete group cleanup, owner detachment
   and enablement. Native `systemd-analyze --user verify`, with generators disabled
   and private HOME/XDG_RUNTIME_DIR/SYSTEMD_UNIT_PATH, accepts the two files. It
   verifies static files without starting a manager or activating any service.
   It does not prove behavior of drop-ins, aliases or the real session graph.
2. The fixture owner starts harmless Python sentinels, each in its own owned
   process group under 64MiB address-space/2 CPU-second/32-FD/no-core limits.
   Desktop heartbeats continue after two separately, explicitly launched AI
   crashes (exit17), with the same desktop PID. A heartbeat must be timestamped
   after each failure, so queued old output cannot pretend responsiveness.
   Explicit AI recovery uses a fresh PID. Desktop restart first cancels/reaps the
   old AI and desktop, starts a fresh desktop alone, and leaves AI stopped until
   another explicit new launch. These lifecycle transitions are implemented by
   the **fixture owner**, not executed from the systemd unit graph.

All six child processes were reaped. Each sentinel output is capped at 16KiB and
each expected event has a 2-second deadline; cleanup terminates then kills if
necessary. No unrelated process or process group is signalled. The roles do not
spawn descendants, open network sockets, persist state or execute requests. Thus
no-request-replay is a fixture condition, not evidence of real conversation replay
correctness. The owner closes all pipes after cleanup.

Full OS suite: **132 tests passed**. Source/unit/static-verifier hashes, stdout,
child outcomes and a passive current admission snapshot are preserved under
`../integration/evidence/session-isolation-001/`. Admission remains insufficient
for the VM policy; no VM launch was attempted. Native static verification and
program fixtures fit within small process limits and change no host configuration.

Reproduce only the lightweight fixture, with a fresh private output directory:

```
python3 distro/integration/qualify_session_isolation.py <new-output-directory>
```

Actual live-manager stop/restart propagation, COSMIC session disruption, real
endpoint cancellation/descendant cleanup, low-memory OOM interaction, persistent
history semantics and the full Nix image remain unqualified. Guest inference is
still unqualified. Preserve the inactive legacy worker and default bindings,
unresolved licensing/notice caveats, draft PR #22 and pending metadata approval.

## Explicit recovery choices and controlled failures

The follow-up `qualify_ai_recovery.py` passed five additional actual-process
scenarios with seven owned sentinel children, all reaped. No real AI service,
model, compositor, user request or VM was started. Desktop responsiveness is
checked by a fresh heartbeat after each failure, preserving the same desktop PID
until the deliberately requested fixture desktop restart.

- A startup crash (exit17) is followed by a fixture owner choice to keep AI stopped.
  It starts no replacement, and desktop heartbeats continue.
- A newly chosen restart launches a controlled heartbeat stall. The 2-second event
  deadline expires, owner cancellation exits that worker cleanly (exit0), and the
  desktop continues. This is a synthetic heartbeat protocol, not an inference
  timeout/health protocol for the actual endpoint.
- Reusing that consumed decision is rejected before any worker starts. A fresh
  fixture choice can start a worker that deliberately ignores SIGTERM. Cleanup
  waits one second, sends SIGKILL to that owned process group and reaps it (-9).
  Escalation does not signal the desktop or any unrelated process.
- Explicit recovery uses a new steady worker. After cancelling it and restarting
  the fixture desktop, the new desktop epoch invalidates a pending old choice;
  that stale choice starts nothing.
- A fresh choice under the new epoch recovers a new AI sentinel. No automatic
  restart, fallback request, saved request replay or background retry occurs.

`fixture_restart_choice.py` is deliberately a **fixture-only, single-owner choice
freshness helper**. It accepts only restart/keep-stopped, checks the in-process
revision and desktop epoch, consumes a choice before a locked callback, and never
revives a choice after launch failure. Regression tests reject replay, stale
revision/epoch, invalid action/type, and startup failure reuse; keep-stopped never
calls a launch callback. This is not authentication, durable cross-process CAS,
a user-consent UI, an IPC server, a package executor or proof that a model cannot
forge an approval. The fixture controller supplies choices to simulate explicit
owner decisions. It must not be exposed to an endpoint or AtomSpace as authority.

Per-worker 64MiB address-space/2 CPU-second/32-FD/no-core limits and bounded
heartbeat/output/cleanup deadlines are inherited from the earlier fixture. These
are process rlimits, not verified systemd MemoryMax/cgroup isolation. No actual
kernel memory pressure or OOM was injected. The inactive model worker and real
conversation-parent contract remain untouched. The real endpoint's lifecycle,
descendants, history and cancellation still require component-specific tests.

Full OS suite: **135 tests passed**. Final fixture receipts include source hashes,
exit outcomes, fresh desktop/AI identities and passive current admission status in
`../integration/evidence/ai-recovery-001/`. Admission remains insufficient and no
VM was launched. Native live-manager lifecycle behavior, guest inference and the
Nix/COSMIC image remain unqualified. No host service/activation or PR metadata
retry occurred; legacy defaults, licensing limitations and draft/approval holds
remain unchanged.

Reproduce the bounded fixture only:

```
python3 distro/integration/qualify_ai_recovery.py <new-private-output-directory>
```
