# Non-destructive baseline planner migration

Current dependency: package_bridge.py -> adapters/package_planning.py ->
components/omega-pm/omega_pm/core.py. The baseline component entered in7fbcb5f
and matches the user-supplied archive. No rights grant was identified; commit
attribution and the description 'authored source subset' do not establish one.
Exact matches/consumers are recorded in provenance/repository-prototype-audit.json.

An opt-in parallel path now exists:
package_bridge_v2.py -> adapters/package_planning_v2.py (Python stdlib only).
No omega_pm import, executable MeTTa parser or package mutation API is exposed.
The scalar plan_single helper preserves the read-only bridge helpers; reports
use schema2 explicitly. The legacy plan_source/SnapshotOnly classes are not
implemented by this successor. Those direct callers require explicit migration,
not an import alias that silently changes accepted syntax or plan identities.
This was not a formal clean-room process: the authoring agent had read old code.

Migration sequence for independent review:
1. Inventory external callers in addition to the tracked bridge/native fixture.
2. Have callers explicitly select package_bridge_v2 and schema2. Their desired
   package fact still goes through actual PeTTa matching; Python receives bounded
   scalar strings and a labelled historical snapshot. The report cannot authorize
   Nix or make a supplied snapshot become current observed state.
3. Run existing legacy tests and v2 native contract side by side. Compare operation
   counts, desired outputs, zero mutation and lack of authority. Keep both paths
   available until consumer acceptance; rollback is selecting the old bridge.
4. Only after consumer migration, remove the unresolved baseline component and its
   import path together, or establish a rights-holder license grant. Removing it
   now would break the active read-only native planner. History/backups remain a
   separate licensing decision; no rewrite is proposed here.

Validation: eleven state/successor tests pass. Real PeTTa/Janus probe passed
fixture match, operation count1, exact desired path and false authorization.
The runtime used explicit PYTHONPATH for the integration module. Failed import
attempts and successful raw output are preserved under evidence/baseline-successor-001.
The legacy bridge/adapter/component are unchanged. This does not establish source
licensing clearance, live Nix observation by this bridge, or guest integration.

## Side-by-side migration parity gate

`qualify_planner_parity.py REPOSITORY NEW_OUTPUT` runs each adapter in a separate
fresh Python subprocess using disposable labelled fixtures. Eleven cases passed
the active scalar helpers: desired package/path, count, membership, zero mutation,
no live observation and false authority. Cases cover empty/unchanged/replacement,
removal/mixed changes and rejection of invalid path/name, duplicate snapshot keys,
missing provenance and invalid observed output. Error classes differ and are not
part of the consumer contract. The first harness run failed to catch the legacy
custom Error; the corrected harness explicitly catches that known error class.

One mixed fixture has different ordered operation lists: v2 groups removals before
additions. The unordered planned changes/count agree, but ordered plan or full
report/checksum compatibility is NOT claimed. Any downstream ordered-plan consumer
must explicitly adopt schema2 semantics. Neither bridge executes those plans.
Both legacy and successor passed independent actual PeTTa/Janus fixture probes,
with exact path, one operation and false authority. Raw evidence is under
planner-parity-002 and planner-native-parity-001. No legacy consumer binding was
changed. Eleven state/successor tests still pass.

Provenance conclusion remains unchanged: archive and Git matching establish
identity/introduction, not ownership or a license grant. No additional rights
proof was found. Keep the repository-wide licensing issue and PR draft open.

## Complete mixed-plan parity correction

The earlier operation-order difference is now fixed in the successor: name order
is stable, with remove before install for each name. The successor emits the
same complete inner snapshot plan fields as the legacy scalar bridge (schema,
snapshot-only backend identity, before state, desired state, ordered operations,
and canonical SHA256 plan id). Its outer report remains explicitly schema2 and
read-only. The plan checksum is not a signature or execution authorization.

The strengthened parity gate compares complete inner dictionaries and ordered
lists directly. Twelve cases pass: seven accepted complete plans and five invalid
input rejections. Unicode snapshot provenance also matches the legacy checksum.
A fixed mixed golden-plan regression locks the expected hello-remove,
hello-install,zeta-remove sequence and checksum. Twelve unit tests pass; the
actual PeTTa/Janus successor probe passes again. Evidence is retained under
planner-complete-parity-002. This supersedes the earlier unordered-only parity
finding, not its historical evidence. No legacy binding was modified.
General MeTTa text parser parity and external caller compatibility remain outside
this scalar bridge gate. Licensing/provenance remains unresolved repository-wide.

## Real read-only observation fixtures

