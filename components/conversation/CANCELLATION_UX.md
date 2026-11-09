# Cancellation UX candidate rebased on merged main

Base: ab5dfe1e0270c3723eccff5f6a928e2abdb54a98, including PR34 and the existing
DesktopReplyPanel/provenance work. CancellationUX delegates committed-response
validation to that panel and exposes its neutral provenance view; it does not
maintain an alternative authority grant. It uses existing repository adapters without duplicating them. This source
proposal adds no transport executor or production activation. No GUI source was accessed and no production profile activated.

## Qualification

Twenty-two deterministic tests passed, plus five offline captured-packet consumer
checks. Fresh live qualification passed 20 checks and a read-only SQLite audit
added 6, for 26 passing live/audit checks on the merged source base. Two real native
Omega/PeTTa/Granite replies completed at 531 and 536 input tokens through an explicit
experimental 768 profile. This does not change the default 512 budget.

The first scenario stopped an actually resident inference process after a pure
stop proposal had left it running. An owned Popen worker was stopped only after
registry binding validation; native descendants disappeared before the local stop
callback. A pre-stop snapshot ticket was rejected. Fresh inspection exposed the
real pending claim, explicit recover returned interrupted, and another fresh
inspection/review released the turn. Draft text was retained. A user-chosen new
ID then completed real inference; it reused neither the interrupted ID nor a
silently rewritten draft.

The second scenario deterministically deferred a valid local stop proposal until
a real committed reply arrived. The reply disabled execution of the queued stop;
the transport suppressed it, full snapshot review retained the draft, and the
worker remained usable. This is a controlled commit-before-stop ordering, not a
claim to statistically exercise simultaneous OS scheduling races. Successful
native generation was serial. No graphical widget was involved.

The final store held all 16 messages, unchanged six-turn history prefix and both
original NARS observations. The stopped request was terminal interrupted; the two
new IDs were committed with responses identical to the delivered replies. Revision8
had no pending claim. The source six-turn checkpoint remained revision6/read-only.

## Controller contract

CancellationUX proposes actions only; it has no transport, process/signal executor,
clock, timer or automatic retry. Draft edits remain separate from captured input.
Only one Send is captured at a time; stop/replay/recovery proposals cannot be
repeated while unsettled. Old identity reuse is refused as a new turn. Exact replay
keeps its original payload and expected revision.

The transport registers worker_binding() with its own opaque worker/process
identity. Just before executing a stop, supply its CURRENT registry binding to
can_execute_cancel(..., current_binding=...). Stop only that still-owned bound
worker; do not infer handles/PIDs/actions from model/server text. Nonces fence
stale callbacks across turns and instances, not authenticate producers. A local
stop proposal is not a new JSON-lines op:cancel. Existing backend owner-death checks
remain decisive for op:recover. A local exit observation alone never grants
recovery success; busy requires fresh inspection and another explicit decision.

Matching committed replies suppress unexecuted cancellation. They never append
local transcript entries or erase drafts. Release requires a fresh snapshot that
contains the exact committed pair. Interrupted recovery similarly requires new
inspection/review. Conflicting terminal outcomes reject. Unknown reply fields
cannot supply controls; all display text is plain text. Waiting remains distinct
from failure even after a long elapsed interval.

transcript=null/transcript_available=false means no current accepted snapshot;
retain the application's session-keyed cached transcript. An accepted empty list
means a confirmed empty snapshot. This controller is not a durable session/draft
store. Real GUI, owned-worker registry, transport event wiring and crash persistence
remain future client integration work.

## Validation and reproduction

    python3 -B -m unittest discover -s components/conversation/tests -p test_cancellation_ux.py -v
    python3 -B -m unittest discover -s components/conversation/tests -p test_waiting_view.py -v

The 22 unit tests need no native runtime. The five captured-packet checks and raw
native traces remain in the local qualification checkpoint, not as claims of
independent reproduction. No failed artifact transfer was retried.

Run the live probe only with qualified external runtime/profile dependencies and
the verified six-turn synthetic language checkpoint, using a fresh output path:

    python3 -B components/conversation/tests/probe_cancellation_ux.py \
      --profile /absolute/path/to/experimental768-profile.json \
      --source-db /absolute/path/to/verified-six-turn/history.sqlite \
      --output /absolute/path/to/new-cancellation-evidence

The probe reads the source checkpoint through SQLite read-only mode, copies it,
starts two owned endpoint processes and explicitly stops one during resident
inference. It then performs explicit recovery and two real model turns. The
commit race deliberately defers a local stop proposal until a real committed
reply wins; it is not a statistical simultaneous-OS-race test. It writes raw
requests/stdout/stderr and result JSON. Expected time is several minutes.
It does not download a model, enable a profile, or touch the graphical client.

The source was qualified on merged main ab5dfe1. See CANCELLATION_UX_SUMMARY.json
for producer evidence scope. Model/binaries, actual GUI/worker registry/transport
implementation and crash-persistent drafts are outside this change.

The full local conversation suite ran 330 tests: 329 passed and one optional native
fixture skipped. These include the 22 focused waiting/cancellation tests.

## Uncertain recovery delivery

`recover(confirmed=True)` still returns only the existing backend packet. Capture
`recovery_ticket()` locally at that moment, and pass that captured value to
`receive_recovery_reply(packet, ticket=ticket)`. The local ticket is never a wire
field. Each operation has a distinct turn/serial ticket; old callbacks cannot
settle another attempt with the same backend identity.

If the recovery response is lost, call `transport_lost()`. It preserves the
outstanding operation as uncertain and fences previous snapshot tickets. Request
and accept a new matching snapshot, then explicitly call
`reconcile_recovery(confirmed=True)`. Reconciliation sends no request. If the same
claim remains pending at its original revision, the user can separately propose
another recovery with a new ticket. If no claim is pending, the user can review
and release; that snapshot alone does not claim a received interrupted receipt.
Other pending claims or stale/in-flight snapshots cannot reconcile the operation.
Retired callbacks reject after either path.

An observed owned-worker stop also clears the local outstanding replay flag and
fences its older snapshot tickets. A fresh own-pending snapshot can then support
explicit recovery. A matching committed reply is still admitted: stopping never
proves rollback. This fixes waiting-state dead ends without adding automatic
recovery/replay or changing backend packets.

A callback must retain the ticket captured when dispatching; it must not look up
the current ticket later. For example, bind it as the callback's local/default
argument. The reusable control-only probe exercises both server outcomes with
real dead-owner claims and no model generation:

    python3 -B components/conversation/tests/probe_recovery_reconciliation.py \
      --profile /absolute/path/to/qualified-profile.json \
      --source-db /absolute/path/to/verified-six-turn/history.sqlite \
      --output /absolute/path/to/new-reconciliation-evidence

This still needs the endpoint's qualified external dependencies for startup.
It uses real Store claims owned by a short-lived child, not real conversation
inference, and deliberately withholds results to test callback reconciliation.
