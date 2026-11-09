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

## Reconciled durable v2 integration

Published main commit `4225bb553f03f78bf3da9f0ae5ec6861d2388a53` contains the
conversation successor through `21e8621`. It was fetched through GitHub and
merged into the existing native-memory branch. The four conflicted conversation
files (`fresh.py`, `qualify_fresh.py`, `probe_durable.py`, `FRESH_HOST.md`) retain
the published main versions exactly. The current v2 implementation was not
replaced with the earlier v1 receipt/lease mechanism.

`durable_server.py` uses client-supplied request IDs, committed CAS claims,
atomic history/response commits and saved replay before any native execution.
Lost response delivery can replay the saved response value after restart.
Cancelled pending work requires explicit recovery after the original owner dies.
See `components/conversation/DURABLE_API.md`; no additional acknowledgment field
or incompatible transport was invented. The v1 `fresh_server.py` stays separate.

The optional native replay regression combines real MORK and real SQLite with
an explicitly labeled provider double. It commits a response, discards delivery,
reopens the store, verifies exact replay without native retrieval or generation,
rejects changed payload reuse, then retrieves two committed messages with real
MORK for the next claimed request. It is not new Omega/Granite model evidence.

Historical v1 storage/lease utilities and tests remain available for recovery;
the reconciled current launcher does not select them. The original working
checkout and profile 002 remain untouched. The earlier Library 401 was neither
retried nor bypassed. Source availability through the published repository
resolved the v2 contract-access blocker.

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

Reconciliation validation: 121 conversation tests ran with 120 passing and one
optional real-ECAN skip. This includes four real native MORK calls across the
v2 adapter and SQLite replay tests. All 73 memory/helper tests passed, including
20 additional real native calls. No new full PeTTa/Omega/Granite qualification
was performed on this merged checkout, and no CI run is claimed. The independent
PathMap reproducer and observed failure are in `probes/pathmap-fork`.
