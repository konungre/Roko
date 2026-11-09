# Bounded conversation capacity qualification

The validated MORK profile supports eight complete exchanges (sixteen messages).
This is a storage/admission ceiling, not unlimited conversation or a guarantee
that any eight exchanges fit the model. Native input remains limited to 512
tokens; a request can reach that budget earlier. `op: limits` reports remaining
history capacity but does not reserve it or count a future prompt.

When over budget, the default `context_policy: complete` fails with
`context_limit` rather than
silently dropping context. A user may explicitly choose `extractive_v1` when the
profile enables it. That lossy model-context projection reports omissions and
source hashes while preserving complete authoritative history. It does not raise
the sixteen-message ceiling. A ninth exchange fails with `history_limit`.
Failed request IDs remain terminal; successful IDs replay only their original
payload/revision. Repeating a failed ID never automatically reruns inference.

## Reproduce locally

Use a qualified external runtime profile and the verified synthetic six-exchange
`language` database with twelve messages and two cognitive observations. The probe
reads this source through SQLite read-only mode, copies it into a fresh output
directory, and compares source logical state afterward. It refuses an existing
output directory. It resumes six exchanges for two new native generations; it
does not claim eight exchanges generated from an empty database in this run.

```sh
python3 -B components/conversation/tests/probe_eight_turn_capacity.py \
  --profile /absolute/path/to/qualified-profile.json \
  --source-db /absolute/path/to/six-turn/history.sqlite \
  --output /absolute/path/to/new-capacity-evidence
```

The probe runs default budget refusal, explicit opt-in exchanges seven/eight,
a default request after opt-in, capacity inspection, ninth-exchange refusal,
exact replay and a fresh endpoint restart. It saves raw requests/stdout/stderr,
return codes and logical before/after database state. It invokes the actual
local endpoint and model, and may take several minutes. No model download or
runtime replacement is performed. Preserve the original database for recovery.

Audit captured evidence without running a model or opening any database:

```sh
python3 -B components/conversation/tests/probe_eight_turn_capacity.py \
  --audit-only --output /absolute/path/to/capacity-evidence
```

Audit-only writes `audit-result.json`, preserving the producer's `result.json`.
Checks include exact new message pairs, model-context history hashes, native
successful generation receipts, token counts, complete stored transcript and
cognitive ledger, terminal failures, replay identity and zero-work restart.
Captured evidence is local producer evidence; an audit is not independent native
reproduction. The reproducible scripts and summaries do not contain model weights
or binaries. No graphical desktop integration is claimed.

## Local qualification

On merged main `70c57dba`, the probe and audit passed 33 checks. New native
exchanges seven/eight used 508/504 input tokens and both recalled red foxes and
robins. A tampered restart reply was rejected by the audit. The full suite ran
223 tests: 222 passed and one optional native fixture skipped. See
`EIGHT_TURN_CAPACITY_SUMMARY.json` for the qualified limits and provenance.

Audit hardening also verifies the exact restart request sequence and exactly
four native attempts in order (rejected, generated, rejected, generated). Captured
fixture tests reject a changed restart revision and an extra unsuccessful native
attempt. Set `ROKO_CAPACITY_AUDIT_FIXTURE` to the captured evidence directory to
run `test_capacity_probe_audit.py`; these tests execute no native process.
