# Populated canonical store prerequisite

The read-only check in `evidence/canonical-profile-prerequisite-001/availability.json`
found no `/nix`, `/nix/store`, system profile directory or agent `.nix-profile`.
This checks explicit locations, not all filesystem paths. Existing authorized
workspace native profiles were already qualified in `AWARENESS_NATIVE_NIX.md`:
empty observations succeed; populated observations expose alternate workspace
store paths and are rejected without rewriting them.

The missing prerequisite is a **disposable Nix store and populated profile whose
realized outputs genuinely use canonical `/nix/store` paths**, accessible to the
native Nix executable in that store context. A provisioned disposable VM or
builder with its own canonical store would satisfy this without host activation.
A bare fabricated manifest or rewriting the current workspace output strings
would not satisfy it. No host directories, global store, mounts or security
settings were changed to manufacture that prerequisite. Strict namespace sandbox
qualification remains unavailable; no retry or weaker system configuration was
attempted. Alternative rooted-store provisioning has not been qualified here.

On that future builder, record the executable/runtime closure identity, profile
symlink and manifest hashes, actual `nix profile list --json` output, and verify
all referenced outputs with native `path-info` in the same store context before
claiming realized package ingestion. Observe a separately managed disposable
profile, preserve it, restore the snapshot in a fresh process as historical with
zero backend calls, then explicitly re-observe. Test removal and failures against
disposable generations. Retain the point-in-time/ABA limitation documented for
the read-only observer; an observation must never authorize activation.

In this executor, one new dependency-free fixture test exercises the combined
`ReadOnlyProfile` -> `SnapshotAwareness` -> SQLite checkpoint path with populated
canonical-shaped strings. It checks the full package snapshot and atom payload,
inactive-element exclusion, restart token separation, zero-read historical
restore, subsequent package removal and durable version advancement. A malformed
multi-output observation then leaves both the current view and checkpoint version
unchanged. Both the Nix response and atom sink in this test are **fixtures**;
none of the canonical-shaped output strings is asserted to exist. The complete
state suite passes 29 tests, and no additional native coverage is claimed.

Legacy defaults, draft PR #22, unresolved prototype licensing, separate Hyperon
notice limitations and pending PR metadata approval remain unchanged.
