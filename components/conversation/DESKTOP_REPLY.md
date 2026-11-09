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
