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
and replayed unchanged. There is no automatic continuation, repair or retry. A user
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
`invalid_request`, and `native_turn_failed`. No text is committed on failed native
inference or input-limit admission. An oversized transport line ends the process.

## Durability and concurrency

The SQLite database uses WAL and FULL synchronous transactions with private file
permissions. Its path belongs to trusted launcher configuration. Local durability
still depends on the underlying filesystem/storage; this is not distributed storage
or a backup service. Use it on this host, not as a cross-machine shared-filesystem
coordination protocol.

A claim is committed before ECAN/model execution. Successful user/assistant history,
response, revision increment, and claim completion are saved in one transaction.
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
commit. The v2 session also has a 128-exchange admission ceiling; native token limits
will usually be reached first. To continue beyond admission, explicitly create a
new session and supply a user-approved summary; no automatic summary is substituted.

ECAN is the real pinned attention-bank subset on PeTTa, ephemeral and advisory.
Its source is separately acquired and hash-checked before and after execution.
It is not full ECAN diffusion/scheduling and does not provide durable MORK memory.
No full autonomous Omega loop, model-generated command execution, guest deployment,
or graphical desktop qualification is implied.

## Verification

`probe_durable.py --profile ABSOLUTE_PROFILE --output NEW_DIRECTORY` runs actual
ECAN/Granite turns across process restarts, saved replay, stale CAS, explicit output
limits, input-limit rejection, active cancellation and explicit recovery. It creates
synthetic story history in a private database under its new output directory.
Source tests include real SQLite competing writers and process-crash cases; API
callback tests explicitly use a fake provider and are not model evidence.