`qualify_observed_parity.py REPOSITORY NIX_BASE NEW_OUTPUT` reads native Nix JSON
for two retained nonempty private profiles and a retained empty generation.
No profile/package write command is invoked. Actual workspace store paths are
not rewritten to /nix/store: both bridges correctly reject those noncanonical
paths, including when desired intent is canonical but observed paths are not.
Duplicate provenance rejection is also compared. A real empty native generation
plus explicitly labelled fixture intent produces equal complete plans in both
bridges. The desired canonical fixture path is not claimed installed or real.

Seven comparisons passed across three native observations. A missing-path native
read failed as expected. Active pointer and journal hash stayed unchanged; all
retained rollback profiles remained present. These retained fixtures predate the
monotonic pointer journal and are read-only here, not candidates for automatic
migration or mutation under the new adapter. Twelve state tests pass.
Evidence: planner-observed-parity-002/result.json. This establishes observation
boundary/parity behavior, not a live canonical /nix/store package installation,
closure integrity, production readiness or license clearance. Legacy bindings
remain untouched and the draft licensing block remains.

## Native missing/corrupt rollback observation gate

`qualify_profile_failures.py NIX_BASE NEW_OUTPUT` builds fresh private profiles,
retains the first, and activates the second. It temporarily moves only the old
private symlink to simulate a missing target, then points it at a disposable copy
with malformed JSON, and finally a valid manifest from the wrong generation.
All three native rollback observations are rejected with the active token
unchanged. Restoring the old private symlink permits reviewed rollback at the
next revision, restoring payload1. The original native manifest digest remains
unchanged. No Nix store object is deliberately corrupted; only a private copy is
written, and symlink manifests are refused before writing.

The final receipt is profile-observation-failures-002/result.json. Twelve state
tests pass. These are process-level private fixtures, not installed OS recovery,
physical power loss, guest health or licensing clearance. Legacy consumers and
the repository-wide unresolved-source issue remain unchanged. Keep PR22 draft
until independent review and provenance/rights decisions are complete.

## Reconciled opt-in for existing bridge consumers

The branch merged current main0f3117c without conflicts (merge a861b46), preserving
all upstream work. Existing `package_bridge.py` now reads a trusted launch-time
ROKO_PACKAGE_PLANNER selector. Unset/legacy retains the old import and behavior;
successor-v2 imports only the independent scalar adapter; unknown values fail
instead of silently choosing a backend. Request/snapshot data cannot set it.
The existing native test runner forwards this one launch selection and records
it. Existing code importing package_planning directly is not migrated.

Adoption/rollback: restart the bridge-owning process with successor-v2 after
consumer schema2 acceptance; to restore the default, restart with legacy or unset
the selector. No profile/package or user database migration is performed. Keep
legacy source while any default/direct consumer depends on it, and obtain rights
proof or replace remaining consumers before claiming repository-wide clearance.

Fourteen state/bridge tests pass after reconciliation. Fresh subprocess tests
prove default legacy, complete inner-plan equality, no omega_pm import in successor
mode, and unknown-mode rejection. Both launch selections also passed the SAME
actual PeTTa/Janus bridge fixture (count, desired path, no authority), with native
logs retained in bridge-opt-in-native-001. The reconciled 101-test OS suite passed.
This is opt-in behavior only; no production consumer or host state was activated.

## Startup failure and legacy restoration

`qualify_bridge_restart.py REPOSITORY NIX_BASE NEW_OUTPUT` collects the actual
retained empty native profile manifest, combines it with explicitly labelled
fixture intent, and exercises five fresh processes: default legacy, explicit
successor, injected missing successor module, invalid selector, restored unset
default. All phases pass their expected outcomes. Failed startup does not silently
fall back or import omega_pm; restoring the default produces the exact original
legacy report and complete inner plan. The current profile pointer and retained
rollback links remain unchanged. This does not remove the legacy dependency.

A separate actual PeTTa/Janus launch with an invalid selector emitted the expected
startup diagnostic and no success marker. A new launch with the selector unset
passed the same fixture as the old default. Evidence in bridge-restart-001 records
both failure and restoration. The missing-module injection is a Python import
fault fixture, not a claim that a real installed package was removed. The prior
native-profile parity gate separately covers nonempty workspace observations and
their required canonical-path rejection. No host activation, package operation or
license clearance follows from these read-only migration checks. Keep PR22 draft.

## Remaining-caller acceptance and deletion gate

The tracked static inventory is reproducible with audit_planner_consumers.py;
its AST import edges and text-reference locations carry file hashes. Conditional
and test imports are labelled, not treated as proof of runtime calls. Dynamic
imports, user-installed entry points and external callers remain incomplete.
A dirty worktree is recorded, so the baseline commit is not misrepresented as an
exact snapshot of unstaged/staged source. No inventory result authorizes deletion.

provenance/remaining-caller-migration.json records four separately reviewed gates:
- Scalar bridge: explicit schema2 acceptance and helper/inner-plan/startup parity;
  opt-in remains reversible by process restart with legacy/unset.
