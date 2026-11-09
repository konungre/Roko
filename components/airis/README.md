# Bounded AIRIS scalar transition learning

This portable directory contains the authored contract, actual-upstream experiment wrapper, trace/state bounds, worker/supervisor source and pure tests from the qualified AIRIS v3 slice. The pinned original `airis.py`, runtime binaries, full runtime manifests, raw logs and private receipts are intentionally external. Apache-2.0 LICENSE and NOTICE are retained under `upstream/`; `upstream-lock.json` supplies exact public source identities.

Upstream: [singnet/AIRIS-general](https://github.com/singnet/AIRIS-general), commit `db19ad4e2cea33e6129c8bf03e85797da8cf7625`.

## Actual prior host result

One separately reviewed and admitted v3 attempt passed four fresh workers in 3.041271743 seconds whole-command monotonic time. Each original AIRIS instance learned two relative-outcome rules from four synthetic scalar transitions, updated both rules, predicted step/hold at a held-out value, and passed empty-knowledge ablation plus original snapshot restoration. A repeated increment case checked fresh-state reset. This migration does not rerun that gate. See `NATIVE_RESULT.md`.

The actual code path calls original `Airis.__init__`, `pre_capture_input`, `predict`, `post_capture_input`, `create_rule`, `update_rule`, `get_knowledge` and `load_knowledge`. A single prescribed replay-plan entry bypasses exploratory planning; a source trace guard forbids `make_plan`. `step` and `hold` are recorded fixture labels, not external commands.

## Boundary and limitations

- Four immutable synthetic evidence records per worker; one bounded scalar meter field.
- Actual learned, empty-ablation and restored predictions are checked independently, never supplied as fallback native outputs.
- At most 200,000 upstream line events, 24 graph nodes, 128 knowledge keys and one replay-plan item. Graph limits are post-operation checks, not allocation limits.
- Original log writes are restricted to two owned temporary directories, bounded and audited. The native worker checks a real denied socket operation under inherited seccomp. No external actions, model, VM or persistent learning state are used.
- Recovered Python prefix, exact module search path, isolation flags and imported-file hashes are checked before and after original AIRIS code. The earlier v2 prefix-warning failure is preserved, not silently accepted.
- Historical process caps: 20 seconds per child, 512 MiB address space, 256 MiB sampled RSS, 4 GiB host memory/disk reserves and a 90-second cooperative whole-gate budget. Native scripts still require an exact reviewed closure and separate admission.

This is a tiny deterministic transition-learning fixture with recorded action-labelled controls. It does not establish general causal discovery, confounding resistance, intervention design, causal identifiability, full AIRIS, Omega orchestration, Predictive/Causal Coding, PRIMUS, guest integration or a hostile-code sandbox.

## Portable tests

From repository root:

`python3 -B -m unittest discover -s components/airis/source -p test_pure.py`

The suite has 84 tests: 83 pass locally; one check explicitly skips until the exact external upstream source is materialized. Source tests use clearly synthetic native-shaped data and never import original AIRIS or run a native worker. All 84 tests passed in the historical reviewed scratch candidate where the upstream source was available.
# Development cleanup update

The gateway now retains finalization failures and child receipts. This changed
source requires a new native admission; historical results remain historical.
See [cleanup successor](../../docs/COGNITIVE_CLEANUP_SUCCESSOR.md).
