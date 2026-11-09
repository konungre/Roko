# Parent handoff: actual durable native conversation

> Historical v1 checkpoint evidence. The current endpoint is `durable_server.py`
> with the published durable v2 API (`components/conversation/DURABLE_API.md`).
> Its client request IDs, replay, CAS claims and explicit recovery supersede
> the v1 server-generated IDs and automatic abandoned-request cleanup below.
> Original qualified profiles remain bound to the original checkout, not this merge.


Outcome: actual PeTTa/Omega provider dispatch and local Granite inference now use
native MORK-selected durable history. `durable-native-proof-002/SUMMARY.json`
passes restart recall and cancellation with zero dispatched external actions.
This is a bounded host integration, not autonomous Omega or a guest release.

Current qualified launch binding on this computer:

```sh
ROKO_FRESH_PROFILE=/workspace/conversation-runtime-symbolic/durable-profile-002.json \
  /opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -B \
  /workspace/Roko/components/conversation/fresh_server.py
```

The profile's SHA-256 is
`223db0a4b5572957eb3feba510b30d946464f4e40401b514a4e3ffe6fafc3b1c`.
Its database is `/workspace/conversation-memory-state/probe-002.sqlite`, namespace
`durable-probe-002`, containing four synthetic proof messages. Do not present it
as a clean user session. Generate a new host profile/private database for that.

The JSON-lines transport is unchanged: `{text, context: []}` in, exactly
`{text, context_ids: [], executed_actions: 0}` out. No request can choose a
program, provider, file, namespace, query language or runtime profile.
The conversation still allows at most four exchanges; do not silently reset or
truncate its durable history. Provider prompt/token caps may reject earlier.

Native host integration uses `ExternalMORKBackend(profile)` inside Janus.
It invokes a separately supervised Python worker, which calls
`RebuiltMORKCandidate.query_facts`. Do not invoke the old signal-owning native
supervisor directly inside Janus: attempt 001 exposed incompatible C signal
handlers. Its failed receipt is preserved. No historical hash pin was weakened.

Storage API additions:

- `prepare_exchange(session, request_id=..., expected_revision=..., content=...,
  source=...)` stages user data and obtains native evidence without appending it.
- `accept_exchange(session, request_id=..., request_token=..., content=...)`
  commits the staged user and admitted assistant text atomically.
- `abandon_open_requests(session)` discards staged text after failure/restart;
  only call while holding an exclusive host lease. `open_session` supplies it.

The real proof performed two separate worker launches. The second native MORK
receipt returned IDs `t000000000000` and `t000000000001`; Granite answered
"You mentioned a lighthouse." The third inference was cancelled with no answer,
no live native group and no history change. Restart then cleared open requests.
32 conversation/lifecycle tests and 69 memory/helper tests pass; contract doubles
in those suites are separate from the genuine end-to-end evidence.

Known boundaries remain: source labels are assertions, model text is unverified,
turn-role lookup is not semantic inference, SQLite is the durable store, and
the transport is not exactly-once delivery. The PathMap candidate predates a
zipper bug fix; qualify only this bounded adapter contract. No graphical desktop,
guest image, arbitrary MORK program or autonomous-action safety claim is made.

The supplied parent bundle/handoff and every embedded manifest entry were
verified locally. Branch `55bebd8d79454c765b258b27471ad54a971700e5` was recovered
without merging over the memory changes. Prior checkpoints remain intact.
The review branch is `codex/native-durable-memory`, based on the recovered
conversation commit above. The parent owns independent review and merging. Model weights, upstream
runtime sources/binaries and SQLite state are excluded from the source handoff.
Profiles contain this host's paths/hashes; other computers need new local builds
and qualification profiles, never rewritten historical identities.