- Direct parser/SnapshotOnly API: not supplied by v2. Inventory external calls and
  migrate to explicit structured input with error-boundary tests before removal.
- Console entry point: no drop-in replacement. Preserve the old state directories,
  prepare read-only exports, build/test a new private-root CLI and explicit state
  import, and never share mutable profiles between old/new controllers. Existing
  legacy Nix mutation incompatibility is not a safe rollback fallback. Preserve
  source/state without silently invoking old apply or deleting data.
- Hyperon awareness: projection.py is not a drop-in. Agree with the cognitive owner
  on stage/revision/provenance and live snapshot/CAS/restart behavior. An observed
  operation receipt cannot become installed/running/health by renaming predicates.

No default was switched and no baseline source deleted. Keep the current scalar
opt-in for experiments; require separate review for each remaining consumer.
Archive/Git identities and source-context investigation are provenance evidence,
not a license determination or proof of third-party ownership. The parent reviews
original context separately; private room transcripts are not republished here.
Rights/project-license and historic-import decisions remain explicit release gates.
Sixteen state/inventory tests pass, including static/dynamic scope, syntax failures
and unchanged input hashes. No PR description retry or host activation is involved.

## Direct adapter and read-only CLI opt-in

`package_planning.py` now selects the successor only when the trusted process
launcher explicitly sets ROKO_PACKAGE_PLANNER=successor-v2. Unset/legacy keeps the
original definitions/import behavior and class module names. Unknown modes fail.
The same scalar bridge continues to work in both selections, proven again through
actual PeTTa/Janus; legacy component tests remain30 passes/one live Hyperon skip.

Successor `plan_source` requires JSON with exactly schema=roko-snapshot-desired-v2
and packages. It does not accept or evaluate the old MeTTa text language. Reports
use outer schema2; complete multi-package inner plans and observed snapshot
values/identity match the old adapter on the disposable regression. SnapshotOnly
returns independent observation dictionaries. Object class identity, mutable
.snapshot internals, external exception catches and general text-parser semantics
are NOT drop-in guarantees. Restart with legacy/unset to restore that API; no
state/profile is migrated by selecting an adapter.

`python omega-baseline/integration/package_snapshot_cli.py --planner successor-v2
--desired DESIRED_JSON --snapshot SNAPSHOT_JSON` is a separate, explicit read-only
CLI. It emits plans on stdout, reads bounded regular non-symlink inputs and
refuses root use. Missing selection and --apply are rejected before mutation;
input files remain unchanged. It does NOT replace the original omega-pm entry
point or its simulation/apply/state interfaces. Those mutation surfaces and
Hyperon awareness remain pending independent replacements and owner schema review.

Nineteen state/migration tests pass, including multi-package complete-plan parity,
snapshot isolation, invalid text input, explicit CLI selection and apply rejection.
No default takeover, legacy package-source deletion, license clearance or host
activation occurred. This is an opt-in read-only migration step, not completion
of every inventoried legacy surface. Keep PR22 draft and metadata retry stopped.

## Read-only awareness contract assessment

The opt-in package_awareness_v2.SnapshotAwareness accepts a read-only backend and
an explicit caller-owned fresh runtime factory. It imports neither omega_pm nor
Hyperon, installs no runtime, evaluates no desired rules and exposes no apply.
It validates the supplied snapshot, creates legacy-shaped data atoms in a NEW
dedicated runtime, and publishes current only after the whole insertion succeeds.
The caller must guarantee an independent fresh space; immediate current-runtime
reuse is additionally rejected. This is not a general sandbox for arbitrary
factories, not a durable owner subscription and not proof of every historical
space/proxy being distinct. Consumers must use the returned observation/runtime.

Separate fixture subprocesses compare old/new initial facts, removal on refresh,
escaped opaque revision, backend/revision identity, no query calls and preservation
of current after factory failure. All eight parity fields match; the successor
imports no legacy core. Additional unit tests reject current-runtime reuse before
append and preserve current after a partial fresh-sink insertion failure. The
current Python has no Hyperon package, so native Hyperon compatibility is FALSE.
These are contract doubles; prior PeTTa proofs do not substitute for this native
Hyperon gate. No existing awareness binding or factory default was changed.

The installed predicate here is historical legacy-format snapshot data, not a
claim that arbitrary fixture packages are installed or that a built/running/health
stage was proven. This adapter is not the v1 durable OS-fact projection contract.
Desired-from-MeTTa queries, live owner-space integration and mutating CLI remain
separate migrations. See MUTATING_CLI_REQUIREMENTS.md for explicit action gates.
Twenty-one state tests pass. Provenance/licensing remains unresolved, PR22 stays
draft and the blocked metadata update has not been retried.
