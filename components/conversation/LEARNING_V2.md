# Native MetaMo, AIRIS and NACE in durable v2 conversation

Optional `cognitive_tasks` now invokes actual component implementations inside a
v2 turn, before Omega/PeTTa dispatch to local Granite. This is executable integration,
not a model description of a plan. Inputs are explicit typed data supplied by the
caller; no component request, runtime path, action or training sample is invented
by the language model. See the API extension in `DURABLE_API.md` and complete
synthetic examples in `tests/learning_fixtures.json`.

| Component | Actual executed scope |
| --- | --- |
| MetaMo | Five pinned upstream modules; MAGUS proposal scores, selection and proposed goal delta. Independent oracle checks the actual scores and choice. |
| AIRIS | Original pinned Airis class; four recorded scalar transitions, rule creation/update, held-out prediction, empty-knowledge ablation and snapshot restoration. |
| NACE | The exact seven-function upstream-derived slice; bounded 3×3 board/rules, evidence revision and hypothetical prediction checked against an independent oracle. |
| AI-DSL (optional) | Actual upstream type-composition search on Hyperon, with independent type/depth/capability checks. No synthesized service is executed. See `AI_DSL_V2.md`. |

## Durable behavior

The optional list has at most three tasks, one per component, and a 10,000-byte cap.
Existing typed contracts bound all states, candidates, transitions and rules.
Pure validation happens before the durable claim. The complete task list enters
the request fingerprint; altered tasks cannot reuse an existing request ID.
Runtime failure after claiming marks that request failed without committing
history or observations. Successful component observations and structured native
`cognitive_results` commit with the generated response in the existing SQLite
transaction. Restart/replay returns the exact response without component or model
execution. A failed model call does not commit previously computed observations.

`cognitive_results` contains native results independent of model prose. The first
native integration attempt exposed a real quality error: Granite reversed AIRIS
step/hold values even though the input prompt and native result were correct.
That attempt and its failed quality audit remain preserved. The successor uses
explicit scalar labels and returns structured native results so a client need not
infer verified facts from generated text. Model prose remains unverified in
general; no general response-grounding guarantee is claimed.

## Local qualification

The successor native probe passed all 25 checks in 101.146904 seconds. It ran
three real component/model turns, restarted and replayed them without native
execution, then exercised a real AIRIS result followed by model context rejection.
Replies were `act2`, `step=8, hold=7`, and `NACE predicts a reward value of 1.`
Checks compare exact prompt hashes, claimed session/request/revision binding,
component receipts, structured results, history/observation commit and rollback.
See `LEARNING_NATIVE_002_SUMMARY.json`; raw evidence is in the private handoff.

A further single-turn combined probe passed all five checks in 65.595402
seconds: three real components, one real model call, three atomic observations,
exact structured results and zero-work replay. Its input was 456 tokens and
output 62 tokens (EOS). Independent post-audit also verified the exact combined
prompt hash and every component snapshot binding. See
`LEARNING_COMBINED_NATIVE_001_SUMMARY.json`.

The ordinary suite ran 121 tests: 119 passed and two external ECAN/MORK tests
skipped. Three repository-layout tests also passed. Native ECAN/MORK were not
requalified in this executor's learning profile. Their reviewed integration paths
remain intact, as do main's NARS parser, durable store, MORK adapter, v1 behavior
and v2 generation/truncation policy.

## Runtime preparation

First prepare a fresh local profile using `qualify_fresh.py`. Then run
`qualify_learning.py` with `--profile`, separately qualified `--metamo-manifest`,
`--airis-manifest`, `--nace-manifest`, a locally rebuilt `--guard-manifest`, an
absolute `--evidence-root`, and a new `--output` profile. The guard is the existing
NARS runtime inventory/verification mechanism; it contributes pinned Python files,
source-tree membership and symlink checks, not a substitute learning engine.
The profile includes each component's original manifest and file pins. Consumers
must rebuild/requalify their own runtime rather than copying these machine paths.

`learning_exec.py` runs one fixed component controller in a separate process to
isolate legacy module import names. It verifies the closure guard before/after;
the component gate independently verifies its own files and actual output. Existing
native child limits remain in force. The outer native supervisor has a 30-second
deadline, parent lifetime checks and descendant cleanup; its worker inherits the
conversation's network denial. MetaMo/AIRIS retain their own bounded launchers;
NACE retains its resource-limited seven-function worker. These are bounded trusted
workloads, not a general hostile-code sandbox. Binding records are written and
fsynced before native execution; raw component and outer receipts are retained.

No external actions, model-selected component calls, autonomous goal changes,
persistent AIRIS agent state, full NACE/AIRIS/MetaMo, guest execution, arbitrary
prose extraction or complete cognitive architecture is established. Only the
advisory observations and saved results persist. The existing model input budget
still applies to accumulated history and observations; it never silently drops
history to make a task fit.
