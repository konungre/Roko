# Original MeTTa-NARS NAL-1 on Hyperon

This development adapter executes the two original MIT-licensed MeTTa modules
at `945e2f83711b143e3f6e2eb112cc40c4f531c6f2` using Hyperon 0.2.10. It does not
replace inference with the Python oracle. Native atom structures are decoded and
checked independently against the existing fixed-point Fraction contract.

Six fresh-process host cases passed: baseline, asymmetric truth, zero confidence,
zero frequency, upper confidence boundary, and baseline reset. The first closure
passed in 2.086 seconds. The package-import successor passed in 1.933 seconds.
Both attempts are preserved privately. The final parent-lifetime successor passed
the same six cases in 1.849 seconds; its manifest SHA-256 is
`281644bff711d21d0c011842abe522b7bd4949fbc4c645e593f3d0cbc3a296cf`.
See [current native summary](proof/native-host-003-summary.json).

## Boundary and provenance

`source/runtime.py:run_native(request, manifest=..., admission=...,
evidence_directory=...)` accepts the existing two-premise NAL-1 contract and
returns independently checked response data plus an observed process receipt.
Paths and manifest identity are trusted controller configuration, not request
fields. The worker creates native atoms from generated n0/n1/n2 symbols and
bounded numbers. User identifiers and provenance strings never enter MeTTa code.

The local manifest covers source trees, the dedicated venv, the base Python
standard-library tree excluding its unrelated site-packages, resolved executable
mappings from a bounded runtime probe, interpreter, launcher, and symlink targets.
Tree membership and hashes are checked before and after each successful call;
the observed executable map set must match the probe. This is a new local closure,
not the historical PeTTa/Janus admission. It is not a general filesystem/network
sandbox. Conversation workers inherit the existing network denial.

Each call uses a fresh process, 3-second CPU and 6-second wall limits, 512-MiB
address-space limit, 64-KiB per-file output limit, 64 descriptors, one-process
limit, and disabled core dumps. These are configured limits, not measured peak
memory. Failure never returns reference-oracle output as native output.
Output, errors, and receipts remain in exclusive per-call evidence directories.
Before importing Hyperon, the worker binds its lifetime to the synchronous
calling process with Linux parent-death SIGKILL and checks parent identity on
both sides of that binding. Four tests include a real harmless child whose
calling parent is killed; no native child remained live after that test.

Only deduction and exemplification over a distinct-symbol inheritance chain
are admitted. Output retains original premises and uncertain-derived-belief
status, with no action authority and no persistent semantic-state update.
No full NARS memory, attention, temporal inference, planning, autonomous learning,
or guest execution is established.

## Runtime acquisition

The observed wheel was
`hyperon-0.2.10-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`,
SHA-256 `12a0479df6afadda7562ffe10e7d63a6701aaec02f7177b91412bc05a09ed419`.
It was installed in a dedicated local venv. The runtime and private inventories
are excluded from this repository. Rebuild and freeze locally; do not copy paths
or reuse another machine's admission. Source `contract.py` is byte-identical to
the pre-existing `nars-inference-v3` contract.

`source/worker.py --probe` (under the same resource limits as execution) records
the local executable mappings without NARS inference. `source/qualify.py prepare`
then freezes the current closure; `source/qualify.py run` requires its exact
digest and preserves six observed receipts. Both are explicit qualification
commands, not automatically executed during normal source tests.

The conversation adapter consumes these results through the real restored Omega
session interface. Its combined-native qualification is recorded separately in
the conversation component; source wiring alone does not establish that result.
