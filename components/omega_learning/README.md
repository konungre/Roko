# MetaMo hook for the actual Omega conversation turn

This is authored integration source for the canonical `live-system/omega-chat` turn boundary. It replaces the fixed-task assumptions of the earlier WorkingState proposal adapter for freeform candidate ranking. The actual Omega loop owner supplies the complete immutable conversation snapshot, candidates, explicit motivational features, the fixed native gateway and a current-snapshot digest callback.

**Status:** 36 pure tests pass. The actual MetaMo scorer and earlier controller adapter passed their separate native gates, but this new freeform hook has not yet been wired into or executed by a combined native Omega conversation turn. Pure mock observations do not establish that integration. No new native run is authorized by these files.

## Exact caller interface

`prepare_conversation(snapshot, candidates, motivation)` creates an immutable plan.

The canonical snapshot contains exactly:

- `version: 1`, `session_id`, `revision`, `request_id`.
- `messages`: ordered records with `turn_id`, `role`, `content`.
- `user_text`: the current user message, separate from prior history.
- `evidence`: records with `id`, `text`, `provenance`.
- `components`: existing controller-owned component observations.

Every byte of the canonical snapshot is retained and bound into the native request identity. Snapshot size is at most 128 KiB, with up to 64 history records and 64 evidence records. Over-cap inputs fail instead of being truncated. History, sources, component observations, candidate text and revision all affect the binding. Instruction-like text stays literal data and never enters MeTTa expressions.

Candidates have exactly `{id, text, features}`. Features contain `correlations` (eight bounded values), `risk`, `delta_goals` (eight bounded values), and optionally `provenance`: `controller_policy`, `unverified_model_estimate`, or `explicit_user`. Absent provenance is labeled an unverified estimate. No features are guessed. `motivation` uses the existing eight-goal/six-modulator MetaMo contract. One to eight candidate texts are accepted, each at most 8 KiB UTF-8, without truncation.

`score_conversation(plan, run=..., current_snapshot_sha256=..., binding=RuntimeBinding(workspace))` invokes the fixed trusted MetaMo gateway once. The caller's digest callback must compute SHA-256 of the current full canonical snapshot immediately before and after scoring. It is a trusted controller dependency, not model/request data.

The `run(kind, request)` callback returns the actual gateway response and observed receipt, or raises. There is no retry, numeric fallback, fabricated receipt or direct native process launch in the hook. The runtime binding references the already reviewed v4 scoring closure and exact helper-first imports. Changed closures need separate review and admission.

Output contains `snapshot_sha256`, `candidate_id`, exact `selected_text`, `score`, `verification: "unverified"`, `executed_actions: 0`, `authorizes_actions: false`, and component provenance. It never marks arbitrary prose correct, applies a motivational update, changes conversation state, removes evidence, closes a task or authorizes an external action. The actual Omega controller decides how to use this advisory result while retaining its original context.

Full executable/probe validation remains the fixed gateway's responsibility. Receipt checking is evidence linkage, not cryptographic attestation. Features may be unverified estimates, and a high ranking does not promote them or the candidate answer to fact.

## Scope and next integration step

The Omega loop owner must wire this hook into the real candidate-selection stage, keep all original conversation/evidence state, and include it in a separately reviewed end-to-end turn gate. Until that happens this remains a source-tested hook, not the user's requested completed conversational system.

AIRIS's tested scalar transition-learning experiment is preserved separately. This hook does not invent semantic rewards or claim that synthetic AIRIS transitions already implement conversational causal learning. Actual observed turn-state transitions and their authority/provenance boundary still need an explicit mapping before adding AIRIS to the loop. NACE, MOSES, AI-DSL and the requested architectures are not implemented by this hook.

## Tests and lineage

From repository root:

`python3 -B -m unittest discover -s components/omega_learning -p 'test_*.py'`

The copied score contract is byte-identical to the qualified MetaMo v4 contract (SHA-256 `a0028e70899cfd792f8c1706613082573eb61469d2b0a1e91ea04db88ccae3f6`). Hook receipt checks preserve its exact source/packet/cleanup/resource boundary. Tests use explicitly named synthetic observations and never execute a model, Omega, MetaMo or an external action.
