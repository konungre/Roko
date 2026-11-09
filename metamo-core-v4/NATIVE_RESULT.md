# MetaMo MAGUS native subset: passed

The single reviewed v4 attempt passed eight fresh native processes and all eight
fixed scoring/selection cases. Each process executed 16 compatibility probes,
including the real upstream growth-signal consumer: 128 probe checks total.

The actual unmodified upstream MAGUS implementation produced all 21 scores and
selected all eight expected proposals. Independent Python acceptance checks
matched every score within 1e-9; no fallback or invented native output was used.

Passed cases:

- Original upstream score, best-candidate and curiosity/ethics conflict fixtures.
- Lower-risk preference and positive growth-shift preference.
- Stable first-candidate ties, including reversed input order.
- Maximum eight-candidate request.

Observed bounds and cleanup:

- Whole external command: 6.858223074 seconds, within the 90-second budget.
- Controller interval: 6.812241918 seconds.
- Maximum observed child RSS: 67,543,040 bytes.
- Minimum observed available host memory: 7,662,596,096 bytes.
- All eight children exited zero, were reaped through owned final cleanup, and
  had empty process groups afterward.
- Every child and the completed gate verified all pinned inputs unchanged.
- No model, VM, download, install, network operation or external action ran.

Native receipt SHA256:
`50555393a33955901a9d0c76f93b12a21c7dfcff5d6f4d8c4c4556c28c096d97`

Source manifest SHA256:
`f848eb8166947cb01b8fa4d2ef47b5d3f2a2ae7f7d510b86a4fcb2271e65d05b`

Upstream: `iCog-Labs-Dev/MetaMo` at
`bf97e50a68aa5059457092dfbe70699b7dd1dbe2`, MIT. The five upstream modules remain
byte-identical. The seven numeric helpers are explicitly authored compatibility
code using pure MeTTa/PeTTa arithmetic over a finite six-decimal input domain.

The earlier v3 attempt failed once because its helper import order was
incompatible with PeTTa compilation. That failure remains preserved. v4 was a
separately reviewed and authorized successor, not a repaired old result.

This verifies bounded host MAGUS scoring and DecisionMonad proposal selection.
It does not implement or establish full MetaMo appraisal/dynamics/consensus state
cycles, persistent motivational updates, guest/live endpoint integration, broad
architecture equivalence, autonomous actions, or hostile-code containment.
