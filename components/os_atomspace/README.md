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
