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
