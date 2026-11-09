# Package receipt presentation

`package_reply_view.py` is an opt-in, read-only plain-text renderer for completed
or truncated v2 reply packets. It accepts one JSON response per input line:

```sh
python -B components/conversation/package_reply_view.py < saved-replies.jsonl
```

This is a working CLI and reusable `render_reply(response)` function. It is not
a graphical desktop integration or a change to the durable API. Existing
clients displaying only `text` will not gain this presentation automatically.
The service remains responsible for source/runtime qualification and trusted
transport. The renderer neither authenticates a producer nor rechecks files.

The fixed notice precedes the generated answer. It shows receipt availability,
recorded check time, unknown observation age, source revision and commit, snapshot
digest, and query receipt digest. The check timestamp is explicitly not the OS
observation time. Saved replay retains its historical check; rendering later
does not refresh it. Missing evidence does not imply missing packages. A
last-known record is labeled historical, separate from admitted source data.
Strict legacy receipts lack a check timestamp; the renderer does not invent one.
Replies without package metadata explicitly report that no receipt is attached.

All notices state that live host, running system, system activation and health
are not established and no mutation authority is granted. Incompatible reply
binding, malformed provenance, missing proof digests, unknown freshness schemas,
and positive authority flags produce a neutral notice without source claims.
This is conservative presentation, not a new authorization layer or independent
verification of the claimed digests.

Every generated-answer line is prefixed and labeled advisory. Terminal control
characters are escaped, and source labels use quoted JSON escapes. Generated
text cannot emit unprefixed receipt-notice lines or use terminal escapes to
rewrite the notice. The renderer does not detect or suppress arbitrary false
natural-language claims: a model can still say something unsupported inside its
clearly labeled answer. No semantic live-state guarantee is claimed.

The input response, authoritative transcript, model prompt, saved replay,
revision, and cognitive ledger remain unchanged. Presentation performs no
model/tokenizer/native calls and issues no requests or mutations.

`tests/probe_package_reply_view.py --native-result RESULT --output NEW_DIRECTORY`
checks the actual four saved native responses from the package-status probe,
including unavailable/restored receipts, historical provenance and expired
admission. It tests presenter execution against measured native packets, not a
new run of PeTTa/Omega/Motto/Granite. GUI wiring and genuine live OS observation
remain separate work.
