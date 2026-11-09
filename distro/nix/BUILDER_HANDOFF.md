# Reproducible acquisition/build verification handoff

This is a checklist for a separately provisioned disposable builder, NOT evidence
that this executor can build the image. Kernel namespaces remain unavailable here;
no retry, privilege escalation or host-setting change is authorized by this file.
Keep PR22 draft and preserve all source/license caveats.

1. Pin the reviewed repository commit, nixpkgs-candidate.json and local module
   hashes. Verify both upstream archive SHA256 and extracted NAR hash. Record
   explicit firmware/network/access parameters and protected test-credential
   identities. Never use or publish a real operator password/hash/private key in
   fixtures, logs, public caches or Git. Production secret provisioning remains
   a separate unresolved design; use ephemeral credentials only for isolated tests.
2. Evaluate with IFD disabled. Confirm the unprovisioned lockout negative case,
   normal user/root locks, no auto-login and no EFI-variable writes. Resolve exact
   system/image derivations from the SAME inputs. Changing credentials, policy or
   store prefix changes identities; do not reuse historical output paths blindly.
3. Qualify a fresh strict sandbox: sandbox=true, sandbox-fallback=false, declared
   Nix-store toolchain, inaccessible undeclared host canary and native namespace/
   mount evidence. Stop on failure. Option acceptance or success with fallback is
   not proof. See SANDBOX_QUALIFICATION.md.
4. Acquire missing dependencies only on that authorized builder, using normal
   source/hash and binary-cache signature/trust checks. Record substituter/source
   provenance. Do not rewrite paths, disable signatures, auto-repair corrupt data
   or silently fall back to unsandboxed builds. Stage complete inputs before the
   offline realization test. Current workspace requested outputs are absent.
5. Realize the exact reviewed roots offline and inside the strict sandbox. Retain
   commands, exit codes, derivation/source identities, dependency inventories and
   bounded logs. Run ordinary recursive path-info and store verification. Missing
   paths or failed verification must stop export; do not label metadata a closure.
6. Force rebuild and compare outputs/NAR hashes. Repeat on an independent clean
   builder with the same logical store prefix and inputs. Matching derivation
   identities alone does not establish matching image bytes. Record toolchain and
   image-creation tools; inspect embedded timestamps/UUIDs if bytes differ.
7. Export to a private local cache using normal Nix copy, then verify import and
   closure on a fresh target under the approved trust policy. The tiny fixture
   export in this executor is not an image or cross-machine trust test. Current
   qualify_offline_closure.py deliberately targets the workspace store; a canonical
   builder needs a separately reviewed store-layout binding, not arbitrary URL input.
8. Supply an UNQUALIFIED evidence packet: source-pin.json, sandbox-result.json,
   roots.json, closure-verification.json and image-hashes.json. Manifest schema is
   roko-builder-packet-v1, status unqualified, files mapping exact names to SHA256.
   verify_builder_packet.py checks correspondence and expected source pin only.
   It never verifies a builder identity/signature, replays sandbox evidence,
   validates semantic claims, grants authority or marks an image ready. Review
   authenticated native evidence independently; a self-hashed manifest is not trust.
9. Only then boot in a disposable VM with no host disks and explicit resource/
   timeout/cleanup limits. Prove non-root login/desktop, offline behavior, exact
   generation/health and retained rollback. Test persistent history/replay and
   model cancellation with the qualified guest closure before a daily-driver claim.
10. Keep licensing/provenance review separate. The legacy prototype source still
    supports active default/direct consumers. No archive/Git identity or new build
    definition supplies the missing rights-holder grant. No release clearance.

Verification tests cover packet tamper, missing/symlink files, wrong source pin,
false qualified status and inability of checksum success to grant image readiness.
No builder connection or acquisition beyond existing authorized inputs is initiated.
