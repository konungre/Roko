# MetaMo controller proposal adapter

This is a separate authored, read-only adapter connecting the bounded MetaMo
MAGUS scoring contract to Roko's existing `WorkingState` proposal contract.
It contains no native worker, provider, network, persistent store or action
dispatcher. It has not been wired into a guest or live endpoint.

## Data flow

1. The controller prepares an immutable plan from an open, unproposed original
   state, its revision, explicit motivational values, and one to eight proposed
   answers or invoice records. All offers reference exactly one existing source.
2. The adapter binds original evidence bytes, provenance, revision, offer order,
   proposal contents and numeric features into a deterministic request identity.
   Only generated proposal IDs and numerical features reach MAGUS. Source text,
   instructions and proposal argument strings never become MeTTa expressions.
3. A trusted controller calls the fixed reviewed MetaMo gateway. The adapter
   rechecks the original state and revision both before and after that call.
4. Receipt checks bind the response to the exact request, original native packet,
   imports, selected symbol, scores, proposed delta, runtime observation, measured
   input manifest and successful owned-child cleanup. A failure is propagated;
   there is no reference-score fallback and no automatic retry.
5. The output contains the selected inert proposal in the existing schema:
   name, arguments and evidence_ids. It includes selected evidence provenance,
   receipt/request/snapshot digests, and explicitly false action authority.
6. An optional preview invokes an existing deterministic arithmetic, exact-quote
   or invoice checker on a detached `WorkingState` clone. Even an accepted preview
   cannot save, close or alter the original state.

The controller supplies goal correlations, risk estimates and proposed changes.
The adapter does not claim to infer these features from evidence. The selected
goal delta is returned as advice; it is never applied to motivational state.

## Semantics and trust boundary

A high MAGUS score is neither factual verification nor permission. The tests
explicitly give a wrong answer the higher synthetic score and confirm that the
existing arithmetic checker rejects it. A correct answer can be verified in the
detached preview without closing the task or changing persistent state.

All original sources remain in the immutable plan. Selecting one proposal does
not remove low-ranked or contradictory evidence from the original controller.
Stale revisions, changed source bytes, tampered plans, unsupported proposal names
and mismatched native observations fail closed.

The `run` and `current` callbacks are trusted controller dependencies, never
fields supplied by a user or model. Receipt validation does not authenticate an
arbitrary dictionary or provide independent cryptographic attestation. Full ELF
hash checks and numeric helper-probe checks remain the exact fixed gateway's
responsibility. Pure tests use explicitly labeled in-memory synthetic receipt
fixtures and never present them as native execution evidence.

## Source bindings

- MetaMo scoring gateway: frozen `metamo-core-v4` manifest
  `f848eb8166947cb01b8fa4d2ef47b5d3f2a2ae7f7d510b86a4fcb2271e65d05b`.
- Upstream MetaMo: `iCog-Labs-Dev/MetaMo` commit
  `bf97e50a68aa5059457092dfbe70699b7dd1dbe2`, MIT.
- The copied proposal contract and existing controller implementation are
  byte-pinned in `proof/source-lineage.json`.
- Native host reserve remains 4 GiB, separate from the 512 MiB child address-space
  cap and 256 MiB observed RSS cap. This module changes no runtime policy.

## Verification and limits

53 pure tests pass. Coverage includes existing-controller schema compatibility,
detached verification, false high-score rejection, invoice checking, original
source preservation, stale state before/after runner invocation, receipt linkage,
failure propagation, numeric-only requests and authority-escalation rejection.

This implements evidence-bound proposal advice from a scoring subset. It does
not implement full MetaMo appraisal, damping, projection, consensus or a state
cycle. No native MetaMo process was run for this adapter checkpoint, and it is
not a guest, live endpoint, autonomy or whole-architecture integration proof.

Run the source-only checks with `python3 -B source/test_adapter.py`.

Public source allowlist: this README and `source/*.py`. Exclude private proof
files, runtime receipts and workspace-specific checkpoint metadata.

## Adapter revision 2

This preserved successor binds the corrected v4 helper-first import order and
requires16 helper/consumer probe entries. The v1 adapter targeted the v3 core
whose only native attempt failed, so v1 is not a working-runtime claim.

## Proposed real controller qualification

The frozen two-case gate invokes the already native-qualified v4 gateway for
new actual outputs. It checks a wrong higher-scored answer is rejected and a
correct higher-scored answer is accepted only in a detached preview. Both
original tasks and both evidence sets must remain open and unchanged. No
historical receipt or mock score is used by this gate. It requires separate
source review/admission and has not run in this source checkpoint.
