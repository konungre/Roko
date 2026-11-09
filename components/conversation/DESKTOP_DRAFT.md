# Desktop draft integration

DesktopDraft wraps the diagnostics adapter merged through PR #27.
No transport or GUI implementation is included. Seven local state tests passed;
these are not native inference tests or evidence of graphical client integration.

Keep editable draft state separate from the immutable captured turn. Only an
explicit Send callback calls begin(request, confirmed=True). Never clear input
on send, transport loss, replay, error, snapshot, recovery, or release. The caller
may implement a separate user-requested Clear control. New typing must never
change the captured request; replay returns exactly that original request.

Feed transport loss/errors to the controller and request a fresh snapshot via an
explicit user callback. Every loss/error invalidates earlier snapshot decisions.
Until a new valid matching snapshot arrives, offer only Inspect snapshot. Render
all text as plain text. Never execute model/server text or returned actions.

Recovery requires explicit confirmation plus owner_stopped=True; this is caller
intent, not proof. The backend still checks owner death and may return busy.
Proposal generation does not execute anything or clear pending state. A malformed
snapshot leaves the previous accepted transcript and draft intact but does not
satisfy a fresh-snapshot requirement.

After a snapshot without pending work, a user may explicitly review_and_release.
Release only unlocks draft editing/submission workflow; it does not prove whether
the old turn committed and does not clear its draft. Explain that a new ID after
an uncertain committed turn can submit the same semantic message twice. Reuse
exact original ID/payload for replay; use a new ID for a consciously new turn.
The desktop must create new-turn revision and identity from current reviewed
server state and must handle normal CAS conflicts. Never adjust replay revision.

The wrapper has no persistence across desktop process exit. The real client must
persist the complete immutable request before dispatch and keep drafts separately
if crash restoration is required. No crash-durability claim is made here.

Run: python3 -B -m unittest discover -s components/conversation/tests -p test_desktop_draft.py -v

Qualification on main dfdaa450: seven unit tests and eleven local real-endpoint
checks passed across three sessions. An exact replay returned the saved response,
a live owner refused recovery with busy, and an exited owner's claim recovered
as interrupted. Identical request IDs in distinct sessions stayed isolated; every
draft and all authoritative history remained unchanged. Three fresh endpoint
processes reported zero model, MORK, NARS, ECAN or token-counter work. This tests
real service replay/recovery, not new Granite inference or graphical integration.
The full suite passed 212 tests with one optional fixture skipped (213 run).
