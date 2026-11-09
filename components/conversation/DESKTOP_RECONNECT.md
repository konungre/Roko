# Desktop reconnect state

Based on main 19a253c81e0182c1d7745a7cdcb41a0d190d293b, including PR28.

ReconnectState is a local event coordinator, not a transport. Bind a controller
instance to one captured request and serialize its callbacks on the desktop event
loop. Keep transport callbacks and local tickets scoped to that instance/lifetime;
never restore tickets across process restart or use them as authentication.

On service loss call service_lost(). User Inspect callbacks call
request_snapshot(confirmed=True), capture its ticket locally alongside the actual
transport operation, and send only its packet to the backend. Do not send tickets
as new API fields. Pass the locally retained ticket with each snapshot callback.
Older epochs, earlier outstanding inspections and duplicate completions reject
before changing accepted draft/history. Invalid packets do not consume tickets.
Feed correlated errors through receive_error(), which invalidates earlier replies.

Route replay/recovery through propose_action() and release through
review_and_release(); do not bypass this wrapper using the held DesktopDraft.
Both are blocked while an inspection is outstanding. Every proposal remains
explicitly confirmed. No transport invocation, reconnect attempt, timer, retry,
worker termination, or automatic recovery exists here.

Display phase as idle / snapshot_required / snapshot_requested /
pending_owner_review / snapshot_review_required. These describe local review
state only: service_health stays not_established even after a valid snapshot.
Render every draft and transcript as plain text. A backend snapshot has no
transactional reservation; CAS and live-owner checks still apply at execution.

Run python3 -B -m unittest discover -s components/conversation/tests -p test_reconnect_state.py -v.

Qualification: seven deterministic tests and fifteen local real-v2-endpoint
checks passed. Four fresh endpoint processes supplied three sessions' snapshots;
the client delayed and reordered their delivery. All three stale-connection,
older-inspection and cross-session replies were rejected. Exact replay returned
the saved response, live-owner recovery remained busy, exited-owner recovery
returned interrupted, and drafts/full history remained unchanged. Receipts show
zero new model/MORK/NARS/ECAN/token-counter work. These are endpoint lifecycle
checks, not new inference or GUI integration. The full suite ran 220 tests:
219 passed, one optional native fixture skipped.
