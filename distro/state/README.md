# Declarative OS state foundation

Nix/Guix-backed generations tied to AtomSpace are a core OS requirement.
The current Debian/minimal-guest tools are bootstrap qualification tools.
The preserved user-supplied prototype-v0.2 is a constrained data-only MeTTa
parser and Nix user-profile reconciler, not a system generation manager.
Its simulation is not live Nix; its export is not a live AtomSpace bridge.

Cognitive interface: keep desired, resolved, installed, running and observed
snapshots separate. Every snapshot needs machine/backend identity, revision,
predecessor and evidence digest. Desired is authorized intent. Resolved binds
source locks, platform, derivation and output closure. Installed requires backend
receipts. Running requires independent boot/service observations; builds and
installations cannot establish it. Replace snapshots by revision to avoid stale
facts. AtomSpace proposes changes; a bounded executor checks authorization,
expected revision and exact generation identity before activation.

The first implementation target is Nix system generations with an explicit
COSMIC module. Guix remains an alternative backend. Required lifecycle:
pinned resolution -> isolated build -> closure verification -> staged generation
-> bounded boot trial -> independently observed health -> confirmation.
Retain prior generations/closures as recovery roots. Separate user/model data
and schema migrations from immutable OS state. The prototype's multi-operation
profile apply is non-atomic and must not become the production activation path.

Neither Nix nor Guix is installed here. Live backend execution, full MeTTa
compatibility and AtomSpace ingestion remain unqualified. Next work requires
pinned official unprivileged Nix tooling, disposable offline build/generation
tests, cognitive-owner agreement on versioned facts, and a real declarative
COSMIC image. Existing boot/state fixtures remain acceptance tests.

## First live backend and AtomSpace check

Nix 2.26.3 from authenticated Debian download-only packages ran as UID1000 from
an extracted workspace runtime. A real fixed-output `builtin:fetchurl` derivation
read a local file offline into a direct workspace store. Output bytes matched
its declared SHA256. The first relocated-root attempt failed and is retained.
This is a tiny fixed-output build, not a NixOS build, system generation, profile
activation, sandbox/isolation qualification or boot test. Sandbox was disabled for
this disposable development store; no host installation or activation occurred.

`facts.py` defines v1 desired/resolved/built/activated/running/observed/health
facts with explicit generation and evidence/predecessor hashes. Its typed executor
requires a matching current revision and an external trusted review callback;
serialized facts supply no authority. Real handlers for system activation are
not installed. Three boundary tests pass.

The actual PeTTa runtime accepted a built fact derived from the Nix build receipt
and matched generation and provenance. Numeric-only hex digests required an `h`
symbol prefix to prevent parser coercion. Evidence under `evidence/nix-live-001`
contains exact local recipes/paths and diagnostics; it is a measured local test,
not a portable reproduction recipe. This is PeTTa's in-memory AtomSpace only:
no cognitive-owner durable ledger or host-state reconciliation is connected yet.
Next gates are complete source/closure provenance, live user-profile generations,
durable snapshot replacement/CAS, and a real NixOS COSMIC image with health trials.

## Live profile generations and durable snapshots

A second live test built two tiny directory outputs and installed them into an
explicit workspace profile. Native Nix history reports generations 1 (package1),
2 (empty after removal), and 3 (package2). The observed generation3 JSON was
persisted and read back after reopening the SQLite ledger. Four state boundary
and ledger tests pass, including stale CAS and simulation labeling.

`ledger.py` commits fact documents and their evidence mode atomically, binding
revision and predecessor digest. Simulation is retained separately in the body;
consumers must not project it as real activated/running state. The tested activation
fact is simulation only. No system activation handler has been installed.

The live Nix2.26.3 test rejected `profile install --name` and numeric removal
indices. Installation without --name and removal by the observed element name
succeeded. This invalidates the prototype's claimed live CLI compatibility for
this version; its backend must remain disabled pending a versioned adapter fix.
Receipts include the actual failures. Replacement here creates an empty intermediate
generation and is not a safe atomic production update path.

The directory builders use host /bin/sh and /bin/mkdir, with sandbox disabled.
They establish real profile/history behavior only, not hermetic builds or NixOS.
The fixed-output build from the previous test remains separately evidenced.
The local recipes include exact test paths; replay needs fresh isolated paths.

## Successor private profile switch

`profile_switch.py` prepares a complete native profile in a new private generation
directory, verifies its exact output set, then switches a single `active` symlink
with rename and parent fsync. Existing generations remain available. It uses the
observed Nix2.26 CLI without --name or index selectors. This supersedes the
preserved prototype's incompatible mutation path; it does not silently rewrite
that historical implementation. Empty desired profiles are currently rejected.
Only cooperative clients using this private root lock are supported.

Two real candidate profiles and pointer switches passed, with old profile retained
and stale target rejected. `projection.py` reads a durable ledger snapshot and
refuses simulation-mode export. The observed pointer receipt was committed,
reopened and projected into actual PeTTa, where exact fact matching passed.
This is a private profile observation, not running-system or health evidence.

The retained-profile rollback path requires external review and matching current
pointer, admits only generation directories within the private root, and compares
a fresh native profile observation with the saved receipt before switching.
A real rollback restored payload1 from payload2. Unreviewed rollback left the
pointer unchanged; a stale repeat was rejected. `rollback.json` retains the
actual native observation. This establishes private-profile rollback only; OS
boot rollback, health confirmation and user-data schema rollback remain separate.

## Integrated native receipt gate

`qualify_profile.py BASE SYMBOLIC NEW_OUTPUT` joins actual offline Nix build
commands, two prepared private-profile switches and a retained rollback with
durable versioned observations. Each canonical receipt digest is bound into a
fact; facts survive ledger close/reopen, then all three exact facts are inserted
and matched in real PeTTa with successful Omega utils/provider imports. Stale
profile rollback, unreviewed rollback and stale ledger insertion must all fail.
The final gate002 passed. The Nix outputs may be cached; this gate does not claim
fresh rebuilds. Inputs remain the previously measured local non-hermetic builders.
No model inference, autonomous Omega loop or system activation is performed.

Schema coordination: `roko-os-fact v1` uses machine/backend/revision, explicit
stage, generation, canonical receipt SHA256 and predecessor snapshot digest.
Digest symbols carry an h prefix to preserve numeric-only hashes in PeTTa.
These gate facts are OBSERVED operation receipts. They must not be promoted to
system BUILT/ACTIVATED/RUNNING/HEALTH. Durable ingestion into the cognitive owner's
long-lived AtomSpace remains to be wired through that owner's snapshot/CAS API;
this gate proves replay from the OS ledger into an actual in-memory AtomSpace.
