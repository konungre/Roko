# Native read-only awareness qualification

`qualify_awareness_hyperon.py` passed with native Hyperon 0.2.10 on this x86-64
host using CPython 3.12.14. This supersedes the earlier statement that native
Hyperon was unavailable for this interface; earlier fixture receipts remain
unchanged and correctly labelled. It does not qualify all Hyperon versions.

The dedicated workspace venv used the official PyPI CPython 3.12 manylinux
x86-64 wheel. Its SHA-256 matches both PyPI release metadata and the existing
`components/nars_hyperon` pin. See `evidence/awareness-hyperon-001/acquisition.json`.
No system installation, wheel vendoring, dependency installation or host
activation occurred. Reproduction requires a separately provisioned compatible
Python environment with `hyperon==0.2.10`, then:

```
/path/to/venv/bin/python distro/state/qualify_awareness_hyperon.py . /new/private/proof-directory
```

The explicit command uses two fresh worker processes and a private SQLite
checkpoint. It tests actual `MeTTa.parse_all`, native space `add_atom`,
`get_atoms`, pattern-query bindings and grounded-string values:

- Refresh installs facts from synthetic read-only backend observations.
- Removed packages disappear from the new space while the earlier space remains
  intact. Queries inspect facts directly; no MeTTa evaluator executes input text.
- Failed refresh preserves the current observation.
- A revision containing quotes, an apparent execution expression and a newline
  is one grounded string with its original value, not extra executable atoms.
- A delayed old observation finishes after a newer observation and is rejected,
  using real native spaces in the overlapping refreshes.
- Another process restores version 3 as explicitly historical, with no backend
  observation and no package action authority.

Use `Environment.custom_env(config_dir=None, create_config=False)` explicitly.
An exploratory default `MeTTa()` constructor attempted configuration initialization
on the read-only home and aborted in native code. The qualification command
therefore never uses that default. Initial harness corrections also replaced
Python `len(BindingsSet)` with the documented interface exposed by this installed
runtime, `BindingsSet.iterator()`. Failed scratch attempts were retained locally;
the committed successful receipt hashes the final qualifier source.

This is native interface evidence with **synthetic package observations**, not
live Nix state, an Omega owner subscription, a persistent native AtomSpace, a
COSMIC guest or a production runtime admission. The checkpoint holds snapshots;
native spaces are rebuilt after restart. Generic `Observation.live_hyperon_verified`
remains false: the generic adapter cannot attest arbitrary caller factories;
only this explicit external receipt establishes the tested runtime. Atom order
is not a contract; qualification locates the revision by its predicate.

The cooperative checkpoint concurrency and authority limits in
`AWARENESS_CONCURRENCY.md` still apply. Legacy bindings/defaults remain unchanged.
The old prototype provenance/licensing issue and the separate Hyperon bundled
library notice audit remain unresolved; this test grants no redistribution
clearance. PR #22 stays draft and the pending metadata approval is untouched.
