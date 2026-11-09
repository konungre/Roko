# Native durable-memory component review

Review branch: `codex/native-durable-memory`. Parent performs independent review
and merge. The branch includes the recovered conversation ancestor
`55bebd8d79454c765b258b27471ad54a971700e5`; the memory integration is a separate
commit on top. Do not replace a newer conversation component wholesale.

## Evidence

The actual PeTTa/Omega/Granite run used native MORK-selected SQLite history across
two worker launches. The second response recalled “lighthouse”; four committed
messages survived restart. Cancelling a third native inference produced no
answer, no committed rows and no surviving native process group. An EOF restart
discarded the abandoned prepared request. No external actions were dispatched.
The v4 Library checkpoint `libfile_733cc5535858819186c15fd41a8dceb5` contains the
complete source/evidence handoff and private-build recipes/locks, excluding
weights, database contents, upstream runtime source and native binaries.

Additional qualification: 73 memory/helper tests passed, including four opt-in
real-native methods making 20 native calls. These cover all wildcard masks at
arities 1–3, relation/argument symbol aliasing, permutation/deduplication,
maximum-length symbols, absent/empty results, distinct provenance for duplicate
facts, session isolation and a stale receipt after another SQLite writer commits.
The reference equality check only verifies native answers; it never substitutes
an answer after native failure. Ordinary test runs skip these four methods unless
the operator explicitly supplies a reviewed runtime closure.

```sh
ROKO_NATIVE_MANIFEST=/absolute/reviewed/runtime-manifest.json \
ROKO_NATIVE_MANIFEST_SHA256=reviewed_digest \
python3 -m unittest discover -s mork-recovery-v1/tests -v
```

The actual run selected manifest SHA-256
`b480e3973455b2b6bedc903ec245b5cd0e7a8fd0e9b30a85a7a6329d54aef7d2`.
Existing profile 002 and its runtime were not rewritten for these tests.

## Integration contract and outstanding work

The storage interface is `prepare_exchange` followed by `accept_exchange` with
an opaque receipt token and expected history revision. Commit inserts both rows
atomically; the host owns an exclusive lease, and abandons staged receipts after
failure/restart. `ExternalMORKBackend` is the Janus-compatible subprocess boundary.
Keep the independent supervisor: embedded Janus owns C signal handlers that the
older direct Python supervisor cannot safely restore.

This branch still exposes the original `{text, context: []}` conversation
transport. It does not claim integration with the newer durable v2 transport.
The newer Library handoff was discovered, but the required download route remains
blocked by the previously reported HTTP 401; no alternate download route was used.
The published `basilisk/native-conversation-bubble` branch does not contain that
conversation API. The parent must supply its contract or publish its source
branch before interface reconciliation and a fresh end-to-end qualification.

Keep the following limitations in the PR and any release notes:

- Selected PathMap `5f2118c1d61d782a7590bac8874dcb3c94c1e0fb` predates a known
  zipper bug fix. These results qualify only the bounded fact adapter.
- SQLite provides durability; native MORK executes ephemeral typed queries.
- Source labels are caller assertions, not authenticated truth. Memory and
  model output never authorize actions.
- Four exchanges maximum in this conversation adapter; no silent history eviction.
- Local manifests bind reviewed bytes, not a portable release or a security audit.
- Missing upstream MORK license declarations remain unresolved. Upstream sources,
  binaries and model weights are not included in this review commit/checkpoint.
