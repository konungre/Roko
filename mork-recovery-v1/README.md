# mork-recovery-v1

Authored MORK audit, bounded fact adapter derivative, process cleanup tests,
durable evidence/history, and an Omega request-preparation bridge. 66 authored
checks passed in the initial checkpoint. A separate private native rebuild now
passes ten real query/integration probes; the current authored suite passes 69
checks. The subsequent bounded PeTTa/Omega/Granite host integration passes real
restart/recall and cancellation probes; it is not a production or autonomous
system qualification.
Upstream/private source and native runtime are excluded.

See [conversation integration](CONVERSATION_INTEGRATION.md) for the new host
interface, limits, exact verification scope, and remaining runtime blockers.
See [native rebuild](NATIVE_REBUILD.md) for the candidate's exact identity,
explicit host-selection API, and compatibility/security limitations.
See [live durable conversation](../components/conversation/DURABLE_MORK.md)
for the actual host integration and its separate runtime receipts.

See the repository-level docs for current status, external dependencies and publication limitations. Development-root paths may be public placeholders. These sources are not a self-contained runtime.
