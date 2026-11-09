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
