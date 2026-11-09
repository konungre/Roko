# Bounded conversational Omega extension (not native-qualified)

This component replaces neither Omega nor its message state with a Python loop.
`worker.pl` loads the externally supplied Omega `src/loop.metta` and `src/utils.py`.
`step.metta` schedules one receive/infer/commit step using Omega's actual
`messagesAppend` and `messagesGet` state operations. Python provides data validation,
local Granite inference and the existing native ECAN adapter. This is a new bounded
Omega loop extension, **not execution of upstream's unbounded `(omega)` loop**.
Upstream's tool-execution loop is intentionally not invoked by this conversational
entry point. No generated text is parsed as MeTTa or executed as a command.

Input is JSON lines: `{"text":"What should we talk about?","context":[]}`.
Optional symbolic records have exactly `id`, `text`, `sti`, `lti`, `stimulus`.
The native ECAN adapter ranks up to 16 records and its attentional focus selects up
to four for the advisory system context. Empty context skips ECAN; it does not
claim an ECAN result. Missing ECAN fails a contextual turn rather than silently
substituting Python ranking. Native ECAN still uses its existing ephemeral bank;
long-lived attention economics are not implemented here.

History retains four complete exchanges in memory. Failed turns do not commit.
Token overflow fails explicitly rather than silently losing conversational history.
The existing native inference executable imposes 1024 input / 128 output tokens.
There is no action execution, HTTP provider, automatic dependency installation,
or automatic source acquisition. The bounded input/output and timeout are not an
OS sandbox. Offline tokenizer loading is enforced; process-level network denial
must be provided by the live-system launcher.

## Run

Set `PETTA_PATH`, `OMEGA_PATH`, and `ROKO_RUNTIME_ROOT` to separately reviewed local
runtime roots. `ROKO_SWIPL` optionally selects the Janus-enabled SWI executable.
The runtime root uses the existing baseline model/tokenizer lock and native ECAN
source lock layout. Configure SWI/Python shared-library paths for that runtime.

```
python3 -B components/conversation/run.py --check
python3 -B components/conversation/run.py --probe
python3 -B components/conversation/run.py
python3 -B -m unittest discover -s components/conversation/tests -v
```

The probe sends two open-ended writing-project turns through the real worker.
A successful transport still requires reading the answers to assess relevance,
continuity and factual grounding. There is no mock fallback in the native runner.
The source unit tests use test doubles and are not end-to-end native evidence.

## Coordination and current blockers

Branch: `dev/ai-openai`, isolated from `main` at `7548663`.
- ai-symbolic: supply bounded, attributed symbolic records through the above input
  contract; do not provide executable source. Scores currently come from caller
  evidence, not an automatic salience estimator.
- ai-mork: durable conversation history is a follow-up integration; current history
  is session-local and must not be represented as persisted MORK memory.
- ai-learning: future learning records can use the same symbolic record contract;
  this component neither mutates learned policy nor claims learning results.
- desktop-avatar: consume reply JSON `text`, `context_ids`, `executed_actions`.
- live-system: restore the pinned local tokenizer, inference executable, compatible
  Python/Janus and native ECAN closure, then run `--probe` under network denial.

Current local inspection found recovered Granite GGUF weights but no
`omega-granite-infer` executable or baseline tokenizer closure at the expected
runtime root. The first recovered SWI invocation failed loading `libswipl.so.10`;
setting its restored library paths allowed `swipl --version` to report 10.0.2.
Janus/PeTTa execution in that relocated environment still needs qualification. Native conversational
turns, native ECAN-in-conversation, and MeTTa worker behavior remain unqualified.
No upstream/private runtime source or model bytes are added to this component.
