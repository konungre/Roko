# Local conversation through a bounded native Omega step

The recovered-host endpoint has completed real free-form Granite turns, a follow-up
that recalled the prior lighthouse setting, and native ECAN context selection.
The actual desktop `chat-bubble-v3` transport has completed a two-turn session.
This is a development host qualification, not a guest/COSMIC installation or a
complete autonomous Omega system. See `VALIDATION.md` and `PARENT_HANDOFF.md`.

## Desktop-compatible endpoint

Run `recovered_server.py` with an explicit trusted `ROKO_WORKSPACE_ROOT` environment
variable pointing to the existing development workspace. It verifies the pinned
symbolic closure, binds the matched SWI/Janus/Python runtime, installs inherited
child-only network denial, and keeps one worker alive for multiple turns.

Request JSON line:
```
{"text":"What could I write next?","context":[]}
```
Reply JSON line (exactly these three fields):
```
{"text":"A model-generated reply","context_ids":[],"executed_actions":0}
```

Replies are **unverified model text**. Diagnostics go to stderr. No request may
choose executables, providers, paths, roles or tools. Startup/runtime errors end
the process with diagnostics; the desktop marks the session unavailable and
requires explicit New conversation. It never silently replays a turn. This is
the existing desktop schema, not the older planned versioned/CAS API.

History is session-local, with a four-exchange limit. Overflow errors explicitly;
no earlier turns are silently removed. There is no durable history or retry
idempotency. Cancellation discards the session and is not rollback. The desktop
process watcher uses PID start identity, rather than a parent-thread death signal:
GUI transports may create the worker in a thread that exits after the first turn.
The native inference supervisor independently owns cleanup of its separate session.

## Actual cognitive path

1. The native worker imports unchanged Omega `src/loop.metta`, `src/utils.py`, and
   `src/providers.metta`; provider definitions must precede compilation of the step.
2. Optional symbolic records are validated and sent to the pinned actual ECAN
   gateway. Its worker completes and is cleaned up before model inference.
3. `rokoRecoveredStep` uses Omega's actual message state, constructs an actual
   Omega `LLMRequest`, dispatches through `llmProviderChat` and the real registry,
   admits a single inert `reply(text)` value, then commits the user/assistant pair.
4. The provider renders plain Granite conversation roles, runs the verified local
   generic CPU runtime, and verifies the model before promoting history.

The model generates free text: it is not asked to fill record_answer/contact/invoice
forms. The adapter wraps that text in Omega's required response carrier; the carrier
is never evaluated. Neither model text nor user text enters `sread`/`eval`. Upstream
`omega(1)` initialization, external-provider defaults, plugins, tool dispatch,
autonomous wakeups and recursive tail are not invoked. This is an explicit bounded
native derivative/extension of the turn, not execution of the unchanged full loop.

Optional context records contain exactly `id`, `text`, `sti`, `lti`, `stimulus`.
At most 16 records are accepted; native ECAN selects a focus of at most four.
The original user message and history remain intact regardless of that selection.
ECAN is ephemeral and advisory; this is not its full scheduler/diffusion system.
Empty context skips ECAN without claiming an ECAN result.

## Bounds and remaining work

The reused native binary enforces 512 actual input tokens, 64 output tokens,
1024-token context, four threads, a supervised 120-second deadline, 5GiB process
RSS limit and 6GiB address-space limit. Startup requires 7GiB available memory and
4GiB free disk; the supervisor retains the 4GiB available-memory abort floor.
Some replies can end at the 64-token cap; one qualification reply visibly did.
No output repair, retry, or claim of complete answer quality is made.

Remaining integrations: durable authoritative history/CAS and idempotency; MORK
memory projection; MetaMo/learning hooks; versioned product API; guest deployment;
native graphical interaction tests; broader conversation quality and output budgets.
The ordinary baseline `run.py` profile still requires its original runtime layout
and is not the qualified recovered-host entry point.

## Source tests and reusable development probe

```
python3 -B -m unittest discover -s components/conversation/tests -v
```

`probe_recovered.py --workspace ABSOLUTE_ROOT --output NEW_DIRECTORY` is the finite
recovered-runtime probe. Run it under the baseline `scripts/no-network.py` wrapper.
It refuses an existing output directory and preserves requests, source hashes,
stdout/stderr and results. Private runtime/source bytes are not copied into Git.
