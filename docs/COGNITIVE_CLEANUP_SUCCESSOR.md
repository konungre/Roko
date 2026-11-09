# Cognitive gateway cleanup successor

The MetaMo and AIRIS gateways now attempt child cleanup, process-group
observation, selector closure, every stream closure, and restoration of every
saved signal handler independently. Finalization exceptions are retained in
`receipt.finalization_errors` as stage/error pairs. Raw captured stdout/stderr,
return code, and owned-child cleanup evidence survive these failures.

An execution failure is also retained in `execution_error`. Cancellation keeps
its exception identity and receives the receipt before propagation. A deferred
signal is replayed after handler-restoration attempts. No finalization failure
can produce a passed receipt. Both MetaMo consumers reject nonempty finalization
errors even if a malformed producer labels the receipt passed.

## Preservation and qualification

`checkpoint/cognitive-before-cleanup` at `88072b8` preserves the pre-change
sources. Git history, upstream attribution, frozen NACE source, and historical
native result documents remain intact. Changes are in the development gateway
files; they are **not covered by the historical native qualification**.

Do not reuse the old native admission. Freeze a successor dependency closure,
review its exact source/runtime hashes and resource limits, obtain its admission,
and run a bounded native test. The conversation hook's historical manifest pin
has deliberately not been replaced with an invented or unreviewed digest.

## Fresh tests

Each gateway has nine new process-double fault-injection tests. They exercise
multiple simultaneous close failures, child-cleanup failure, failed signal
installation/restoration, deferred cancellation, missing child, and the complete
`run_native` receipt path with captured output and cancellation. No native worker
or model is launched. Real process-group cleanup remains covered only by its
existing qualification, not by these doubles.

After this change: MetaMo core 78 pass / 4 upstream skips; AIRIS 92 pass /
1 upstream skip; conversation hook 38 pass; controller adapter 54 pass.
The unchanged NACE suite previously passed 70 with 2 upstream skips.

## Conversation integration readiness

The existing canonical API remains `prepare_conversation(snapshot, candidates,
motivation)` followed by `score_conversation(plan, run=...,
current_snapshot_sha256=..., binding=...)`. Candidate text and the full snapshot
remain hash-bound; ranking remains unverified advice without action authority.
The consumer now explicitly rejects finalization failures.

The conversation owner still needs to supply the restored turn loop and verified
selection API. No substitute conversation loop or fabricated gateway observation
has been introduced. Once supplied, wire this hook at candidate selection and
test stale state, cancellation, receipt failure, and exact selected text through
that actual interface. Combined Omega execution remains unverified.
