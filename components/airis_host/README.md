# Fresh original AIRIS scalar-learning qualification

Four fresh workers execute actual AIRIS-general at
`db19ad4e2cea33e6129c8bf03e85797da8cf7625`: increment, decrement, double-step,
and repeated increment. Each learns two rules from four synthetic scalar
transitions, updates both rules, predicts a held-out scalar, then passes empty
knowledge ablation and original snapshot restoration. Repeated increment checks
fresh-process reset. All four passed in **1.446679 seconds** on the rebuilt
Python3.12.14 host. No Python oracle substitutes native outputs.

The complete upstream `airis.py`, README, Apache-2.0 LICENSE and NOTICE are
preserved. Preparation checks all four against exact byte count, SHA-256 and
Git blob identities. The contract, experiment and worker are byte-identical to
`components/airis/source`; paths, local runtime observation, launcher and host
qualification are new. The original bounded experiment prescribes a one-item
replay plan and forbids `make_plan`; step/hold are inert fixture labels.

Run as one command:

```sh
python -B components/airis_host/qualify.py \
  --base-manifest LOCAL-NARS-CLOSURE.json \
  --python /absolute/local/python3.12 \
  --output NEW-EVIDENCE-DIRECTORY
```

The base inventory contributes local Python files, maps and membership checks;
AIRIS does not run in Hyperon. Trusted runtime paths must be rebuilt and qualified
on each consumer machine. Each worker uses Python isolated/no-site mode; exact
prefix, import path, imported file hashes and native executable mappings are
checked against the fresh inventory. Recorded bytes, membership and symlinks
are checked before/after. Linux parent-death binding, child-only seccomp network
denial and a real denied-socket negative control are retained.

Resource caps: CPU10 seconds, wall15 seconds, address space512MiB,
file size256KiB, descriptors64, nproc1, no core dumps. Original trace/state bounds
remain 200,000 upstream line events,24 graph nodes,128 knowledge keys and one
replay-plan item. Original log writes are restricted by the worker audit hook to
two owned log directories; the controller audits file count, size and hashes.
These controls are not a general hostile-code sandbox; graph bounds are checked
after operations. Imported-file evidence is measured host evidence, not portable
attestation or exhaustive dynamic-library-resolution proof.

Five test methods reject false learning, changed authority/provenance, runtime
substitutions, log symlinks, and verify receipt preservation on spawn failure.
They use explicitly synthetic packets. Actual native evidence is separate in
`proof/native-host-002-summary.json` and the private handoff. First host run001
also passed four cases; run002 follows the strengthened source-lock preparation
and explicit seccomp-library pin. Both attempts remain preserved.

No conversation integration, persistent learning, action dispatch, general causal
discovery/identifiability, full AIRIS, guest qualification or complete Predictive
and Causal Coding architecture is established by these bounded fixtures.
