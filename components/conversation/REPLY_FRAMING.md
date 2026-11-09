# Receive-only reply byte adapter

`DesktopDraft.create_reply_receiver()` returns an attempt-bound `ReplyIngress`.
The caller supplies byte chunks obtained from a trusted pipe/socket and explicitly
signals EOF. The receiver opens no connection, sends no request, starts no timer,
and performs no retry, recovery, process execution or model call. It accepts
completed/truncated turn-reply packets only, not snapshot/error/control routing.

```python
receiver = controller.create_reply_receiver()  # after explicit begin(...)
chunk = trusted_socket.recv(65536)              # transport owned by caller
if chunk:
    receiver.feed(chunk)
else:
    receiver.eof()
```

Run all controller and receiver callbacks serially on the same event loop/thread.
They are not thread-safe. A socket-reader thread must marshal chunks to that loop;
the connection's origin/authentication and lifecycle remain the transport's job.
The receiver's `connection_authenticated` is always false: it authenticates
nothing. Never infer live computer or service state from successful framing.

`JsonLineFrames` buffers fragments until LF, then strictly decodes UTF-8. Multibyte
characters may span chunks. CRLF is accepted as JSON whitespace; CR counts toward
the body cap. Limits are 128 KiB per frame body, 64 KiB per input chunk, and 64
frames per chunk. Empty frames, invalid UTF-8, over-limit input, partial EOF, and
strict JSON/schema errors fail closed. No fragments are auto-completed. The
complete-frame callback rejects duplicate keys, nonfinite/overflowed numbers,
excessive nesting, mismatched request identity and changed saved replies.

Framing produces no backend actions. `ReplyIngress` only delivers complete frames
to the captured reply callback. Snapshot/error responses on a multiplexed service
need a separately correlated dispatcher (including existing snapshot tickets),
not this reply-only adapter. Generic `JsonLineFrames` can supply frames to such a
trusted dispatcher; model text must never choose a handler or backend operation.

The receiver is bound to the captured controller attempt by object identity.
After release/new begin, old frames and old EOF cannot update the new attempt,
even if external request IDs are reused. Exact saved repeats within the original
attempt remain idempotent. A clean or failed stream end invalidates snapshot
based decisions locally, with no automatic snapshot request. EOF after an accepted
packet reports that a whole reply packet arrived; it does not describe delivery
as incomplete. Truncated generated text remains labeled. EOF before a reply
retains unknown-delivery guidance. Accepted reply/history/draft remain intact.

A failed receiver is terminal; a new receiver/connection requires caller choice.
Framing failure can discard undelivered frames from the current chunk. If a later
callback fails, already accepted earlier frames remain accepted; there is no batch
rollback or promise of atomic multi-frame delivery. Inspect a fresh authoritative
snapshot before further request decisions. Neither diagnostics nor EOF prove
current service health or refreshed package evidence. A cancellation remains the
primary exception if the local loss callback also fails; diagnostic types record
the secondary failure without logging raw reply bytes. Loss notification occurs
at most once per receiver.

Validation uses real local AF_UNIX socket pairs. A fixture peer emits four saved
native response packets in fragments; the receiver writes no application bytes.
Tests cover UTF-8 splits, coalesced repeats, limits, bad controls, stale attempts,
EOF, preserved unsent input and cancellation cleanup. This is real local transport
execution with a fixture peer, not an authenticated Roko daemon, native inference,
Nix/Guix operation, graphical client or live-host measurement. Saved requests are
reconstructed from normalized database payload/identity, not original wire bytes.
The evidence DB is immutable/read-only and checked unchanged. Run:

```sh
python -B components/conversation/tests/probe_reply_socket_transport.py \
  --database CLOSED_NATIVE_HISTORY.sqlite --output NEW_DIRECTORY
```
