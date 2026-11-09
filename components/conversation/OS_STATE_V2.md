# Imported OS profile observation in durable conversation

The optional `os_state` cognitive task has a closed read-only request:

```json
{"component":"os_state","request":{"version":1,"operation":"query_imported_profile"}}
```

The request cannot supply paths, receipts, runtime configuration or an operation
such as build, activate or rollback. Those names are rejected before claiming a
durable turn. Existing three-task and model context limits remain in place.

The trusted profile pins the OS owner's exported `roko-os-fact-v1` profile
history, native receipt bytes and source commit. The gateway verifies every
canonical receipt digest, consecutive revision and predecessor wrapper hash,
then projects only the latest observed private-profile operation. Actual local
PeTTa/Omega ingests the typed snapshot and queries all seven phases. The native
rows must exactly match the snapshot; file hashes are rechecked afterward.

The bounded observation tells Granite that the source is an imported external
Nix private-profile record. Full native data is returned separately in
`cognitive_results`, including source commit, revision, machine, receipt digest,
snapshot digest and the original v1 fact. The verified data correspondence does
not authenticate the source or establish current host, system activation,
running-system or health state. Those fields remain explicitly false. No Nix
command is rerun by this gateway, and no fact supplies mutation authority.

Successful results and observations commit atomically with the generated response
and history. Restart replay returns the saved structured result without Nix,
PeTTa, AI-DSL, Motto or model execution. The qualified source snapshot is pinned;
this endpoint does not silently follow changing OS files or claim to be a live
package-state subscription. A future source generation needs its own trusted
qualification and a new durable request.

Prepare the OS manifest with
`components.os_atomspace.conversation_gateway.prepare(SYMBOLIC_PROFILE,
FACTS_PATH, RECEIPTS_PATH, SOURCE_COMMIT)` and pass it to `qualify_learning.py`
using `--os-state-manifest`. This is preparation; the separate native probe
establishes actual runtime behavior. Existing profiles without OS state remain
valid, and an unqualified request fails closed.

`tests/probe_os_profile_native.py` combines the actual imported profile query and
actual AI-DSL search in one Omega/Motto/Granite turn, verifies both structured
results and atomic observations, rejects a mutation request, and restarts the
server to check replay without native execution. The Nix profile operations
occurred on the OS owner's executor; the cognitive test qualifies only its own
receipt verification, PeTTa queries and conversation dataflow.

The extended probe also makes an ordinary follow-up without cognitive tasks.
It checks that the source machine and revision are recalled from the committed
observation, that no new source query runs, and that both saved replies replay
after restart. This establishes receipt-aware conversation across turns; it does
not establish a live or authenticated observation of the current computer.
