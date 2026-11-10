# Boot-local policy diagnostics and ordering

Later actual adapted systemd guest trials are recorded in
`STARTUP_MANAGER_FIXTURE.md`. Statements below about unexecuted units describe
the original evaluation checkpoint, not the later adapted fixture. The full Nix
image still has not been booted.

The live image now declares `roko-startup-report.service`. Pinned Nix evaluation
passed headless/COSMIC × offline/managed cases, including generated unit text.
The service is wanted by multi-user.target, ordered after local-fs.target and
before multi-user.target and display-manager.service. It has no Wants/Requires
network targets, models, history storage or desktop services. Ordering does not
pull in display-manager on a headless image. It does not require network-online.
The offline configuration still disables network manager, DHCP and online waiters.
No generated service or guest was executed here; this is evaluation evidence.

The oneshot has a 15-second start limit, DynamicUser, a private 0750 runtime
directory, no capabilities, no privilege gain, strict system protection, protected
home, private temporary directory and network namespace, and only AF_UNIX socket
families. These are evaluated systemd declarations, not proven kernel confinement.
No current sandbox capabilities/settings were changed to test them. Python is
referenced from the pinned Nix package set, adding a real image-closure dependency;
its image realization remains unqualified.

The local program reads the immutable first-boot policy and current kernel boot
identity, then atomically publishes `/run/roko-startup/status.json` (0640) with
fsync and emits a concise journal record. It never probes networks, starts models,
changes packages or activates generations. Missing/invalid/oversized policy or
invalid boot identity produces a sanitized failed report and nonzero exit.
Publication failure raises rather than reporting success; systemd OnFailure
starts a separate journal diagnostic. The failure service uses only a pinned echo
executable and never auto-repairs/reboots/falls back to a privileged session.

Valid policy produces `unqualified`, **not ready**: policy flags are declarations,
not evidence of observed runtime health. Issues name missing model/history
qualification, unprovisioned credentials, unproven requested offline isolation and
unsafe automatic state changes when declared. Even optimistic policy flags never
set readiness/authority true. Live-root persistence remains unqualified. A policy
report is not an AtomSpace activation receipt, a service health monitor, a network
isolation test or an authenticated status statement.

Login is not a Requires-dependent of this diagnostic service: a failed oneshot
can delay the targets until failure/timeout, but cannot deliberately lock an
otherwise provisioned local login behind a model/network/history check. The
existing locked/unprovisioned administrator policy still requires explicit fixture
provisioning before an accessible-image claim. The runtime directory is preserved
across unit restarts so a failed write can leave a prior complete report. Consumers
must compare boot_id with the current kernel boot and inspect the current unit
state; file presence alone is never health. `/run` is ephemeral across boot, and
these reports do not claim durable history. DynamicUser-owned data is diagnostic,
not an authority boundary against the service account or administrator.

Six local program tests cover unavailable components, optimistic false readiness,
invalid/duplicate policy with sanitized errors, missing policy/invalid boot ID,
invalid fields and failed-publication preservation. The complete OS suite passes
115 tests. Four pinned native Nix evaluations confirm ordering/hardening/policy
values and generated service text. See
`../integration/evidence/startup-ordering-001/result.json` and `os-tests.log`.
These are program/evaluation tests, not a systemd boot, COSMIC session, realized
image closure or production readiness result. Future disposable VM qualification
must inject invalid policy/unavailable storage, inspect both unit states/journal,
check current-boot report identity and bounded target progress, and verify offline
startup without DNS/cache/model-download dependencies.

PR #22 remains draft, licensing/notice caveats unresolved, metadata approval on
hold. The new module applies only to the opt-in declarative live image and does
not change legacy package-planner bindings or activate this host.
