# Durable conversation integration checkpoint — 2026-11-09

> Historical v1 checkpoint evidence. The current endpoint is `durable_server.py`
> with the published durable v2 API (`components/conversation/DURABLE_API.md`).
> Its client request IDs, replay, CAS claims and explicit recovery supersede
> the v1 server-generated IDs and automatic abandoned-request cleanup below.
> Original qualified profiles remain bound to the original checkout, not this merge.


Latest update: `../components/conversation/DURABLE_MORK.md` records the actual
PeTTa/Omega/Granite + native MORK restart and cancellation proof. The new
`prepare_exchange` / `accept_exchange` methods stage user input and commit both
messages atomically, preserving the parent controller's failure semantics.
`abandon_open_requests` requires an exclusive host lease; the integrated host
provides one. These coexist with the original explicit append/response APIs.

Update: a separately identified private native rebuild subsequently passed ten
real query/integration probes. See NATIVE_REBUILD.md for its exact identity and
explicit `native_backend` interface. The historical/default runtime remains
unavailable. At that intermediate checkpoint the live loop was still unexecuted. The remainder of
this document records the initial checkpoint's scope and tests.

This is working SQLite history and host-side Omega request preparation, not a
qualified native MORK/PeTTa conversational loop. SQLite is not MORK. The native
adapter and its binary/helper pins were not changed. Native failure returns no
retrieval receipt; there is no Python matching fallback.

## Host interface

Place `mork-recovery-v1/source` on the trusted host's module path. Create
`ConversationStore(private_database_path)` only after the host has enforced
access and retention policy. The database is unencrypted; use a private parent
directory. Session strings and receipt tokens are binding identifiers, not
authentication or permission. The host owns all API calls, IDs and source labels.

1. `append(session, admission_id=..., role='user', content=..., source=...,
   expected_revision=...)` durably admits a reviewed message. Identical retries
   return the same turn ID; reusing an admission ID for different data fails.
2. `prepare_omega_request(store, providers, session, request_id=...,
   expected_revision=..., system_prompt=..., max_messages=...,
   max_characters=..., max_tokens=128)` returns `(request, receipt)`. `providers`
   is the host's already-loaded Omega providers module. This function does not
   start a provider, invoke chat, import MeTTa, or dispatch any tool. Supply the
   selected provider's real limits; stricter token limits remain its job.
3. After independently validating a provider's response, call
   `accept_response(session, request_id=receipt['request_id'],
   request_token=receipt['request_token'], content=approved_text)`.
   A response cannot commit against changed history or another request/session.
4. `snapshot(session)` reloads complete history. `forget(session)` transactionally
   removes history and saved request receipts. `close()` releases the connection.

Direct `prepare(session, request_id=..., expected_revision=..., role=None,
timeout=3)` is available to the parent controller without Omega message building.
It calls the existing native-only `query_facts` on typed `chat_turn(turn_id, role)`
facts. A role filter may be `user`, `assistant`, or `None`. It does not extract
semantic facts from message content or evaluate generated rules.

The native result's implementation label is preserved. Provenance contains
session, revision, request ID, a history digest, stable turn IDs, text hashes,
source labels and admission times. Source labels are caller assertions, not
proof that a claim is true. History text remains in its original user/assistant
role. Only the host's explicit system prompt becomes a system message. Retrieved
evidence remains in the receipt and grants no action authority.

## Durability and bounds

The authoritative transcript holds at most 32 messages, each at most 4096 UTF-8
bytes, and at most 65536 UTF-8 content bytes in total. Capacity exhaustion raises
an error; no transcript is silently discarded. MORK sees only the latest 16
turn-role index entries, explicitly marked in every receipt. This limited index
does not claim to retrieve older messages or perform semantic search.

Writes use SQLite immediate transactions and FULL synchronous mode. History,
request/response association and acceptance survive reopening. Up to 64 request
records per session are retained. Native calls execute outside the write lock;
the history digest and pending request are checked again before saving a receipt.
Native failure/cancellation marks the request failed; crashes may leave pending
requests. Neither is replayed as successful: retry with a fresh host request ID.
An accepted response and its completion state commit atomically. Host response
admission is explicit; saving provider output does not authenticate its claims.

Secure deletion is enabled, but backups and storage-device remnants are outside
this API's guarantee. There is no global session quota. The host must implement
account access, consent, overall storage policy and backup deletion. No code here
provides a sandbox for arbitrary model/provider code.

## Evidence and remaining work

Both supplied archives were consumer-locally materialized using the current
Library transfer helper. Every entry in their embedded SHA-256 manifests passed.
The public checkout is based on `75486634b950afa7c1493e913f230113fe15a094`.
The bundle's branch `11d635e9eb464f5374dbbfdd74e6d97ff285e32e` was recovered as
`recovered/ai-mork`; it was not merged over public artwork or other later files.

`python3 -B -m unittest discover -s mork-recovery-v1/tests -v` passes 66 tests.
The new tests exercise real SQLite reopen, revision conflicts, interleaved writes,
capacity, session isolation, deletion, stale responses and a real unavailable
native-runtime failure. Positive native and Omega API responses use explicitly
named contract doubles. They are not native execution evidence.

Missing: the exact two pinned MORK shared objects, pinned SWI-Prolog runtime,
historical Cargo lock/toolchain closure, and live PeTTa/Omega runtime. The supplied
archive explicitly excludes native binaries. Cargo/SWI were absent from PATH.
Fresh source downloads cannot establish historical binary identity. A replacement
build requires separately recorded dependency closure and qualification, not
silently changing the adapter's existing hashes. No native process was qualified,
no model weights were acquired, and no external actions were dispatched.

A Library title search found `roko-conversation-memory-hook-v1.tar.gz` and
`roko-mork-recovery-v1-source-proof.tar.gz`. The required search-result download
helper failed with `hosted apps tools/list request failed with HTTP status 401`.
Neither was materialized, inspected, merged, or automatically retried. The parent
must reconcile its current hook against this interface before claiming live
integration. The runtime-artifacts split archive was only discovered by title;
its contents have not been inspected and no claim is made about its binaries.

All repository changes are local and uncommitted. Nothing was pushed.
