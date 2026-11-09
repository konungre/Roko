# Experimental native input-budget contract

Existing profiles and the default C++ build retain a512-token input limit.
The1,024-token context allocation and128-token maximum output allowance remain
unchanged. A separately built768-input runner is experimental and requires an
explicit trusted profile capability. No generated profile or binary is activated
by this change. The sixteen-message/eight-exchange MORK ceiling is separate.

A trusted administrator profile may contain:

```json
"native_budget": {
  "kind": "roko-native-budget-v1",
  "input_tokens": 768,
  "context_tokens": 1024,
  "max_output_tokens": 128
}
```

Only exact typed512/1024/128 and768/1024/128 contracts are admitted. Booleans,
unknown fields and unsupported tuples reject. The executable/model remain pinned
in the profile's files closure. An explicit contract requires the pinned runner's
`--capabilities` JSON to match exactly. The probe runs under bounded native
supervision before the durable store opens; malformed/mismatched receipts and
legacy binaries without this command reject. Absent contracts preserve legacy
runners without requiring a new command. Generation receipts still enforce512
for those profiles.

The default build needs no special flag. A separately reviewed experimental build
can add `-DROKO_INPUT_TOKEN_LIMIT=768` to the existing compiler invocation. The
source's shared constants drive both capabilities and actual admission/allocation;
unsupported compile-time values fail static assertions. No native dependency,
model, memory ceiling, network policy or deadline is changed. Do not replace a
qualified executable or modify a pinned profile in place; retain recovery copies
and requalify the complete external closure before activating any new profile.

FreshProvider uses the admitted contract for native generation validation and
exact-token context planning/provenance. `op: limits` reports its input limit.
The default complete-context policy remains complete and fails if over budget.
Lossy `extractive_v1` still requires explicit request opt-in and profile capability,
reports omissions, and never changes authoritative history. A larger budget does
not imply arbitrary prompts, unbounded history, fast responses or desktop fit.

## Reproducible load and recovery checks

Both probes require a qualified external768 profile and the verified synthetic
six-turn `language` database with12 messages/two observations/no pending claim.
They read the source database through SQLite read-only mode, use a fresh private
output directory, and retain raw requests/stdout/stderr and result JSON.

```sh
python3 -B components/conversation/tests/probe_budget_recovery.py \
  --profile /absolute/path/to/experimental-profile.json \
  --source-db /absolute/path/to/verified-six-turn/history.sqlite \
  --output /absolute/path/to/new-load-evidence
```

This opens two real endpoints against one copied DB. It checks pending/busy,
refuses live-owner recovery, explicitly cancels an owned endpoint during resident
native inference, verifies descendant cleanup, explicitly recovers the dead claim,
and submits a new ID. It then tests exact replay, two native turns in a second
session, reused IDs scoped by session and stale CAS. Successful inference is
serial; this is concurrent-client contention, not parallel model throughput.
Cancellation deliberately leaves a pending claim until explicit recovery.

```sh
python3 -B components/conversation/tests/probe_budget_resource_limit.py \
  --profile /absolute/path/to/experimental-profile.json \
  --source-db /absolute/path/to/verified-six-turn/history.sqlite \
  --output /absolute/path/to/new-resource-evidence
```

This copies the source tree into its fresh output, excluding Git metadata and
Python caches. Only that copy's RSS threshold is tightened from5GiB to3GiB and
its profile pins recomputed. It tests actual `resource_limit` propagation without
host exhaustion or relaxed caps, preserved history/ledger, terminal failed IDs,
and explicit new-ID retry under the unchanged normal5GiB supervisor. It does not
claim that the normal5GiB ceiling was reached.

## Evidence scope

Local cloud qualification includes actual Omega/PeTTa/Granite durable turns at531
and755 input tokens, refusal of full769-token context, visible opt-in projection,
full-history preservation and exact saved replay under a later legacy512 profile.
Separate earlier standalone tests exercised768+128 tokens, invalid limits and
supervisor cancellation/deadlines. Standalone timing/memory results are not a
production endpoint performance guarantee. The user’s actual desktop hardware
has not been qualified. See `NATIVE_BUDGET_SUMMARY.json` for exact source scopes.
