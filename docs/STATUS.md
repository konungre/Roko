# Current component status

This publication was prepared on 2026-11-09. It separates actual recorded runtime
gates from source-only preparation. Native checks were not rerun for publication.

This document describes project status across the preserved local work. It is not an assertion that every referenced directory is included in the first public tree; consult PUBLICATION_MANIFEST.json.

## Desktop and controller

- The delivered showcase source is `omega-baseline/desktop/live-request-media`,
  `omega-baseline/boot/showcase-guest-v4`, and `roko-showcase-stage-v4`. It contains
  the real bounded request/controller path and delivered animation source plan.
- StateStore, WorkingState, CLI, explicit proposal/checking, and avatar-event
  code are in `omega-baseline`. Historical desktop/persistence milestones are
  recorded in its documentation, with their original scope limitations.
- `roko-head-app-bound-v2` is an experimental head-input route, not a claim of a
  new delivered complete desktop. Its private artifact binding is redacted.
- `production-unprivileged-cleanup-034` and `production-unprivileged-runtime-038`
  are experimental diagnostics and host-runner sources. An earlier 031 relaunch
  cleanup gate failed. These sources are not a delivered/proven complete
  unprivileged runtime; one private admission reference is redacted.

## AI integration

- **PeTTa and Omega:** existing source pins are preserved. `symbolic-ai-v4`
  observed 7 ECAN checks and 2 literal Omega checks in isolated host processes.
  This was a narrow symbolic gate, not unrestricted Omega execution.
- **Granite plus symbolic context:** `symbolic-granite-v7` observed 2 ECAN,
  4 Omega and 2 actual Granite checks, retaining mandatory source facts through
  exact checkers and state revision checks. External actions remained zero.
- **Live symbolic context:** `live-symbolic-context-v5` is default-off,
  source-reviewed preparation, not guest-native qualification. Its recorded
  source checks were 99 pure tests, 2 regressions and 8 independent tests.
- **MeTTa-NARS:** `nars-inference-v3` exercised the pinned original NAL-1 subset
  on PeTTa: four cases, eight actual native result rows. Recorded source checks
  were 46 owner and 10 independent tests. This is not full NARS, Omega-controller
  integration, or guest integration.
- **MetaMo:** `metamo-core-v4` passed one separately reviewed host gate: eight
  fresh processes, eight scoring/selection cases, 21 actual scores and 128
  helper/consumer checks. v3 failed before scoring because of helper import
  order; that failure remains preserved. Five upstream modules remain exact-pin
  external sources, with seven authored numeric compatibility helpers. The new
  `metamo-controller-adapter-v2` has 53 pure tests and awaits its separate native
  controller gate. No full MetaMo state cycle or guest integration is claimed.
- **NACE:** `components/nace` contains seven byte-preserved MIT-licensed function
  blocks and a bounded predictive adaptation adapter. The source checkpoint
  passed 70 pure tests. The portable copy has 70 passing tests and two explicit
  full-upstream provenance skips. No upstream runtime, planner, ONA/eval bridge,
  environment action, full NACE cycle or guest integration has run.
- **MORK:** `mork-recovery-v1` restores source provenance and hardens the existing
  bounded fact adapter. 46 current pure/authored-helper tests pass. The real
  read/write/match/remove/rewrite/error fixture is authored but not run. Native
  libraries, the historical Cargo lock, toolchain/registry closure and complete
  runtime admission remain missing. Historical native pass statements elsewhere
  are not current MORK qualification.
- **MeTTa-Motto, MOSES, AI-DSL and AIRIS:** requested components with
  research/source mapping underway; no complete native/controller integration
  is claimed by this publication.
- **PRIMUS, Predictive and Causal Coding, and TransWeave:** architectural goals
  and mapped design references, not fully implemented or validated architectures.

All native numbers above are narrow prior observations on specific pinned builds.
None establishes general reasoning accuracy, scalable performance, safety against
arbitrary inputs, cross-host portability, or production readiness.
