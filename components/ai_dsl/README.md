# Bounded native AI-DSL composition search

This component executes unchanged definitions from SingularityNET AI-DSL's
speech/emotion combinator experiment on actual Hyperon 0.2.10. The complete
upstream file, Apache-2.0 LICENSE, relicensing NOTICE and original README are
preserved at commit `1f7b1cacd4daa5915b79061075a10d150fe40a44`.
`upstream/source-lock.json` records exact bytes, SHA-256 and Git blob identities.
The worker loads the exact prefix before the upstream demo-test marker, then
executes a fixed query selected by a closed goal enum and depth 0..4. It does not
accept caller MeTTa code, a custom knowledge base, shell commands or endpoints.

The actual implemented capability is bounded type-composition search. **No
speech recognition, emotion recognition or other service is executed.** Accepted
pipelines are search results, not completed service calls; responses explicitly
report `executed_services: 0`, `executed_actions: 0` and `service_results: null`.
No conversation integration is claimed for this standalone gateway.

The optional `ai_dsl` cognitive task is integrated separately in
`components/conversation`: actual search results are staged as bounded advisory
context and exact `cognitive_results`, committed with durable history and replayed
without recomputation. See `../conversation/AI_DSL_V2.md` for the qualified path.

## Why the independent capability check is needed

The upstream depth-four speech/emotion query returns two type-correct proofs.
One calls speech-to-text and then wraps the resulting String directly with
`text-emotions.MkOutput`, bypassing emotion recognition. The other also calls
`text-emotions.MkInput` and `text-emotions.recognize`. The independent Python
checker verifies every service signature, composition edge and proof depth,
then rejects the first proof for its missing required service. The rejected
proof remains in the evidence. Type correctness alone is not sufficient to
establish the requested capability, and even an accepted composition does not
establish that any external service works or has run.

## Reproduction and limits

Run `python -B -m unittest discover -s components/ai_dsl` for independent checker
tests. Run `python -B components/ai_dsl/qualify.py --guard-manifest LOCAL_MANIFEST
--output NEW_DIRECTORY` for six actual native cases, including insufficient
depth, shortcut rejection and a fresh-process repeat.

The trusted local manifest inventories the rebuilt Hyperon environment; it is
reused from the NARS runtime only as a closure guard. No NARS inference is
claimed. Sources and runtime bytes are pinned before execution and checked
afterward. Each search has a fresh worker, inherited network-denial filter,
5-second CPU limit, 512-MiB address-space limit and 12-second supervisor deadline.
The existing Linux subreaper binds worker lifetime to the caller and cleans
descendants. Independent finalization records raw bytes and failures without
replacing primary cancellation. A failed receipt write retains attached memory
evidence but cannot guarantee a disk receipt. These controls are not a general
hostile-code sandbox, and local profiles are not portable admissions.

This is a small unary-composition subset. It does not establish general
AI-DSL completeness, MOSES, PRIMUS, service reliability, tool authorization,
learning, persistent state or guest qualification.
