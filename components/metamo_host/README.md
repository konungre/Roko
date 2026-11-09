# Fresh MetaMo host qualification

This separately named host experiment executes actual pinned upstream MAGUS
scoring and selection through the rebuilt PeTTa/SWI runtime. It does not reuse
the historical `metamo-core-v4` machine admission. Eight fresh processes passed
in 3.709495 seconds; all scores matched the independent Python test oracle,
all expected winners and deltas matched, and each process passed 16 numeric
helper observations. No fallback implementation supplies native results.

Upstream: iCog-Labs-Dev/MetaMo at
`bf97e50a68aa5059457092dfbe70699b7dd1dbe2` (MIT).
`upstream/` contains five exact modules and their LICENSE; the proof lock records
bytes and hashes. The bridge, request contract, fixtures, helper probes,
numeric compatibility definitions, oracle, and Prolog worker are byte-preserved
from this repository's `metamo-core-v4/source`. Only paths, executable-map
reporting, launcher and qualification controller are new. The numeric shim is
controller-owned compatibility code, not additional upstream behavior.

Run `python -B components/metamo_host/qualify.py --symbolic-profile LOCAL.json
--base-manifest LOCAL-NARS-CLOSURE.json --output NEW-EVIDENCE-DIRECTORY` as one
shell command. Profiles are trusted local configuration, never request fields.
The output directory must be new. The controller records a fresh manifest before
execution, retains stdout/stderr/receipt for each case, and stops on failure.
The dependency on the NARS inventory is file inventory reuse only: MAGUS executes
in SWI/PeTTa, not Hyperon. Both runtime inventories must be rebuilt locally.

Limits: CPU 5 seconds, wall 10 seconds, address space 512 MiB, file size128 KiB,
64 descriptors, nproc1, no core dumps. Linux parent-death binding and the existing
child-only network-denial launcher are used. These limits are not a general
sandbox or proof against arbitrary hostile descendant behavior. Only fixed
trusted modules and generated typed expressions execute.

Source, base-Python tree membership, recorded symlinks, and pinned bytes are
verified before/after each case. Every observed executable mapping must be
pinned. Symbolic inventory is a recorded file inventory, not exhaustive proof
of all possible dynamic dependency resolution. Neither this manifest nor its
paths is a portable runtime admission.

`proof/native-host-001-summary.json` is a safe synthetic summary. Private raw
receipts and local manifest are retained in the handoff. Three test methods
exercise independent score/selection/probe/import/map acceptance and inventory
mutation rejection. This is not full MetaMo, state evolution, action dispatch,
or conversation integration. No model chooses goals or candidate features.
