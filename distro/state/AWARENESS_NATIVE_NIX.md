# Read-only native Nix profile to native Hyperon

The opt-in `package_profile_observation_v2.ReadOnlyProfile` supplies native Nix
profile observations to `SnapshotAwareness`. No default binding changes. The
controller supplies the trusted command prefix, environment and absolute profile
path. The qualifier uses Nix 2.26.3 with an offline workspace-local store and
Hyperon 0.2.10 in a separate venv. No profile installation/switch, build, rollback,
host activation or sandbox-setting change occurs.

`evidence/awareness-nix-001/result.json` records the actual native commands' JSON,
raw-output digest, profile path, resolved target, manifest digest and a revision
binding those fields. It also records the Nix executable and observer source
hashes. These hashes are provenance evidence, not runtime-closure admission,
signatures, monotonic native revisions or authority. Full receipts remain in
qualification evidence; the awareness checkpoint holds the snapshot and its
revision, not a transactional receipt archive.

Two fresh processes passed:

1. A retained, genuinely empty native workspace profile produced a native space
   containing state/version facts, and checkpoint version 1. A missing profile
   failed explicitly and preserved the current observation. A retained populated
   native workspace profile was observed but rejected before publication because
   its output paths are outside the existing canonical `/nix/store` contract.
   Actual paths were retained, never translated into invented installed paths.
2. A second process restored version 1 as `restored-historical-checkpoint` with
   zero backend calls, then re-observed the real profile and published version 2.
   Native revision stayed equal while the checkpoint version advanced. Identical
   content does not make an old publication decision current again.

Both profiles' links and manifest hashes were unchanged across the qualification.
The native store may perform its own bookkeeping during reads; no guarantee of
zero filesystem writes anywhere in the local store is asserted.

The observer requires an existing resolvable profile symlink, native manifest
schema 3, unique JSON keys, explicit boolean activity and one output per active
package. Missing profiles, malformed output, nonzero native exits and detected
profile drift fail without synthesizing an empty snapshot. Four dependency-free
failure tests are fixtures, separate from the native qualification. The full
state suite passed 28 tests.

The before/after target/manifest sampling detects ordinary drift; it does not
lock the native profile owner or exclude ABA changes between samples. The
revision hashes observed content, not a durable Nix generation sequence. The
SQLite awareness publication CAS still protects its own cooperative publishers;
it cannot make an independently managed profile transactional. No observation
authorizes an action or establishes running-system health.

Reproduction requires the retained disposable profiles and local Nix runtime,
plus the independently provisioned Hyperon environment:

```
/path/to/hyperon-venv/bin/python distro/state/qualify_awareness_nix.py . /path/to/nix-fixture-base /new/private/proof-directory
```

**Remaining boundary:** successful ingestion of a populated canonical
`/nix/store` profile is not established here. The current nonempty alternate-store
paths are rejected deliberately. No live Omega owner subscription, guest boot,
COSMIC session, production deployment or malicious-owner isolation is qualified.
Legacy remains default. Prototype licensing and Hyperon bundled-library notices
remain unresolved. PR #22 remains draft; pending metadata approval is untouched.
