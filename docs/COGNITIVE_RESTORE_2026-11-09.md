# Cognitive integration restoration

Restored the four commits ending at `78a5a74943093a1af82c1d8e0fa7a0a408b8d5f4`
from the private transfer onto repository checkpoint `7548663`. The merge retains
the newer artwork attribution as well as the NACE and AIRIS license notices.
No push, native worker, model, or external action was executed.

The transferred archive SHA-256 is
`c7ddb780b1c72297d407356793a1b6b3f354f0760fc2028222b933c7f1f8569d`.
Library metadata was applied and verified by the current Library transfer helper.
Git verified the incremental bundle against prerequisite `7fbcb5f`.

## Fresh validation

Run from the repository root with Python 3:
`python3 -B -m unittest discover -s <directory> -p 'test_*.py'`.

| Directory | Passed | Explicit missing-upstream skips |
| --- | ---: | ---: |
| components/omega_learning | 36 | 0 |
| components/nace/source | 70 | 2 |
| components/airis/source | 83 | 1 |
| metamo-core-v4/source | 69 | 4 |
| metamo-controller-adapter-v2/source | 53 | 0 |

Total: 311 passed, 7 skipped, zero failures. These are source/contract tests,
not observations of native cognitive integration.

## Integration boundary for the conversation owner

Import from `components.omega_learning.metamo_turn`:

```python
plan = prepare_conversation(snapshot, candidates, motivation)
advice = score_conversation(
    plan,
    run=trusted_gateway,
    current_snapshot_sha256=current_full_snapshot_digest,
    binding=RuntimeBinding(runtime_workspace),
)
```

The complete snapshot and candidate schemas are in
`components/omega_learning/README.md`. The gateway must return the actual
response and receipt. There is no synthetic fallback. Advice carries exact
candidate text and unverified ranking; it grants no action or truth authority.

This checkout does not contain `live-system/omega-chat`, the conversation
owner's current selection API, or the admitted native runtime closure. A combined
turn cannot yet be wired and validated here. Transfer the owner's current source
and coordinate that API before modifying their turn loop.

## Cleanup issue remains open

Inspection confirmed the same receipt-loss pattern described in the prior NACE
review also exists in the restored MetaMo v4 and AIRIS gateways: exceptions from
`selector.close()` or stream finalization can escape before receipt construction;
a stream close exception can also prevent saved signal handlers being restored.
The existing historical native successes do not test this fault path.

Do not replay a historical admission against changed code. A successor gateway
needs independently recorded finalization failures, unconditional attempts to
restore all handlers, retained raw child/cleanup evidence, and fault-injection
tests before a new bounded native gate. The frozen source and historical records
are preserved unchanged here.

ECAN, MeTTa-Motto, MeTTa-NARS, NACE, MOSES, AI-DSL, AIRIS, PRIMUS,
Predictive and Causal Coding, and TransWeave are not established as combined
Omega conversation functionality by this restoration.
