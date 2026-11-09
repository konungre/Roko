# Read-only awareness concurrency and restart fixtures

This opt-in code does not change legacy OmegaAwareness/default bindings. It uses
caller-owned read-only backend observations and dedicated runtime factories.
Hyperon is absent here; fixture spaces are NOT native Hyperon evidence, and prior
PeTTa checks do not replace that gate. No package or host state is mutated.

Within one SnapshotAwareness, refresh requests receive increasing local tickets.
Only the latest-started request may publish current. A slower old observation is
rejected even if it completes later. If a newer request fails, older in-flight
work still cannot publish automatically: current remains the last complete view,
and a caller must explicitly retry. Ticket order is not semantic ordering of the
backend's opaque revision tokens, source freshness or global health evidence.

Optional AwarenessStore uses a NEW caller-selected private0700 directory and
single-link0600 SQLite file, FULL synchronous commits and BEGIN IMMEDIATE CAS.
Version/backend/snapshot bytes are bound into the checkpoint digest. Cooperative
publishers compare durable integer versions; stale actors must explicitly restore
before another refresh. No existing legacy state file is adopted or migrated.
The digest detects consistency errors, not malicious owner edits with recomputed
hashes. Private-directory/cooperative-writer assumptions and SQLite/filesystem
power-loss guarantees remain limits; no physical power-loss proof is claimed.

Restore is explicit: it creates a fresh fixture/runtime view labeled
restored-historical-checkpoint, makes no backend observation, and receives a new
process epoch in its token. Only a successful subsequent refresh is labeled a new
backend-observation. A restored view is never promoted to live installed/running/
health state or execution permission. Other processes can update the checkpoint
while an old view is retained; there is no automatic subscription or globally
linearizable shared current pointer. Consumers must use the owner protocol and
revalidate versions before decisions. Every observation authorizes_actions=false.

Tests cover overlapping slow/new refresh, competing durable publishers, stale CAS,
explicit restore, corruption without auto-repair, reused-runtime rejection and
partial fresh-space insertion failure. Three NEW processes wrote version1,
restored it with zero backend calls, refreshed/removing a fact at version2, then
restored historical version2 with another process epoch. Read-only fixture parity
with legacy still passes. Twenty-four state tests pass; native Hyperon remains
unverified. Caller must guarantee independent fresh spaces; object identity checks
are not a general sandbox or proof about all native proxy/space aliases.

Keep PR22 draft, provenance/licensing unresolved, and metadata approval pending.
No mutating CLI, source deletion, host activation or metadata retry was introduced.
