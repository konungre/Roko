# MeTTa-Motto typed conversation transport

This experimental adapter runs the original MeTTa-Motto `Agent.__metta_call__`,
message interpretation and response conversion on actual Hyperon. It accepts
only typed system/user/assistant text messages and an explicitly supplied model
callback. It constructs ValueAtoms for content; it never parses user text as
MeTTa code. It rejects normalization before dispatch, including upstream's
conversion of literal backslash-n to a newline. Tools, scripts, event buses,
remote providers and non-text responses are outside this adapter's contract.

`upstream/agent.py` is byte-for-byte MIT source from zarqa-ai/metta-motto commit
`8a9225dee23780ad0be836161e1afcfadc75980a`. The original LICENSE is preserved;
`source-lock.json` records SHA-256, byte counts and Git blobs. The complete
Motto package is not imported: its optional cloud-provider dependencies are
not needed by this standalone upstream module. No modules are stubbed.

Run `python -B -m unittest discover -s components/motto_conversation` using a
Hyperon 0.2.10 environment. These tests execute actual upstream transport but
use clearly synthetic callbacks. `probe_granite.py` separately calls the real
FreshProvider through Motto and records native inference evidence. Run it under
the repository's no-network wrapper with a locally qualified fresh profile.

This is a bounded transport experiment, not yet wired into Omega or durable
v2. It does not establish full Motto, persistent state, tool execution, a
portable runtime admission, or guest integration. Before production wiring,
pin the Hyperon and adapter closure in the conversation profile and supervise
the transport worker with durable request identity and failure receipts.

Hyperon is initialized with configuration creation disabled. The first local
smoke attempt used default configuration and aborted on a read-only filesystem;
the explicit environment resolves this without changing host configuration.
