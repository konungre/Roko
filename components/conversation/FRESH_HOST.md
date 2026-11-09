# Fresh cloud host profile

The opt-in NAL-1 cognitive successor is now separately qualified on a rebuilt
executor. See [actual cognitive integration](COGNITIVE_INTEGRATION.md). The
baseline and historical native summaries below retain their original scope.

This profile rebuilds the runtime on a separate cloud computer. It does not
substitute new binaries for the historical recovered-host hashes. The original
`recovered_server.py` admission and handoff remain available unchanged.

The source branch starts at `b017853706687928c5d2db81f87976ed0be7167f`, which
descends from the configured published repository checkpoint
`75486634b950afa7c1493e913f230113fe15a094`. Development uses a separate clone.

## Desktop transport

Set `ROKO_FRESH_PROFILE` to the absolute locally qualified profile JSON and run
`fresh_server.py` with the profile's Python interpreter. Inherit that environment
in the chat-bubble process. No request can choose paths, programs or providers.

Input, one JSON object per line:

```json
{"text":"What could I write next?","context":[]}
```

Output, exactly three fields:

```json
{"text":"Unverified model-generated text","context_ids":[],"executed_actions":0}
```

The process owns one in-memory session. EOF closes it; malformed input, overflow
or runtime failure ends it. The client must mark the session unavailable and
offer an explicit new conversation, without silently replaying messages. Send
SIGTERM to cancel and discard the session. Diagnostics go only to stderr.
Allow 180 seconds per turn, plus initial profile/model verification.

Cancellation deliberately kills the SWI worker rather than asking Janus to finalize
Python mid-call. The first native cancellation check exposed a SIGTERM-time
`Py_FinalizeEx` crash in that path; its evidence is retained. The independent
inference supervisor owns descendant cleanup after worker death. Normal EOF still
completes model verification and writes the session receipt.
Launcher exit alone is not a synchronous cleanup acknowledgment; cancellation
qualification separately waits until the owned native group disappears. Cancelled
sessions do not produce the normal final history/model receipt.

Only empty context is qualified by this profile. Nonempty context fails explicitly
until a real ECAN closure is separately restored and qualified; no heuristic ranker
is substituted. The original recovered-host profile retains its native ECAN path.

## Native path and bounds

The actual PeTTa worker imports the pinned Omega utility, loop and provider code.
`rokoRecoveredStep` uses Omega's message state and actual `LLMRequest`/provider
registry; the registered local provider renders Granite roles and calls the CPU
inference binary. Its reply is wrapped as inert text for response admission. User
and model text are never evaluated as MeTTa or executed as shell commands.

The new inference source is `fresh-infer.cpp`, derived from the published
`omega-baseline/integration/granite-infer.cpp` and upstream llama.cpp's MIT example.
The tokenizer is the pinned GGUF's embedded tokenizer. No remote Python model code
or network inference service runs. The input delimiter escaping is retained.

Bounds: four exchanges per session, 4,000 characters per user message, 16 KiB
rendered prompt, 512 native input tokens, 64 generated tokens, 1,024-token native
context, four CPU threads. Responses can end at the token cap; no automatic repair
or retry occurs. Native supervision enforces a 150-second deadline, 5 GiB aggregate
RSS limit, 6 GiB address-space limit and 4 GiB available-memory floor. Startup
requires 7 GiB available memory and 4 GiB free disk. These are trusted native-process
bounds, not a general hostile-code sandbox.

The child inherits a seccomp network denial. The worker is bound to the launcher's
lifetime; inference has a separate descendant-cleaning supervisor. The model is
opened read-only, pinned by descriptor, and hash/identity checked before inference
and before committing history. The prepared profile hashes source/runtime inputs.

## Requalification

Obtain and build the pinned public source dependencies, preserving their licenses
and build provenance. Compile `fresh-infer.cpp` against llama.cpp commit
`f7591a6a01f9273de03331732bdc0b39721168be`. Use the supplied Granite lock for the
exact repository, revision, filename and full SHA-256. Do not reuse a profile from
another machine or rewrite an old recovery lock to make new bytes pass.

`qualify_fresh.py` combines a reviewed symbolic runtime profile with the new model,
inference binary, resolved shared libraries and current conversation source. It
creates a new profile and refuses to overwrite an existing one. Preparation alone
does not establish native conversation success.

`probe_fresh.py --profile ABSOLUTE_PROFILE --output NEW_DIRECTORY` records two real
native turns, strict response schema, cleanup receipts and lighthouse recall. It
also records exact source/profile hashes and preserves failed attempts. Run the
source and lifecycle tests with:

```sh
python3 -B -m unittest discover -s components/conversation/tests -v
```

This is host development. It does not qualify a guest image, graphical desktop,
durable memory, MORK projection, learning, full autonomous Omega execution or the
quality of all generated replies.
