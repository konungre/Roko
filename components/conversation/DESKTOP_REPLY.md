# Candidate desktop reply contract

`DesktopDraft.receive_reply(packet)` connects the read-only receipt renderer to
the existing framework-neutral desktop draft contract. This is executable Python
callback/state behavior, not graphical desktop integration. No inaccessible GUI
source, transport, model process, live-host API or package mutation is used.

The callback accepts a completed or truncated v2 reply only when its session,
request, and resulting revision match the immutable captured turn. The envelope
must report zero actions. Input is detached before validation and bounded to
128 KiB. Repeating the same saved packet is idempotent, including JSON key order;
a changed packet for the same captured request is rejected without rewriting the
accepted reply. Core mismatch, nonfinite input, or invalid text leaves previous
state untouched. Malformed receipt metadata within an otherwise matching reply
produces the renderer's neutral provenance notice.

The candidate view adds `active.reply`:

| Field | Meaning |
| --- | --- |
| `display_text` | Plain-text receipt notice and prefixed advisory answer; never markup or executable content. |
| `reply_revision`, `session_id`, `request_id` | Identity of this service-reported saved reply, not a live-state claim. |
| `history_relation` | `snapshot_unavailable`, `snapshot_behind_reply`, `matching_snapshot_turn`, or `conflicting_snapshot_turn`. |
| `source_check_refreshed` | Always false: rendering or receiving a replay does not recheck the receipt. |
| `live_host_state_established`, `mutation_authority` | Always false. |
| `render_as_plain_text`, `automatic_requests` | Always true and false respectively. |

Display the receipt notice as distinct from generated prose. Preserve the check
timestamp's as-of meaning, unknown observation age, and historical last-known
labels. Do not relabel service-reported digests as authenticated provenance or
mark the computer healthy because a reply exists. With absent evidence, explicitly
show that no receipt is attached. With invalid metadata, show uncertainty. Every
model line remains advisory and prefixed, including unsupported live-host claims.
The renderer does not detect or suppress arbitrary false natural language.

Receiving a reply does not insert it into authoritative snapshot history, change
the unsent draft, clear a snapshot requirement, release the captured request, or
establish an outcome. `history_relation` compares raw user/assistant strings at
the captured turn's position in an independently received snapshot. A match is
only transcript consistency; a conflict is diagnostic and does not rewrite either
record. Existing explicit snapshot/replay/recovery proposal rules remain unchanged;
the relation grants no additional action. After service loss, a cached reply or
repeat packet cannot satisfy the fresh-snapshot requirement.

A future GUI adapter can call:

```python
controller = DesktopDraft(visible_draft)
request = controller.begin(captured_v2_turn, confirmed=True)
# The existing trusted transport owns dispatch and response decoding.
controller.receive_reply(decoded_v2_reply)
view = controller.view()
# Render view['active']['reply']['display_text'] as plain text.
```

This example dispatches nothing. The real adapter must preserve the existing
explicit-send, draft, snapshot, replay identity, and stopped-owner requirements.
Release requires the existing user review and snapshot conditions and discards
only the active presentation, preserving the editable draft. No crash persistence
or source subscription is added.

Validation includes ten local contract tests and a read-only evidence probe over
four actual saved native replies plus their committed histories. Requests are
reconstructed from stored identity and normalized payload, not claimed to be
original wire bytes. The evidence database is opened immutable/read-only, checked
for a nonempty WAL, and hashed before and after. No service/native/model runtime
or graphical UI is executed by that probe. Run:

```sh
python -B components/conversation/tests/probe_desktop_reply.py \
  --database CLOSED_NATIVE_HISTORY.sqlite --output NEW_DIRECTORY
```

## Local provenance disclosure candidate

The follow-on contract adds `active.reply.provenance` and
`DesktopDraft.set_provenance_details_visible(visible)`. A future adapter may bind
a local Show details/Hide details control to that boolean callback. It is a
read-only local interaction, not a server request or an authorization dialog.
Before a reply is captured, the callback rejects without changing state.

Always display `provenance.summary_text` and `provenance.answer_text` as plain
text. The summary retains the receipt status, as-of check, imported or historical
source identity, unknown observation age, and fixed no-live-host/no-mutation
limits. Collapsing hides only the source commit and digest detail lines.
`details_text` is null when collapsed and contains the fixed full receipt notice
when expanded. Show it in addition to the persistent summary, not in place of it.
`answer_text` remains separately labeled and prefixed advisory model prose.

`available_local_controls` is generated by the controller (`show_details` or
`hide_details`), never copied from model text or response metadata. Do not send
those names to the backend. The callback neither reads receipt files nor refreshes
a source, proposes a retry, clears draft/snapshot state, or grants authority.
Absent or malformed metadata can only reveal the same neutral uncertainty notice;
it cannot reveal raw unvalidated source claims. A replay preserves the user's
local disclosure choice and recorded check. Release discards that choice; the
next attempt starts collapsed. No cross-process persistence is added.

The existing full `display_text` remains unchanged for compatibility. Consumers
using only that field will continue to show the full notice; they do not gain a
collapse interaction automatically. This candidate supplies state and callbacks,
not a real graphical widget. Model prose can still be false inside its advisory
section; disclosure is not semantic validation or producer authentication.

`tests/probe_desktop_provenance.py` exercises expand/collapse and service-loss
behavior on four actual saved native packets using an immutable/read-only evidence
database. It proves local dataflow and unchanged database bytes, not GUI behavior,
a fresh model run, a live receipt refresh, or live computer state.

## Complete-frame callback and incomplete evidence

A future trusted transport can pass one bounded UTF-8-decoded JSON reply frame to
`DesktopDraft.receive_reply_line(text)` instead of supplying an already-decoded
object. This local callback uses the presenter's strict parser: duplicate keys,
nonfinite constants or exponent overflow, oversized frames, excessive nesting,
partial frames, and concatenated reply objects are rejected before accepted
state changes. It does not frame a stream, buffer fragments, decode bytes, open
a connection, or retry anything. The transport still owns byte limits, strict
UTF-8 decoding, frame boundaries, origin/authentication and exception handling.
An exception preserves the old captured reply and local disclosure choice; it
does not imply a new source check or current evidence.

An incomplete receipt in a valid matching envelope may be accepted only as an
uncertain saved reply. Opening details cannot invent missing machine identity,
clock policy, query proof or producer flags. A corrected packet for that same
saved request identity is rejected as a conflicting replacement. To obtain a
consciously new response, the existing user-review/release and new-turn identity
workflow still applies. No metadata is silently repaired and no automatic new
request is generated. Legacy strict receipts retain unknown check time; showing
details does not synthesize a timestamp.

Regression tests exercise missing evidence fields, ambiguous frames, changed
same-identity packets, preserved expanded state after errors or bad snapshots,
and explicit release/new identity. Instrumented local disclosure fails on any
file read, process launch, socket creation or request proposal. The evidence
probe's `--frame-input` mode uses four real saved packets plus clearly marked
synthetic bad frames; it is not a new GUI, transport, model, or live-host run.
