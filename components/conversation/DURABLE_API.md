# Durable conversation API v2

This is a separate opt-in endpoint. The earlier `55bebd8` three-field chat-bubble
checkpoint remains in its original checkout and keeps its original launch binding.
Do not change the basilisk client to v2 without adopting this request/response
contract. `fresh_server.py` continues to speak v1; `durable_server.py` speaks v2.

Set trusted environment variables `ROKO_FRESH_PROFILE` to this machine's newly
qualified profile and `ROKO_HISTORY_DB` to an absolute local SQLite path. The
request cannot select programs, model paths or database paths. Launch
`durable_server.py` with the profile's Python interpreter. Keep a 180-second
per-turn client budget plus initial verification. Native inference retains its
150-second deadline. Only one request is processed at a time in each worker.

## Requests and responses

One JSON object per line. `api_version` is integer 2. Unknown fields and duplicate
keys are rejected. Session and request IDs are bounded ASCII identifiers, not paths.

A turn:

```json
{"api_version":2,"op":"turn","session_id":"story","request_id":"turn-1","expected_revision":0,"text":"Suggest an opening sentence.","context":[],"max_output_tokens":128}
```

`max_output_tokens` is optional, defaults to 128, and must be 1..128. Context has
the original schema: at most 16 records with exactly `id`, `text`, `sti`, `lti`,
`stimulus`. Real ECAN selects at most four; `context_ids` identifies the selected
records. Source text never enters ECAN's executable program.

A completed turn returns the same JSON response value saved before delivery:

```json
{"api_version":2,"session_id":"story","request_id":"turn-1","status":"completed","text":"Unverified model text","context_ids":[],"executed_actions":0,"generation":{"input_tokens":80,"output_tokens":15,"finish_reason":"eos"},"history_policy":"complete_no_omission","revision":1}
```

The numbers and text above illustrate the schema, not a model-test receipt.
When the native output budget is exhausted, `status` is `truncated` and
`generation.finish_reason` is `length`. That explicitly partial reply is committed
and replayed unchanged. If the token limit cuts the final UTF-8 code point, its incomplete bytes render
as one U+FFFD replacement character; the private receipt preserves the original
bytes and the exact affected suffix. Interior malformed bytes and malformed EOS
output fail with `invalid_output_encoding`. This boundary decoding does not
change token counts or the three-field generation schema. There is no automatic
continuation, semantic repair or retry. A user
can explicitly ask to continue using a new request ID and the new revision.
The v1 endpoint cannot represent truncation metadata, so this newer implementation
rejects output-limit replies before committing them rather than silently presenting
partial text. The separately preserved old checkpoint retains its historical behavior.

Read durable state without a model turn:

```json
{"api_version":2,"op":"snapshot","session_id":"story"}
```

Response `status: snapshot` includes `revision`, full `history` and the pending
request ID or null. Model replies in history remain unverified text.

After cancelling and waiting for the old worker to die, explicitly abandon its
pending claim:

```json
{"api_version":2,"op":"recover","session_id":"story","request_id":"cancelled-turn","expected_revision":1}
```

Recovery marks that request `interrupted` without adding messages or incrementing
the revision. It never invokes the model. Recovery refuses a living or unverifiable
owner. The interrupted request ID stays terminal; a new user-authorized attempt
requires a new ID. A cancelled worker may leave a pending claim; this is intentional.

Errors return `api_version: 2`, `status: error`, `code`, `executed_actions: 0`, and
valid request/session IDs when available. Important codes are `stale_revision`,
`request_conflict`, `busy`, `pending`, `failed`, `interrupted`, `context_limit`,
`history_limit`, `invalid_request`, `invalid_output_encoding`, `native_timeout`,
`resource_limit`, `native_cancelled`, and `native_turn_failed`. No text is committed on failed native
inference or input-limit admission. An oversized transport line ends the process.

## Durability and concurrency

The SQLite database uses WAL and FULL synchronous transactions with private file
permissions. Its path belongs to trusted launcher configuration. Local durability
still depends on the underlying filesystem/storage; this is not distributed storage
or a backup service. Use it on this host, not as a cross-machine shared-filesystem
coordination protocol.

A claim is committed before MORK retrieval, ECAN, NARS, or model execution.
Successful user/assistant history, internal derived-observation ledger, response,
revision increment, and claim completion are saved in one transaction.
The response is emitted only after that transaction commits. A crash before commit
leaves no partial history; a crash after commit but before delivery can return the
saved response value. These guarantees concern the local transaction, not rollback
of inference computation or exactly-once distributed delivery.

Reusing the same ID and identical normalized payload returns the saved successful
or truncated JSON response value without model inference. Changing its payload or expected
revision yields `request_conflict`. Failed IDs repeat as `failed`, rather than
replaying the original error response; neither failed nor interrupted IDs rerun.
JSON object key order is not part of the replay guarantee.
Concurrent processes cannot claim the same session revision twice. There are no
lease-expiry retries: unresolved pending work requires explicit recovery.

## History and model limits

All committed messages remain durable and are available through `snapshot`.
The model receives complete history; no messages are silently dropped or summarized.
Native admission remains 512 input tokens, 1,024 context tokens, a 16 KiB rendered
prompt, and at most 128 generated tokens. Reaching input limits fails without a
commit. Without MORK, the v2 session has a 128-exchange admission ceiling. With the
qualified MORK profile, it admits four complete exchanges (eight messages),
4,096 UTF-8 bytes per message and 65,536 serialized history bytes. A fifth
exchange returns `history_limit` without dropping prior messages. Native token
limits will usually be reached first. To continue beyond admission, explicitly create a
new session and supply a user-approved summary; no automatic summary is substituted.

