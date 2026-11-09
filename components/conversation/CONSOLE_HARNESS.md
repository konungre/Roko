# Console waiting/cancellation behavior harness

`ConsoleHarness` is an explicit-action presentation prototype around CancellationUX.
It records proposals and renders readable terminal text; it does not open a
transport, execute signals, start a model, install a timer or retry automatically.
The live probes separately dispatch each proposal as a scripted confirmed user
action. This is not the graphical bubble or a production transport/worker registry.

Draft edits stay separate from captured immutable requests. Rejected duplicate
Send/Stop actions add no proposal. A worker binding advanced to another request
blocks Stop. Known completed errors retire the old binding; Stop cannot target
an idle worker for a finished attempt. Elapsed display resets on accepted Send,
not a duplicate click, and never infers failure or causes a request.

A session-keyed cache retains validated full snapshots across review/release and
the next capture. Unknown history renders 'not yet inspected'; a confirmed empty
snapshot renders zero. Stale, rewritten and malformed snapshots cannot erase the
cache. Model reply text is not appended into authoritative transcript history.
Late recovery/worker callbacks and idle connection-loss notices produce fixed
readable feedback without state mutation or tracebacks. Draft and reply strings
are JSON-quoted to escape terminal control sequences.

The console renders selected waiting/cancellation fields. It does not replace the
existing full reply/provenance panel, authenticate a producer, establish live host
health or grant model output mutation authority. Actual widgets must still render
plain text; durable drafts, a real transport and an owned-process registry remain
separate implementation work.

## Run without native dependencies

```sh
python3 -B -m unittest discover -s components/conversation/tests -p test_console_harness.py -v
python3 -B components/conversation/tests/demo_waiting_console.py --scenario recovery-loss
python3 -B components/conversation/tests/demo_waiting_console.py --scenario commit-wins
```

The 16 unit cases and two walkthroughs use deterministic/synthetic events, not
fresh model execution. The walkthrough header makes that distinction explicit.

## Run against a qualified endpoint

```sh
python3 -B components/conversation/tests/probe_waiting_console.py \
  --profile /absolute/path/to/qualified-experimental768-profile.json \
  --source-db /absolute/path/to/verified-six-turn/history.sqlite \
  --output /absolute/path/to/new-console-evidence
python3 -B components/conversation/tests/probe_waiting_console_limit.py \
  --profile /absolute/path/to/qualified-experimental768-profile.json \
  --source-db /absolute/path/to/new-console-evidence/history.sqlite \
  --output /absolute/path/to/new-limit-evidence
```

The first probe copies the verified revision6 fixture read-only, starts two owned
real endpoints, stops one during resident inference, explicitly recovers its
claim, deliberately withholds the control reply from the presentation, reconciles
only after fresh inspection, and completes one new native turn under a new ID.
The six initial exchanges are prior qualified fixture history; the new answer is
real Omega/PeTTa/Granite inference. The interrupted prefill is real execution but
never commits a reply. The final store/cache contains14 messages/two observations.

The second probe reads that resulting revision7 database and makes a separate
private copy. It tests a real over-budget request and context_limit feedback;
its native attempt returns input_limit with no generated text. Explicit snapshot/
review returns Ready without losing draft/history. It claims no fresh successful
generation in the error case. A withheld reply is a controlled presentation fault,
not a network-fault emulator. Successful generation is serial, not throughput
qualification, and results are cloud-local rather than target desktop measures.

Both probes require qualified external dependencies and a fresh output directory;
existing paths are refused. They neither download a model nor enable a profile.
The default512 input budget and sixteen-message history ceiling are unchanged.
Raw stdout/stderr, request logs, rendered console text and result JSON are emitted
for independent review. See CONSOLE_HARNESS_SUMMARY.json for exact evidence scope.
No graphical integration, production activation or alternate artifact transfer is
part of this change.

## Local qualification

The packaged live probes passed 29 checks on main 720ce74. The full suite ran
346 tests: 345 passed and one optional fixture skipped, including the 16 console
cases. The two console walkthroughs are synthetic. The native run has exactly
one newly completed model reply beyond the six-turn fixture; the limit case has
no successful generation. These results do not establish graphical or desktop
hardware qualification.
