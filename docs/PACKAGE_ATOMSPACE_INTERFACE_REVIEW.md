# Core package-state interface: inspection and proposed owner boundary

The OS must be built around a Nix/Guix package manager connected to AtomSpace.
This is a core architecture requirement, not an optional conversational feature.
The cognitive side must distinguish intent, build resolution and observed state;
a generated plan or model assertion must never become evidence of installation.

## Verified baseline

The supplied omega-metta-pm 0.2.0 archive was materialized from Library
`libfile_c869fe94c7708191bdcbb007c7a1410f`, SHA-256
`c4fec119e9f37eb94a2dab4ff01131ec4bb2b49145e5e7378b64765bdd34096f`.
It has strict desired-data parsing, simulation and Nix named-profile adapters,
stale-plan checks, operation receipts and an optional actual Hyperon bridge.
That bridge queries explicit package atoms and publishes each observation into
a fresh dedicated space. It is not arbitrary MeTTa execution or a system manager.

Inspection and local tests: original suite 30 passed, one skipped. Actual
Hyperon 0.2.10 passed four checks for explicit desired-state queries, planning
without installation, fresh observation publication and preservation of the
old snapshot. These tests used the explicitly labeled SimulationBackend and
fictional store paths. Zero actual packages were installed. Neither `nix` nor
`guix` is installed in this executor; live compatibility is not established.
The prototype's default MeTTa factory tries normal configuration creation;
the probe supplied an explicit configuration-free runtime factory appropriate
to this read-only host. The original source was preserved unchanged.

The current distro foundation has native guest/persistence/update work, but no
Nix/Guix build or profile implementation was found in its source. Its release
bundles and slot controls do not establish declarative package generations.
The prototype manages a dedicated user profile, not NixOS system generations;
apply consists of multiple operations and is not an atomic system switch.

## Proposed common state contract for parent/OS-owner review

Every snapshot should bind machine/boot identity, backend and profile/system
scope, generation identity, observation time/sequence, producer identity and
content digests of supporting native receipts. Each phase remains separate:

| Phase | Meaning and required evidence |
| --- | --- |
| Desired | Explicit declarative intent and its author/revision; never proof of installation. |
| Resolved | Pinned Nix/Guix inputs and actual evaluation/derivation identity; mark unavailable outputs separately. |
| Built | Actual successful build receipts and verified output closure identity; not proof of activation. |
| Activated | Actual selected profile/system generation and store closure observed by the native backend. |
| Running | Actual booted system and running service/process identities, which may differ from the selected next-boot generation. |
| Observed | Timestamped native measurements and errors, including freshness and completeness, with immutable evidence links. |
| Health | Explicit native service/system checks and their scope, distinct from merely running. |

AtomSpace should hold these as provenance-bearing facts in replacement snapshot
spaces, retaining historical generation references separately. Unknown, stale
or failed observations cannot assert absence. A failed refresh retains the last
complete snapshot but must expose its age and refresh error. Queries must name
the phase; `Desired(package)` must never satisfy `Activated(package)`.

The OS owner should own pinned declarative builds, actual Nix/Guix execution,
generation selection, rollback and observed boot/service receipts. The cognitive
owner should own typed AtomSpace publication, grounded queries, provenance and
drift reasoning. A bounded broker should connect these interfaces; model text
must not become arbitrary privileged commands. Tie mutations to the exact
reviewed intent and observed generation, recheck drift before switching, preserve
the prior bootable generation, and record postconditions. User authorization
remains the governing action boundary; this document adds no new approval rule.

## Next implementation and native acceptance work

Coordinate the backend choice and exact receipt schema through the parent before
overlapping distro changes. Build an isolated native Nix/Guix fixture on an
appropriate executor; verify real declarative builds and closure availability,
generation change, rollback, drift and restart/crash recovery. Then publish the
actual receipts into Hyperon and query desired/resolved/built/activated/running state
independently. Test that fake, stale and partial receipts cannot promote state.
Finally connect the broker to actual Omega conversation with exact request and
generation identity, while keeping observation queries distinct from mutations.

The new provisional `components/os_atomspace` implementation executes actual
PeTTa/Omega ingestion and all seven phase queries with hash-bound synthetic
fixtures. Every fact remains explicitly unverified and has no mutation authority;
the OS owner's native receipt schema is still pending. This is an inspected
baseline and proposed interface, not a claim that those
build, switch, boot or conversation paths already exist. No host package-manager
installation, system-generation switch or OS mutation was performed here.
