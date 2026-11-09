# Disposable builder qualification procedure

This is a procedure for an appropriately provisioned, separately reviewed builder,
not permission to alter the current host, retry unavailable namespaces, or acquire
blocked inputs. The current executor's canonical-store prerequisite is still
missing. This change supplies packet consistency checks and fixture tests only.

## Provision and bind the test

1. Use a disposable VM/builder with no attached host disks, no production secrets,
   and an actual populated canonical `/nix/store` profile. Provisioning/building
   that fixture is a separate authorized step. Keep any existing system profile
   untouched; select the disposable profile explicitly for every command. Pin the
   reviewed source commit, Nix/Hyperon versions and runtime closure hashes, logical
   store URI, profile path, fixture package outputs and ephemeral evidence root.
2. Work as the non-root test account. Ensure evidence/checkpoint directories are
   new, private and owned. Keep the profile owner quiescent for the observation
   sequence; the observer's before/after samples do not exclude ABA by themselves.
   Record profile and manifest identities before and after each stage.
3. Run native Nix offline against that exact canonical store/profile. Save raw
   `profile list --profile <fixture-profile> --json` output and exit status. Use
   the configured read-only observer, never fabricated or translated output paths.
   Require at least one active package, one canonical output per active element,
   and no ambiguous package aliases. Stop on missing/malformed/unsupported output.
4. Run ordinary native recursive `path-info --json` for all active output roots
   in the same store context, then normal recursive `store verify`. Preserve raw
   commands, exits, references, NAR hashes and trust policy. Stop on missing output,
   corrupt metadata or verification failure. Do not repair, disable signatures,
   build implicitly, substitute from an unapproved source or rewrite paths.

## Observe, restart and exercise failures

5. Feed the observation into a fresh dedicated native Hyperon space and a new
   private checkpoint. Preserve native package-query bindings and complete
   snapshot/receipt, ensuring package names and paths agree exactly. No observation
   grants execution authority. Record the source, native revision and durable
   checkpoint version separately.
6. Exit and start a fresh process using the same checkpoint and backend identity.
   Explicit restore must be historical and make zero backend calls. Then explicitly
   refresh: with the unchanged native profile, require the same snapshot/revision
   and checkpoint version +1. Record a new process epoch. Preserve the previous
   native space; no auto-replay, automatic refresh or old-decision activation.
7. In separately reviewed disposable generations only, test removal and rollback,
   missing/broken profile, native failure, malformed/ambiguous responses, stale
   publisher rejection and interruption recovery. Retain old complete snapshots
   on failure. Missing profiles must not become empty installed-state reports.
   Distinguish injected response fixtures from genuine native failure cases.

## Evidence consistency and offline boot are separate gates

8. Supply `roko-profile-packet-v1`, status `unqualified`, with exactly these fields:
   `schema`, `status`, `observation`, `path_info`, `snapshot`, `restart`.
   Observation is the existing ReadOnlyProfile receipt including its revision;
   path_info is the recursive inventory array of `{path,narHash,references,...}`;
   snapshot is `{packages,revision,source}`. Preserve raw output alongside any
   documented Nix-version format adaptation; never change path strings.
   Restart fields are `origin`, `backend_calls_at_restore`, `restored_snapshot`,
   `checkpoint_version`, `refreshed_version`, `refreshed_snapshot`. This packet
   covers the unchanged-profile restart phase, not the later removal phase.
9. `verify_profile_packet.verify(packet)` checks populated canonical outputs,
   recursive-inventory completeness, receipt/snapshot correspondence and historical
   restart/version progression. It is a partial self-report consistency check,
   not proof that commands ran, hashes are authentic, store bytes exist or the
   builder is trusted. It does not replace native store verification or independent
   review of raw receipts. All authority/readiness results remain false. Packet
   parsing and bounded file correspondence belong to the enclosing trusted collector;
   this function accepts an already decoded object, not arbitrary file paths.
10. Independently follow `../nix/BUILDER_HANDOFF.md`: pin exact image roots,
    qualify strict sandbox with fallback disabled, acquire authorized dependencies,
    realize offline, verify complete closure, compare independent rebuilds and test
    fresh-target cache import. Package-profile success cannot satisfy these gates.
    Keep its five-file builder packet separate; checksums alone prove neither
    closure trust nor image readiness. No new image acquisition/build was attempted
    in this executor.
11. Only independently reviewed image/closure evidence can precede a bounded VM
    boot trial. Prove non-root session, persistent state, offline model availability,
    health, update trial/fallback and retained recovery. None is established by a
    profile packet. Licensing/provenance and Hyperon dependency notices remain
    separate unresolved release gates. Legacy defaults and PR metadata hold persist.

The new packet tests are fixtures. They reject absent package outputs, incomplete
references, tampered snapshots/receipts, empty/noncanonical profiles, false qualified
status, action-authority claims and non-historical/stale restart data. The fixture
success case explicitly returns native/closure/builder verification, image readiness
and execution authority as false.
