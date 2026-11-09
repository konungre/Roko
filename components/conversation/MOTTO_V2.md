# Optional native MeTTa-Motto transport in durable v2

A qualified `motto_transport` profile wraps the existing FreshProvider's chat
callback. Actual Omega dispatch goes through a fresh supervised Hyperon process
running the attributed upstream Motto Agent. It emits a typed model request;
the parent independently compares every message and the snapshot digest before
calling the existing real Granite provider. The child converts that actual
response through upstream Motto and the parent requires exact output equality.
Generation metadata, CAS, complete history and truncated-output semantics remain
owned by the existing durable implementation. Replayed requests skip transport
and model execution.

The transport requires a claimed v2 session/request/revision matching the complete
history. A private start record is fsynced before execution. Receipts contain
binding, raw protocol bytes, finalization errors and status. The existing
subreaper binds the transport to its parent's lifetime, with a 210-second bound;
the model retains its own independent supervision. Network denial is inherited
from the conversation worker. Cleanup attempts are independent, preserve the
original exception and fail closed. A receipt-write failure retains in-memory
and attached evidence but cannot guarantee disk persistence.

`qualify_motto.py` extends a freshly qualified conversation profile with the
exact adapter sources and a verified Hyperon closure. It reuses the NARS runtime
manifest as an inventory guard only: transport execution does not claim to run
NARS inference. Runtime paths must be qualified on each consumer host. The native
probe separately verifies actual transport/model behavior; preparing a profile
does not establish success.

Run `tests/probe_motto_native.py --profile PROFILE --output NEW_DIRECTORY` for
real multi-turn conversation, native recall, a normalization failure with no
model invocation or commit, recovery at the unchanged revision, and restart
replay. Process-double tests separately inject protocol and cleanup failures.

Scope remains text-only: no tools, arbitrary MeTTa scripts, event agents, remote
Motto providers, external actions or guest qualification. Literal backslash-n
input is rejected because upstream Motto normalizes it; actual newline content
is preserved. Model prose remains unverified. This transport adds no persistent
learning state. The standalone smoke experiment and its evidence remain under
`components/motto_conversation`; v2 qualification supersedes only its earlier
integration-status limitation.

## Stack reconciliation

The cognitive branch merged main at d92a26e without rewriting history. Main's
unified v2, MORK, resource diagnostics and guest changes are preserved. The only
merge conflict was additive DURABLE_API documentation; both sections survive.
The resulting source diff against main adds bounded learning tasks and Motto,
not an alternative v1 implementation. Old PR4 language/parser code is already
present in main's unified implementation. PR6 is the cumulative component branch
and should be independently reviewed against main; parent can retarget it and
close superseded stack entries. No agent merge or force-push is required.
