# Explicit desktop consumption of durable diagnostics

`DesktopDiagnostics(original_turn)` captures an immutable copy of the complete
original v2 request. It has no transport, process, retry loop or recovery executor.
The legacy `chat-bubble-v3` implementation was not found in this checkout, so
this framework-neutral adapter is not wired into the graphical client.

A desktop can call `transport_lost()` or `receive_error(packet)`, render `view()`
as plain text, and show controls from `available_actions`. Never dispatch those
actions automatically or from model/server-supplied text. User callbacks may
call `request_for_user_action(action, confirmed=True)` and send the resulting
packet through the desktop-owned transport. The confirmation flag is a caller
assertion, not an authentication token or proof of owner death.

Inspecting a matching snapshot precedes replay/recovery. Snapshots retain every
message, preserve plain-text content, and are rejected if stale, rewritten,
malformed or from another session. Unrelated request errors cannot replace
current guidance. Replay returns the exact original request, including its
original expected revision even when the snapshot is newer.

A matching pending snapshot after transport loss offers explicit recovery rather
than a dead end. Preparing that proposal also requires `owner_stopped=True` and
the original pending ID/revision; another request's claim is refused. The server
still verifies owner death and may return `busy`. The adapter neither kills nor
waits for a worker and does not assume the confirmation establishes death.

Eleven adapter tests and a local eleven-check headless backend test passed. The
backend replay returned the saved response, retained all fourteen messages and
both observations, and refused recovery while its original owner remained live.
No model/retrieval call occurred. The full suite ran 204 tests: 203 passed, one
optional native fixture skipped. This is local backend evidence, not a graphical
UI test or independent reproduction. See `DESKTOP_DIAGNOSTICS_SUMMARY.json`.
