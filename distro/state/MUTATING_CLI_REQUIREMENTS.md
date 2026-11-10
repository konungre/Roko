# Remaining mutating CLI requirements (not implemented/enabled)

The new package_snapshot_cli.py is READ ONLY. Its snapshot-only plans cannot be
passed to a mutating executor. The original omega-pm entry point/default remains;
its Nix mutation compatibility is unqualified. No automatic alias or state import
is provided. The following are acceptance gates, not permission to change a host.

1. Separate reviewed command/namespace for disposable private profiles. Refuse
   root, host/system/default-profile targets, remote/flake expressions, unknown
   arguments and request-selected executables. Keep read-only commands default.
2. Explicit source/closure provenance and native observation before preparing a
   roko-private-plan-v1. Bind source lock, profile root, exact outputs, predecessor,
   monotonic revision and desired set. Never activate a plan from a caller-supplied
   historical snapshot or promote a checksum into authority.
3. Use trusted external review, not a JSON/AtomSpace 'approved' flag. Recheck and
   reserve revision under lock AFTER review at the actual action boundary. Cover
   ABA, review-time mutation, replay, concurrent writers and unreviewed decisions.
4. Prepare/verify a whole native candidate before switching one pointer. Preserve
   old generations and explicit reviewed recovery. Missing/corrupt/wrong-generation
   observations must leave current state intact. Empty-profile activation remains
   unsupported until separately implemented/tested; do not emulate it by deleting
   the old profile or falling back to the legacy remove/install sequence.
5. Migration is read-only export from old simulation/profile/state roots into a
   NEW private root, with explicit owner/path/digest checks. Never let old/new
   controllers share a mutable profile. Retain backups and original binding;
   do not auto-rewrite MeTTa configs as executable input. Import is a separate
   reviewed transaction with schema validation, not discovery-driven adoption.
6. Define uncertain outcome/cancellation handling. A consumed or pending revision
   cannot auto-retry; inspect native state before explicit recovery. Generic
   handler side effects are not a cross-system transaction. Verify rollback and
   restoration on disposable data with process fault injection before migration.
7. Reopen durable receipts, verify chain/CAS and publish explicit stage facts only.
   Hyperon legacy-shaped installed data, desired intent, built output and running
   health are different contracts. No model/runtime query grants execution rights.
8. Preserve bounded resource/output/deadline/cleanup behavior and keep credentials
   out of logs/fixtures. Test only new private workspace roots. No host activation,
   privileged daemon, GC, old-generation deletion or network fallback is implied.
9. Obtain consumer acceptance for CLI syntax, JSON/error schema and explicit
   operator review. Restore prior read-only bindings without mutating old state.
   Existing legacy Nix apply is not a tested rollback mechanism.
10. Review repository/source licensing separately. Origin context is evidence,
    not a rights grant. Keep PR22 draft until rights/integration review completes.

No new mutating console command has been added by the awareness parity work.
