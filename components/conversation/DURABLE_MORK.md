# Durable native MORK conversation integration

> Historical v1 checkpoint evidence. The current endpoint is `durable_server.py`
> with the published durable v2 API (`components/conversation/DURABLE_API.md`).
> Its client request IDs, replay, CAS claims and explicit recovery supersede
> the v1 server-generated IDs and automatic abandoned-request cleanup below.
> Original qualified profiles remain bound to the original checkout, not this merge.


This host profile connects the actual PeTTa/Omega conversation step to native
MORK retrieval and SQLite-owned history. It preserves the bounded, inert-text
provider path. It does not run Omega's autonomous action loop.

## Observed result (2026-11-09)

`/workspace/handoff/durable-native-proof-002/SUMMARY.json` reports `passed=true`.
Two separate PeTTa workers completed actual Omega/Granite turns. The restarted
worker retrieved the prior two messages through native MORK and answered
"You mentioned a lighthouse." Native inference took 68.230 and 58.628 seconds;
complete worker phases including startup/hash verification took 97.719 and
84.682 seconds. Four transcript messages survived restart.

A third real inference was cancelled after observing its supervisor and native
child. It emitted zero answer bytes, left history unchanged and left no live
native group. A subsequent EOF-only restart preserved all four committed messages
and reduced open requests to zero. Three successful MORK retrieval receipts were
observed across the two completed turns and cancelled attempt. No external actions
were dispatched and no Python matching fallback was used.

32 conversation/lifecycle/SQLite tests pass with the real SWI bounded-reader
tests enabled; 69 memory/helper tests also pass. Positive contract doubles in
those source suites remain explicitly labeled and are separate from the native
proof. This is one bounded restart/cancellation scenario, not exhaustive fault
coverage or a general model-quality evaluation.

Qualified local test profile:
`/workspace/conversation-runtime-symbolic/durable-profile-002.json`, SHA-256
`223db0a4b5572957eb3feba510b30d946464f4e40401b514a4e3ffe6fafc3b1c`.
This profile is bound to the synthetic test database containing the four saved
messages. Create a new explicit profile/database for a clean user session.
The restored parent branch is `55bebd8d79454c765b258b27471ad54a971700e5`; the
configured repository base and original uncommitted memory work were preserved.

## Runtime path

The launcher starts PeTTa in SWI-Prolog 10.0.2 with Janus/Python 3.12. It imports
the pinned Omega utilities, loop state and provider registry. Before each model
turn, `DurableSession` stages the new user message and queries MORK for committed
`chat_turn(turn_id, role)` facts. Native-selected evidence supplies Omega's
message history. Actual Omega `LLMRequest`/provider dispatch calls the local
Granite CPU runtime; only one inert `reply(text)` result is admitted.

MORK runs in a separate Python-supervised SWI-Prolog 9.3.34 process using the
private rebuild candidate. Its FFI never loads into the PeTTa/Janus worker.
This separation is required: the first integration attempt encountered a Janus
C signal handler that Python could not restore. That attempt produced no answer
and committed no history; its failed receipt is preserved. The historical MORK
supervisor's signal handling and hashes were not relaxed to hide the failure.

`mork_host.py` validates bounded facts and calls the real rebuild backend from
standalone Python. `mork_supervise.py` reuses the parent-death and descendant-
cleanup supervisor with MORK's original 16 GiB virtual-address limit. The 5 GiB
aggregate RSS cap and 4 GiB available-memory floor remain. Native MORK keeps its
own 1–5 second query deadline and byte/output bounds; its outer supervisor
allows eight additional seconds for setup/cleanup. Network denial is inherited
and installed again around the native query. There is no matching fallback.

## Durable behavior and provenance

The host profile explicitly binds one database path, session namespace and MORK
manifest digest. JSON requests cannot choose them. The parent directory must be
private and host-owned; the host holds an exclusive database lease throughout
the worker lifetime. Session identifiers are namespaces, not authentication.

Preparing a request stores a pending receipt but does not append transcript
messages. After Omega validates the reply and the provider verifies model
identity, the user and assistant messages commit in one SQLite transaction
against the original revision/history digest/request token. Any failed second
insert rolls back the first. A restart reloads complete committed history and
abandons open requests before admitting another turn. Pending text is removed
from those abandoned receipts; their request IDs remain unusable.

Every native retrieval receipt binds the session, request ID, revision, history
digest, evidence IDs, per-message hashes, source labels, admission times and exact
native runtime digest. Source labels are caller assertions, not proof of truth
or authority. Model responses remain unverified text. Raw conversation text
stays in SQLite and Omega message objects; MORK sees only typed turn IDs/roles.
This is a native symbolic turn index, not semantic search or a general persistent
MORK graph. The full transcript is supplied without silent truncation.

The existing conversation limit remains four exchanges/eight messages, below
MORK's 16-fact index bound and the storage module's 32-message/64-KiB ceiling.
The model keeps the 512 input-token, 64 output-token, 16-KiB rendered prompt,
150-second inference and four-thread limits. UTF-8 storage limits can reject a
message that passes the older character limit; rejection commits no transcript.
Nonempty external ECAN context remains unsupported by this fresh profile.

Input and output schemas are unchanged:

```json
{"text":"What setting did I mention?","context":[]}
```

```json
{"text":"Unverified model response","context_ids":[],"executed_actions":0}
```

EOF preserves committed history for a later explicit restart of the same host
profile. Malformed requests and cancellation end the worker; previously committed
history remains. Cancellation during inference cannot commit a half exchange.
Cancellation after a completed database commit does not undo it. The transport
still has no client request IDs or delivery acknowledgment: it is not exactly-
once delivery, and clients must not silently replay an uncertain request.
Staged text can remain after abrupt death until the next exclusive startup.
The database is unencrypted; retention consent, backup deletion, account access
and overall quotas remain host responsibilities.

## Host preparation and execution

Generate a NEW profile with `qualify_fresh.py`, supplying the reviewed symbolic
profile, local Granite executable/model, and all four memory arguments:

```
--mork-manifest ABSOLUTE_RUNTIME_MANIFEST
--mork-manifest-sha256 REVIEWED_DIGEST
--history-database PRIVATE_ABSOLUTE_DATABASE
--session-id HOST_OWNED_NAMESPACE
```

The generator refuses to replace an existing profile. Do not rewrite old
profiles to admit new bytes. `ROKO_FRESH_PROFILE` selects that immutable host
configuration; use its explicit Python to launch `fresh_server.py`. Existing
profiles without a `durable_memory` section retain the original in-memory mode.
Do not infer that a prepared profile has passed native tests.

`probe_durable.py --profile PROFILE --output NEW_DIRECTORY` performs one model
turn, restarts the entire worker, asks for the remembered setting, cancels a third
real inference after observing its native child, and restarts with EOF to verify
abandoned-request cleanup. It requires a new database and preserves failures.
The original handoff, failed attempt 001, and later proof receipts remain separate.

The MORK candidate retains PathMap `5f2118c...`, before the later zipper bug fix.
Its evidence is limited to the bounded adapter tests and this conversation path.
There is no claim of safety/correctness for arbitrary MORK programs. Historical
runtime pins are unchanged. MORK/FFI binaries and source, model weights and other
upstream runtime trees are excluded from the source checkpoint. This remains
host development, with no guest-image, graphical-desktop or autonomous-action
qualification. See `mork-recovery-v1/NATIVE_REBUILD.md` for exact build identities.
