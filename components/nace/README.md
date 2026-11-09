# Roko bounded NACE predictive adaptation candidate

Status: source-only. Seventy authored pure tests pass. No upstream NACE function, simulation, ONA process, planner, robot interface, or native worker has been executed for this candidate. There is no native success receipt. This is a real source integration candidate, not a claim that full NACE is integrated into Roko or its guest.

## Actual upstream code

Repository: https://github.com/patham9/NACE
Commit: `361fddf5f6885a60b6d5e0d179e0394da876df4c`.

`source/nace_slice.py` contains these exact, unmodified function blocks from that commit:

- `nace.py`: `NACE_Predict`, `_MatchHypotheses`, `_RuleApplicable`.
- `hypothesis.py`: `_AddEvidence`, `Hypothesis_TruthValue`, `Hypothesis_TruthExpectation`, `Hypothesis_Choice`.

The deterministic derivation script reads verified upstream bytes and parses their syntax. It does not import, compile, or execute upstream code. `proof/slice-lineage.json` records each block's original line range, byte count and SHA-256. `proof/upstream-lock.json` records nine read files with Git blob IDs, SHA-256 and exact-commit source URLs. Both original module copyright/MIT notices are retained verbatim in the generated slice. The repository LICENSE credits Patrick Hammer; these two modules credit Patrick Hammer and Peter Isaev.

The authored slice header provides `deepcopy` from Python's standard library and explicit `BOARD=0`, `VALUES=1`, `TIMES=2`, `width=height=3`. All other upstream top-level statements and imports are excluded. These bindings are a deliberately bounded compatibility boundary, not a modification of the seven functions.

## What the adapter does

`source/adapter.py` accepts a closed typed request, copies fixture state, and:

1. Applies at most eight explicitly provided positive/negative evidence updates through actual `_AddEvidence` when connected to the native backend.
2. Obtains the resulting frequency, confidence and expectation through actual upstream truth functions.
3. Groups conflicting rules by identical preconditions, then uses actual `Hypothesis_Choice` in request order to select one consequence per group.
4. Calls actual `NACE_Predict` once with an immutable-origin 3×3 world, a fixed inert operation string and `customGoal=None`.
5. Returns hypothetical state data, numeric truth data and provenance, with `authority=false`, `external_actions=0`, and `input_unchanged=true` only after checking input preservation.

The group/order composition in step 3 is authored. It is not a port or execution of upstream `Hypothesis_BestSelection`, whose unordered-set iteration and optional sampling are outside this slice. Repeated evidence can change which consequence is selected. The updates are fixture observations supplied explicitly by the controller; automatic observation, induction, corroboration and causal attribution are not claimed.

The worker statically imports the actual derived slice. It has no oracle or fallback import. The adapter's trusted backend is supplied by that fixed worker, not by model output or request data. Pure tests instead supply an expressly labeled authored `Fraction` reference, never the native slice. Such tests establish contract/oracle/source properties, not upstream runtime compatibility.

## Exact bounds and semantics

- World: exactly 3×3 cells, tokens from `. x f o k u`, two values (reward −1..1 and inventory 0..4), timestamps 0..1000 with none after the current time.
- Operations: inert `left`, `right`, `up`, `down`, `observe` strings. No function is called for an operation and no environment changes.
- Focus: at most four unique tokens, positive integer weights 1..100. Equal maximum weights preserve input order.
- Rules: zero to eight, ordered IDs `r0` through `r7`, one to four unique cardinal/self condition positions with offsets −2..2, and exact inventory context.
- Evidence: integer positive/negative counts totaling 1..21. Upstream uses `<= 20` before incrementing, so a total of 21 is intentional. At saturation, contrary evidence reduces the opposite count; it does not arbitrarily increase the new side. Truth is frequency `p/(p+n)`, confidence `(p+n)/(p+n+1)`, expectation `confidence*(frequency−0.5)+0.5`.
- `Hypothesis_Choice` ties select its second argument. For prediction matches, more conditions break a positive equal-score tie; otherwise the first matching rule stays selected. Only positions matching the global best score are updated.
- Prediction match score is the average matched-condition fraction among applied rules, or 1 when none apply. It is distinct from evidence truth confidence and is not a calibrated probability.
- Upstream returns negative infinity for a certain positive reward and positive infinity for a certain penalty. The adapter represents these as `certain_reward` / `certain_penalty` and a null match score. No non-finite JSON is emitted. In particular, an unchanged world already carrying reward ±1 can trigger this sentinel even when no rule applies, exactly as upstream specifies.
- The prediction's value tuple is overwritten in row-major cell order as upstream specifies; the last applied cell supplies final values. Observation timestamps are retained, not advanced.
- Native worker request/response cap: 16 KiB. Execution requires a separately reviewed manifest and a bounded controller; invoking the worker alone is not an approved runtime gate or a sandbox.

## Excluded paths and dependencies

Importing full `nace.py` imports `world.py`, which can prompt for a world and initialize simulation, Gymnasium/MiniGrid or ROS state. `main.py` drives simulation and has knowledge-loading evaluation. `bridge.py` changes directories, loads an ONA/MeTTa bridge, and builds/evaluates goal expressions. None of those modules is imported by the candidate.

The selected function closure needs only Python built-ins and `copy.deepcopy`. The authored contract/adapter/worker/reference additionally use standard-library dataclasses, hashlib, json, math, pathlib, sys, typing and fractions. No pip requirements, compiler, ONA, Hyperon, MeTTa, NumPy, GUI, Gymnasium, MiniGrid, ROS, network or model dependency is installed or used. Exact interpreter/standard-library/ELF closure and resource supervision are deferred to the native proposal, not implicitly trusted by this source checkpoint.

Not integrated or tested: full `NACE_Cycle`, `_Observe`, rule induction/rotation, partial-observation acquisition, stochastic hypothesis sampling, BFS planning, automatic action choice, `World_Move`, simulation, ONA/MeTTa/ROS integration, persistent learning, actual user actions, guest deployment, or the full NACE architecture. This does not establish PRIMUS, Predictive/Causal Coding, or TransWeave implementation.

## Pure tests

From this candidate's parent directory:

`python3 -B -m unittest discover -s nace-core-v1/source -p 'test_source.py' -v`

The 70 tests verify strict bounds/types, shape errors, evidence/tie conventions, fixed reference scenarios, input immutability, malformed backend responses, exact upstream blobs and derived function bytes, retained licensing, absence of unsafe imports/evaluation, and absence of a reference fallback in the worker. The tests assert that `nace_slice` is not in loaded modules. They do not execute `native_worker.py`.

Next gate: independent source review, exact fixed-case native proposal and resource/closure review, one explicit parent admission, then actual observed output comparison and immutable proof/readback. No invented, cached or pure-reference output may substitute for that gate.

## Portable development tree

This repository copy includes the authored sources, seven-function MIT-licensed derived slice with both original copyright notices, public source hashes, and the upstream MIT license. Full upstream review snapshots and private runtime data are excluded.

Run `python3 -B -m unittest discover -s components/nace/source -p test_source.py` from the repository root. There are 72 tests: 70 pass without external files, and two full-upstream provenance/regeneration checks skip explicitly until the pinned review files are materialized. Portable tests verify the exact generated slice hash and each retained function block hash against the preserved lineage. The original scratch source checkpoint passed all 70 original tests with those source files present, without importing or executing NACE.

This copy is development source, not native qualification. The fixed worker imports real upstream functions only when separately authorized through a reviewed native gate. Never substitute the authored Fraction reference for an actual native result.
