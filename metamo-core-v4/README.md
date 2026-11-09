# Roko MetaMo MAGUS core integration

This derivative prepares a real bounded integration of MetaMo's MAGUS candidate
scoring and DecisionMonad selection code. It is not a replacement scoring mock.
Five upstream MeTTa files are byte-identical at MetaMo commit
`bf97e50a68aa5059457092dfbe70699b7dd1dbe2`; the MIT license is included.

## What is implemented

- A typed JSON boundary admits eight goal values, six modulators and one to
  eight candidate proposals with bounded correlations, risk and proposed goal
  changes. Values must be finite, non-boolean and have at most six decimals.
- Original MAGUS decision source calculates goal/modulator/meta-drive weighted
  scores, a risk penalty, curiosity/ethics conflict penalty and growth reward.
  Its native `magusDecide` chooses the proposal, retaining the first tied input.
- Native bridge callbacks record the actual scores, chosen symbol and proposed
  delta. Python never substitutes a native score or winner. The separate Python
  oracle is used only for independent acceptance checks in the qualification.
- Candidate IDs are inert data. Only generated symbols and validated numeric
  vectors enter fixed MeTTa expressions. Results are proposals only, with no
  state mutation, tools, commands, communications or external action authority.

## Explicit compatibility layer

`source/numeric_compat.metta` is authored Roko code, not upstream MetaMo. It
implements exactly seven helpers reachable from MAGUS scoring: absNumber,
expNum, sigmoidNum, positivePart, scaleArray, clipVector and meanAtIndices.
They use pure MeTTa and existing PeTTa arithmetic rather than importing the
upstream NumPy/Gemini application dependency chain. scaleArray preserves
upstream eight-place rounding. The six-place input domain excludes rounding
half-tie discrepancies. Empty indexed mean is zero. Norm and variance are not
reachable and are not implemented or claimed tested.

Upstream `core/helpers.py` and tests are retained only as review references,
never imported or executed. No requirements were installed.

## Current evidence

73 pure/contract/provenance/controller tests passed. This includes an independent
comparison of the seven mathematical operations against existing trusted host
NumPy for 100 bounded samples. It does not establish native MeTTa compatibility.

The proposed native gate has eight fresh processes covering three original
upstream test scenarios, risk preference, growth preference, tie order and
eight-candidate capacity. Each process must pass 16 native helper/consumer probes and
produce its own runtime-map/import evidence. A failure is preserved, never
replaced by oracle output or silently retried. Native execution requires exact
source review and a coordinator grant. See `proof/native-proposal.json`.

## Bounds and limitations

The existing measured SWI 10.0.2 / Janus / Python 3.12.14 and PeTTa closure is
referenced without installation or large copies. Caps are 90 seconds overall,
20 seconds per child, 256 MiB observed RSS, 512 MiB address space, bounded
streams and files, and 4 GiB free disk after worst-case writes. Child sockets
are denied. Owned-process cleanup retains identity until the final group
signal and reap. This is not a hostile filesystem sandbox.

No full MetaMo appraisal/damping/projection/consensus state cycle is integrated
here, and no guest, model, PRIMUS or live endpoint claim is made. Original
baseline, ISO and previous checkpoints remain unchanged.

## Revision 2

The host launcher executable is pinned and checked before spawn; the child
launcher uses isolated mode. Temporary-directory cleanup failures retain the
completed child receipt and original cancellation exception. Four mock
regressions cover these paths. The host controller standard library is not
fully pinned. Revision 1 was preserved and never executed.

## Revision 3

The host MemAvailable reserve is 4 GiB at admission and during the worker.
This is separate from the child 512 MiB address-space cap. Revision 2 was
preserved and never executed; the host reserve is not relaxed for this gate.

## Revision 4

Revision 3 failed its first real child with a positivePart arithmetic type error.
It was not retried. PeTTa compilation resolves known functions when each file
is imported; v4 therefore imports numeric dependencies before upstream code.
An extra native probe calls the actual upstream growth-signal consumer, and
bounded stage indices identify future failing expressions.73 pure tests pass;
new native success is not yet established. See proof/compatibility-diagnosis.md.
