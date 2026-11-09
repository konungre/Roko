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