ECAN is the real pinned attention-bank subset on PeTTa, ephemeral and advisory.
Its source is separately acquired and hash-checked before and after execution.
It is not full ECAN diffusion/scheduling.

An optional `mork_memory` profile uses the pinned native MORK candidate in a
separate SWI-Prolog process to index typed turn IDs and roles. SQLite remains
the authoritative durable store; the adapter demands every expected native row
before hydrating its original text in order. There is no matching fallback or
automatic recovery. The pinned PathMap predates its zipper fix, so this only
qualifies the bounded adapter workload, not arbitrary MORK workloads.

An optional `nars_cognition` profile recognizes exactly two controlled-language inheritance
assertions forming a three-symbol chain. It admits singular/plural `is`/`are`,
reviewed articles, reversed premise order, periods/semicolons/`and`, bounded
multiword labels, and explicit `Assume`/`Suppose` premises labeled hypothetical.
There is no stemming or synonym/pronoun resolution. Reserved qualifiers and
`-ly` words are refused conservatively; this finite lexical grammar cannot
classify every possible English modifier or ambiguity. Other prose does not run
NARS. Actual native NAL-1 deductions enter the model prompt as uncertain beliefs,
with premise values explicitly labeled controller policy. The internal ledger
is restored across worker restarts and commits with history; failed or cancelled
turns do not commit new observations. It is separate from ECAN `context_ids`.
NARS evidence is bound to the claimed `{session_id, request_id, revision}`;
`revision` is the pre-turn CAS revision. The internal observation ID is `nars_`
plus the SHA-256 of that canonical binding. A unique suffix isolates evidence
attempt directories. Before native execution, a private fsynced `turn-start.json` records the binding,
snapshot and exact native request. The full binding digest also enters each
native premise's provenance; the native task ID carries a bounded digest prefix.
The native child writes under a separate `native/` directory. A completion
`turn-binding.json` links the binding, snapshot and native request/response hashes.
A failed inference retains its pre-execution record, without committing cognition.
Duplicate observation IDs are rejected before model invocation and again at the
durable store boundary. Saved replay performs no inference.
No public v2 fields changed for either integration.
No full autonomous Omega loop, model-generated command execution, guest deployment,
or graphical desktop qualification is implied.

## Verification

`probe_durable.py --profile ABSOLUTE_PROFILE --output NEW_DIRECTORY` runs actual
ECAN/Granite turns across process restarts, saved replay, stale CAS, explicit output
limits, input-limit rejection, active cancellation and explicit recovery. It creates
synthetic story history in a private database under its new output directory.
Source tests include real SQLite competing writers and process-crash cases; API
callback tests explicitly use a fake provider and are not model evidence.

## Optional native learning tasks

A v2 turn may include `cognitive_tasks`, a list of zero to three objects with
exact fields `component` and `request`. Component names are `metamo`, `airis`,
`nace`, and optionally `ai_dsl` or `os_state`, with no duplicates and at most three tasks.
Requests use each component's existing bounded
typed contract; the text model never supplies their state, features, rules or
training data. See `tests/learning_fixtures.json` for complete synthetic examples.
The full list is included in the durable request fingerprint: changing a task
while reusing a request ID returns `request_conflict`.

A locally qualified `learning_components` profile is required. Missing runtime,
failed native verification or failed generation prevents transcript/observation
commit. Runtime paths, manifests and commands cannot be supplied by a request.
Native results become advisory prompt observations. Existing context/token limits
still apply; supplying multiple tasks does not enlarge the model's admission.

Successful task-bearing responses additionally include `cognitive_results`:
`[{"component":"metamo","observation_id":"...","result":{...}}]`.
These are verified structured component results, distinct from unverified model
`text`. They commit atomically with the response, transcript and observation
ledger and replay without reexecuting any native component. No action authority
is added. Ordinary requests and their response shape remain unchanged.

## Resource failure diagnostics

A recognized supervisor deadline produces `native_timeout`; its native RSS or
host-reserve stop produces `resource_limit`. A recognized supervisor cancellation
can produce `native_cancelled` when the worker remains alive to report it. These
codes require both the exact supervisor completion marker and matching exit code.
Raw evidence remains retained. No generation metadata or successful history is
invented after a resource stop. Failed request IDs remain terminal; a new request
may continue from the unchanged revision. Killing the worker itself still uses
the existing pending-claim and explicit recovery contract. Resource caps are
unchanged.

## Read-only capacity query

`{"api_version":2,"op":"limits","session_id":"story"}` returns `status:
limits`, the current `revision`, `history_messages`, `max_history_messages`,
`remaining_exchanges`, `pending`, `history_admits_turn`, `input_token_limit:512`,
`max_output_tokens:128`, `token_admission:checked_during_native_inference`,
`history_policy:complete_no_omission`, and `executed_actions:0`.

This query creates no session or claim and performs no inference or retrieval.
With MORK enabled, four exchanges are admitted; the fifth is refused. The
history flag also accounts for a pending claim. It does not predict rendered
prompt token count or reserve capacity: the subsequent turn must still supply
`expected_revision` and pass native token admission. Existing clients can
continue using the existing turn and snapshot operations.
