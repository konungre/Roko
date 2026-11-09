# Coordination: qualified host endpoint

Use `recovered_server.py`, not the baseline-layout `run.py`, with the existing
chat-bubble-v3 transport. The response retains its exact three-field schema.
The process owns one session and accepts multiple JSON request lines. Model text
remains unverified. No installation, VM change, autostart activation or push occurred.

On the current cloud workspace:

```
export ROKO_WORKSPACE_ROOT=/workspace/scratch/3e1051aa80ac
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -u -B \
  /workspace/scratch/3e1051aa80ac/roko-worktrees/ai-openai/components/conversation/recovered_server.py
```

Desktop arguments:

```
--conversation-python /opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12
--conversation-runner /workspace/scratch/3e1051aa80ac/roko-worktrees/ai-openai/components/conversation/recovered_server.py
```

Inherit `ROKO_WORKSPACE_ROOT` in the desktop environment. The wrapper supplies the
matched runtime internally, including explicit Python for the native supervisor;
it does not assume that embedded Janus `sys.executable` is a Python interpreter.

Actual headless desktop transport proof is retained locally at
`conversation-native-recovery-004/desktop-transport-v2.json`: two replies, no
transport errors, and correct lighthouse recall. Its predecessor failed because
a parent-death signal followed a short-lived desktop thread. That evidence remains
preserved; the successor watches the parent process identity instead.

Native proofs:
- `conversation-native-recovery-002`: two actual Omega/Granite turns with memory.
- `conversation-native-recovery-003`: native ECAN plus actual Granite conversation.
- `conversation-native-recovery-004`: native ECAN chooses four of five records;
  code-like user text stays text. The reply hits the 64-token cap and is incomplete.
- `conversation-native-recovery-001`: preserved import-order failure, zero model calls.

Source lineage: unchanged external Omega loop hash
`4245a23036c434bde33946169fbe71bff0b9cef955476f104f0399c3ce6655d6`, recorded lineage
commit `21d8634b57deb45df3d5bcbb144cf4b314793f14`; source trees are restored files,
not a freshly verified upstream Git checkout. The matched symbolic input manifest
SHA is `541e3c06a8159240a7f88c03f073f3a76f7f9afd54aa7e627dd5e40819f56ac0`.
All 29 reused host-profile source files were separately hash-checked against their
saved receipt, with no mismatches. Model/native assets remain at original paths.

Live-system owner: this is host-only and uses external development closures. Do
not substitute it into guest launchers without a new qualified runtime binding.
Desktop owner: the 180-second per-turn budget contains observed generic-host turns;
long output remains limited to 64 tokens. Keep explicit unavailable/new-session
behavior. Four exchanges maximum; no persistence or silent truncation.
MORK/learning owners: session history and optional symbolic records are integration
points, not claims that durable memory or learned policy is already wired.

The older HANDOFF.md proposal for versioned request IDs/revisions/CAS is still a
future product contract. This endpoint intentionally matches the currently authored
bubble transport; do not label its in-memory commit durable or exactly-once.

Cancellation evidence: `conversation-native-recovery-004/desktop-cancellation.json`.
Actual desktop cancel during active inference returned no answer, marked the session
ended, and observed an empty native process group afterward. Native supervisor and
inference PIDs were observed before cancelling. This is a tested case, not a claim
of rollback or complete fault coverage.
