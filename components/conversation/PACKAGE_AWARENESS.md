# Qualified package receipts in ordinary conversation

A trusted runtime profile can enable `package_awareness`. A normal durable v2
request then receives qualified imported package-receipt context without a
`cognitive_tasks` field. The public request shape stays ordinary:

```json
{"api_version":2,"op":"turn","session_id":"s","request_id":"r","expected_revision":0,"text":"Which source revision and machine does the package receipt mention?","context":[]}
```

The capability is disabled unless configured in a locally qualified profile.
`qualify_package_awareness.py --profile PROFILE --manifest OS_MANIFEST
--evidence-root NEW_ROOT --output NEW_PROFILE` adds the existing pinned OS-owner
manifest. That manifest contains source receipt files, source commit, runtime
selectors and closure pins; these cannot be supplied by a conversation request.
The fresh endpoint requires v2 for this capability. Disabled profiles retain
their existing response schema and do not import the package controller through
the legacy prompt path.

## Context, caching and provenance

The first claimed turn runs the existing actual PeTTa/Omega query over the pinned
OS-owner private-profile receipt. Later turns can reuse that immutable query,
while rechecking source bytes and the saved query receipt on every stage. A cache
hit is reuse of a qualified imported observation, not a fresh Nix observation.
Each stage binds session, request and revision and retains a private receipt.
Source drift, changed cached evidence or invalid query authority fails before
model inference. Native Nix is never executed by this capability.

The model gets one bounded package-context slot with the source machine/revision
and limits. It is separate from the cognitive ledger and the authoritative
transcript, so repeated ordinary turns do not append duplicate package facts.
The response's `package_state` contains the exact source result, context and query
receipt hashes, cache-use flag and durable binding. It commits atomically with
the generated response and full transcript. A source-stage receipt marked passed
does not mean the model turn committed; a later context or model failure can
still fail the request.

Producer authentication, current-host state, system activation, running-system
and health are not established by this imported source. Mutation authority and
executed actions remain false/zero. The source is an externally measured Nix
private-profile operation, not an installed-package inventory or live state
subscription for the current computer. Model prose remains advisory.

## Existing context policy remains explicit

Enabling receipt context does not enable history projection. `complete` remains
the default and can fail with `context_limit`; required package context is never
silently dropped to make room. Only a per-turn `context_policy: extractive_v1`,
with a separately qualified tokenizer/projection capability, selects the existing
extractive policy. Its system context includes the same package receipt. Exact
native token counts and the effective prompt digest cover that context, and
the response records omissions and source-history spans. The authoritative
transcript and cognitive ledger remain unchanged by projection.

Saved replay returns the original package metadata and model-context receipt
without awareness staging, native query, tokenizer, Motto or model execution.
It does not retrofit new package metadata into older saved responses. A new
source snapshot requires trusted qualification and a new request. Main's MORK
capacity and source remain intact; this milestone does not separately qualify
native MORK execution with package awareness.

## Native probe

`tests/probe_package_awareness_native.py --profile PROFILE --output NEW_DIRECTORY`
runs ordinary turns with no cognitive tasks, source recall, default overflow,
explicit projection, policy conflict, exact replay and restart. It independently
reconstructs the projected prompt with package context and compares its digest
with the actual native model receipt. Its user background text is a fixture;
the imported Nix receipts came from the OS owner's measured profile operations.
Local Nix execution, system activation and authenticated current-host state are
outside this qualification.

## Optional receipt-status explanations (explain_v1)

Strict receipt admission remains the default. A separately qualified profile may
select `--receipt-policy explain_v1 --max-admission-age-seconds SECONDS` with
`qualify_package_awareness.py`. This admits explanations when receipt *data* is
unavailable, changed, invalid, or outside the explicit local admission window.
Executable controls, runtime closure, and any cached query proof remain mandatory;
their integrity failures stop the request. Data paths cannot alias controls or
remove a source already mandatory in the base capability.

| Status | Meaning |
| --- | --- |
| `available_freshness_unknown` | Exact qualified bytes are available and local admission is valid at the recorded check. Observation age is unknown. |
| `source_missing`, `source_inaccessible`, `source_unreadable` | Receipt data cannot currently be obtained; this says nothing about package absence. |
| `source_changed`, `source_invalid` | Data cannot be admitted as the qualified supported receipt. |
| `admission_expired` | The configured local admission window elapsed; this does not establish the source observation age. |
| `admission_clock_unverifiable` | The local check predates qualification; no source is admitted. |

`package_state.evidence_checked_at_ns` makes the status an as-of check, not a live
subscription. The source v1 format has no observation timestamp; file mtime,
qualification time, and cache age cannot supply one. When data is not admitted,
`source` and `query_receipt_sha256` are null. A previously queried record may be
retained only as `last_known_source` with `last_known_query_receipt_sha256`;
it is historical and is excluded from the current source context. Full transcript
history remains authoritative and ordinary context policy is unchanged. Saved
replay returns its original historical status without rechecking availability.
No status grants mutation authority or establishes current-host, running-system,
system activation, health, or authenticated producer state.

`tests/probe_package_status_native.py` exercises missing/restored/missing receipt
data, expired admission, full history, and exact restart replay with actual
PeTTa/Omega, Motto and Granite. It mutates only a marked disposable copy of the
imported OS-owner receipts. The expired timestamp is a test fixture; no local
Nix operation or real old observation is inferred from it. Model prose is advisory;
these bounded examples do not establish general language grounding.
