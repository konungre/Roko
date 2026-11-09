# Durable evidence boundary checkpoint

This increment adds SQLite durability around the existing native-only bounded
MORK query adapter. SQLite stores evidence; it is not a MORK implementation.
No conversational loop has been connected or qualified in this checkpoint.

## Interface for the parent integration

Import `DurableMemory` from `source/durable_memory.py` with this source directory
on the trusted host's module path. The host owns a private database path and
session identity. Do not derive a path or session authority from model output.

- `remember(session, fact, source=..., turn=...)` admits an already-reviewed
  typed fact and returns a stable SHA-256 evidence ID. The source label is a
  caller assertion, not independently authenticated provenance. No prompt,
  generated rule, or transcript is automatically stored.
- `recall(session, query, timeout=3)` calls the existing native adapter, retaining
  its complete fail-closed binary/runtime checks. It returns matching facts and
  their evidence IDs, source references, turn references, and admission times.
  Native errors propagate. The host must show memory as unavailable rather than
  inserting a Python lookup result into the conversation.
- `forget(session, id)` deletes only that session's record; `close()` releases
  the database. SQLite secure deletion is enabled, but backups and storage-device
  remnants are outside this API's erasure guarantee.

All results remain advisory and grant no execution authority. Session isolation
is a namespace boundary, not authentication. The host must enforce user access,
private directory permissions, retention consent, and deletion of backups. The
database is not encrypted by this module. There is no global session-count cap;
the host controls session creation and total storage policy.

At most 16 evidence records per session are admitted. Native request byte and
arity limits also apply, and a failed admission rolls back. Capacity exhaustion
is explicit; records are never silently evicted. Repeating an identical
session/fact/source/turn admission is idempotent. Concurrent admissions serialize
through SQLite's immediate transaction. Recall uses a single snapshot read;
concurrent deletion does not revoke evidence already returned to a caller.

## Verification and blockers (2026-11-09)

`python3 -B -m unittest discover -s mork-recovery-v1/tests -v` passed 52 checks,
including six new durability/contract checks. Test doubles are explicitly
identified and do not qualify native MORK. A direct native query failed with
`NativeMORKError: Optional native MORK runtime is unavailable; it is excluded
from distribution`. SWI-Prolog and Cargo were not found on PATH.

The requested transfer bundle `libfile_71ba79b00d108191a4c99d2270be4779` resolved
to `roko-publication-mork-checkpoint-v3.tar.gz`, version 1, 5,851,239 bytes.
The current Library helper failed to download it. A destination-host probe
returned `CONNECT tunnel failed, response 403` for
`sdmntprwestus.oaiusercontent.com`; that host is absent from the configured
allowlist. No bundle bytes were recovered or verified, and the Library item was
not modified. The cloud environment exposes no request-changes tool here.

Next steps require allowing the Library transfer destination, recovering and
verifying the existing bundle, reviewing its native dependency closure, and
coordinating the above interface with the parent PeTTa conversational-loop work.
Do not relax existing binary pins merely to run a newly built engine. Acquire
and qualify the correct runtime, then run genuine native retrieval through the
PeTTa loop before claiming integration success. No files were pushed.
