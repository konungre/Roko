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
