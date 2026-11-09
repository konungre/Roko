# Client guidance for durable conversation failures

`client_diagnostics.describe_error(response)` accepts a v2 error packet and
returns bounded local guidance. `describe_transport_failure()` handles delivery
loss where the commit outcome is unknown. Neither function sends requests,
creates request IDs, retries, recovers, changes state or treats returned text as
commands. This module is not wired into the graphical client or server response.

Delivery loss calls for a snapshot followed by the exact original request,
including its original `request_id`, `expected_revision` and payload. Updating
the revision from the snapshot prevents saved replay and produces a conflict.
Pending/busy guidance requires server-verified owner death before explicit
recovery. Native/resource/terminal failures require review before a new request.
A full session explicitly requires a new session; existing history is retained.
Unknown codes and remote details never become displayed guidance or commands.

All eight diagnostics tests pass, including real SQLite verification of original
revision replay versus changed-revision conflict. Eight local end-to-end checks
passed for deliberate response loss after real generation: the turn committed,
the response was discarded, and exact replay after restart recovered it with
zero native work and unchanged database contents. This is a controlled local
simulation, not independent reproduction. See `LOST_DELIVERY_NATIVE_SUMMARY.json`.
