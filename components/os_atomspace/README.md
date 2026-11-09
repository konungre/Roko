# Core OS state: provisional PeTTa/Omega ingestion and query

The OS package manager must be Nix/Guix-based and connected to AtomSpace. This
component implements the cognitive representation boundary while the OS owner
supplies the actual build/generation/health receipt schema. It does not substitute
a simulated package manager for the required native OS implementation.

`roko.os-state.claims.v0` is explicitly provisional. An envelope binds backend,
machine, boot, producer, snapshot sequence, facts and hash-checked evidence
bodies. Facts separately name **desired, resolved, built, activated, running,
observed and health** phases, subject and generation. Different activated and
running generations can coexist. Duplicate phase/subject facts and unbound or
changed evidence are rejected. Values are encoded as opaque hexadecimal data,
not evaluated as MeTTa expressions.

The fixed worker loads actual PeTTa and upstream Omega modules, ingests typed
claims, defines `rokoOSState`, and executes each phase query. Each process gets a
fresh space. Independent checks compare native rows to the exact input snapshot;
the result carries the snapshot digest. Desired facts cannot satisfy an activated
or running query. Empty query results do not prove package absence.

All claims currently remain `unverified`; hash binding establishes correspondence
to supplied bytes, not trustworthy origin or native OS truth. The bridge returns
`verified_native_os_state: false`, `mutation_authority: false` and zero actions.
AtomSpace represents state; it never authorizes a mutation. There is no privileged
grounded operation, build, install, activation or rollback command in this module.
Freshness, receipt authentication and native backend semantics must be connected
to the OS owner's versioned schema before promotion to verified observations.

Run `python -B -m unittest discover -s components/os_atomspace` for contract
checks. Run `qualify.py --symbolic-profile LOCAL_PROFILE --output NEW_DIRECTORY`
for actual PeTTa/Omega tests: desired-only phase isolation, all seven phases with
different activated/running generation labels, and an empty fresh space. The
fixtures are synthetic, including their evidence; no Nix/Guix is run. Runtime
and source files are hashed before and after, with child network denial and
bounded supervision. Local profiles require consumer-local requalification.

The prior package-manager prototype inspection, actual Hyperon bridge test and
proposed ownership split are documented in
`../../docs/PACKAGE_ATOMSPACE_INTERFACE_REVIEW.md`. Neither Nix nor Guix is
installed in this executor. Real declarative builds, selected and running
generations, rollback and crash recovery remain the OS integration blocker.

## OS-owner v1 build receipt reader

`os_fact_v1.py` reads the exact `roko-os-fact-v1` built-fact schema published by
the OS owner at `e428821335abda7c58b0caa165ea6922bc73e161`. It requires the
original Nix JSON receipt bytes to match `evidence_sha256`, checks the output's
generation basename and receipt shape, and preserves original fact bytes,
revision, predecessor and source commit inside the claim's evidence. It accepts
only built facts; that receipt cannot establish activated, running or health
state. The original source fact remains available in the returned value.

To ingest that source through actual PeTTa/Omega, add `--os-fact FILE
--os-receipt FILE --os-source-commit COMMIT` to the qualification command. The
native reader/import test uses the OS owner's actual offline Nix 2.26.3 build
receipt, rather than a simulated package-manager output. Nix execution itself
occurred on the OS owner's executor and is not rerun by this reader. It was a
tiny fixed-output workspace-store build, not a system generation or activation.
Receipt correspondence is verified; producer authentication, freshness, current
host truth and system status remain unverified. No executor capability is
constructed from the imported fact.

## Durable representation ledger

`ledger.py` stores content-bound built facts in a private owner-controlled SQLite
database. Ingestion requires the expected current revision, a consecutive source
revision, and a predecessor hash matching the prior source fact. Exact raw fact,
receipt and source-commit replay is idempotent; rebinding a revision conflicts.
`BEGIN IMMEDIATE` serializes competing writers. WAL and synchronous FULL preserve
commits. Each snapshot uses one read transaction and revalidates all stored
receipts, fact identities and predecessor links before publishing the latest
built claim. Old revisions remain immutable history; selected and running system
generations are not inferred from this ledger.

The qualifier's `--os-ledger FILE --os-machine MACHINE --os-backend nix` options
read a restarted ledger and ingest its snapshot into actual PeTTa/Omega. The
native test persists the OS owner's real build receipt, closes/reopens the
database, replays the exact record, and queries only its built phase. Unit tests
use explicitly synthetic receipts for competing-writer, predecessor and
corruption cases, including two concurrent SQLite connections and abrupt process
exit immediately after the actual ingestion API commits. The ledger still marks state unverified, does not authenticate
the producer or inspect the remote output's bytes, and supplies no activation
or rollback authority. Native OS generation lifecycle remains with the OS owner.
