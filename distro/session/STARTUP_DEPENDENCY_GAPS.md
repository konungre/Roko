# Static startup review and remaining qualification gaps

Current task complete; development is paused after this checkpoint per the user's
instruction relayed by the parent. No next evaluation or VM trial is scheduled.

The low-resource audit found selected source markers for ten dependencies in the
expected pinned nixpkgs tree. It records file hashes, line locations and required
runtime proofs under `../integration/evidence/startup-static-audit-001/result.json`.
It did not rehash the complete source NAR, evaluate the full configuration, realize
packages, start a manager or activate the host. Every dependency remains marked
runtime_verified=false for the **current declarative Nix/COSMIC candidate**. Prior
minimal/adapted guest proofs remain valid within their own narrower scopes.

## Critical startup and daily-driver gaps

| Dependency | Source-level finding | Critical untested path |
| --- | --- | --- |
| Provisioned account and PAM | greetd includes login PAM; shadow's login declaration requests session registration | The default evaluation account remains locked. Qualify a deliberately provisioned disposable login, wrong-password rejection, no autologin/root fallback and accessible recovery before claiming an usable image. |
| PAM/systemd/logind | PAM can load pam_systemd; logind supplies user@ and user-runtime-dir templates | Actual user-manager startup, owned XDG_RUNTIME_DIR, active seat, logout/restart cleanup and device ACL delivery. Do not restart host logind to test this. |
| Local D-Bus and accounts/greeter | The base systemd module independently declares D-Bus; COSMIC greeter/accounts add bus services | Generated system and user bus units, greeter bus-name activation, real session bus ownership and correct environment delivery. Turning off Avahi does not remove that independent source declaration, but runtime service health is still unproved. |
| Intel graphics and input | The candidate enables hardware graphics; COSMIC selects compositor/core packages and libinput | Realized kernel/firmware/Mesa/EGL/DRM closure, Intel iGPU display, seat access and keyboard/input on target hardware. Do not compensate for missing ACLs by adding broad device groups or root execution. |
| COSMIC/settings target | Inspected upstream session launches compositor/settings daemon before requesting its target | Actual frame/input responsiveness and environment propagation. Source launch order or target activation is not measured readiness. |
| PipeWire/WirePlumber | The pinned PipeWire user service explicitly binds to D-Bus | Functional audio/capture and socket activation without WAN. Failure may degrade audio even if the desktop still draws; avoid adding it as a blanket AI/login readiness gate. |
| Portals | COSMIC selects portal implementations; portal module publishes bus packages | Actual bounded, user-mediated file/screen interfaces and failure recovery; socket metadata alone is not a functional or permission check. |
| User diagnostic confinement | Proposed private-network/system/home/cgroup directives exist | Whether the target user manager/kernel supports them, with failure journal visibility and no desktop dependency. Do not silently weaken settings if the diagnostic cannot start. |
| Local model and history | Asset availability passed only in an adapted guest; declarative policy still says model/history unqualified | Completed non-root inference, matched symbolic/runtime closure, cancellation, private durable history and native recall/restart. Do not infer health from a GGUF header or a policy fact. |
| Realized offline closure and recovery | Policies, minimal boot/fallback and selected source facts have separate evidence | Full pinned Nix image build/closure, actual offline boot, authentication, generation trial/fallback and hardware recovery remain future gates. |

Local IPC/authentication/audio is not the same as optional LAN discovery or
network geolocation. Offline policy leaves local services in place; managed mode
preserves upstream/user settings. Previous small module-merger checks support
that override behavior, not this complete startup chain. No network namespace
isolation or connected-user runtime guarantee is added by the static audit.

## Cached evidence reuse is deliberately narrow

`integration/verify_cached_startup.py` compares current bytes for the four source
fragments covered by the earlier COSMIC/network receipts. It also checks the
recorded pin document, expected session ordering/no-restart semantics, mode outcomes
and rejection of the forced offline conflict. Unexpected lifecycle or execution
hooks are rejected. Tests catch source/pin drift, altered receipt semantics and
unreviewed source paths before they can be treated as a match.

A successful match is **not replayed or authenticated native evidence**. It never
sets image_ready, runtime_dependencies_verified or execution_authorized true. It
explicitly lists unbound critical inputs: the full system/live definitions, common
startup/memory helpers, upstream module/package closure and actual kernel/session
state. Editing those inputs cannot be covered by the old fragment receipts. The
checker is not a signature verifier, general Nix parser, complete dependency graph
or authority source for AtomSpace or an executor.

## Completed checks and pause handoff

All **141 OS tests passed**, including three new cache-consistency regression
tests. The read-only source audit found all selected markers for ten dependencies.
Observed visible headroom was 219,975,680 bytes, still below the conservative full
evaluation/VM budgets. Full evaluation was not attempted; no VM, real desktop,
model, host service, cgroup adjustment or credential change occurred. No PR metadata
retry or merge occurred. Legacy defaults, unresolved licensing/notice constraints,
PR #22 draft status and metadata approval hold are unchanged.

Reproduction commands are provided for review, **not scheduled work during pause**:

```
python3 distro/integration/verify_cached_startup.py <repository> <cosmic-receipt.json> <network-receipt.json>
python3 distro/integration/audit_startup_dependencies.py <repository> <expected-pinned-nixpkgs-source> <new-private-output-directory>
```

Resume only after the user requests it. Review this checkpoint and the explicit
missing runtime proofs before choosing further work; do not force full evaluation
or repeat denied ISO/canonical-store/sandbox actions.
