# Offline closure assembly preflight

`qualify_offline_closure.py NIX_BASE ROOTS_JSON NEW_OUTPUT` accepts up to eight
explicit local derivations in the private store. It rejects remote/flake refs,
flags and foreign paths before Nix execution. It observes each derivation's out
path and runs ordinary recursive path-info offline. Only if every root is local
and valid does it run ordinary recursive store verification, then copy into a
private file:// cache. It never requests build/repair, disables signatures/trust,
activates a profile, retries sandboxing or modifies host security settings.

Current policy-definition identities were refreshed (live-image-derivation-003),
with stable repeated headless evaluation. Preflight found all four outputs absent:
headless ISO/system and COSMIC ISO/system. Exact output paths/native diagnostics
are in offline-image-closure-002. Verification and cache export were skipped, not
failed or bypassed. The CLI returns2 for unavailable/unexported closure. No offline
image closure could be assembled from the inputs present in this executor.

A separate EXISTING TINY PROFILE FIXTURE passed recursive path-info, ordinary Nix
store verification and local cache export. Its cache file hashes are retained in
offline-fixture-closure-002; cache bytes stay private in the workspace. This tests
export mechanism only. It is a non-hermetic development output, not a NixOS ISO,
model closure, transfer/import test or proof that another machine trusts it.
No cache-signing keys or signature-check exceptions were configured.

106 OS tests pass, including rejection of remote/flag roots before command
execution. Source pins remain unchanged; strict sandboxing is still unavailable.
The next image build needs a capable disposable executor and verified acquisition
or realization of the actual pinned dependencies with appropriate store-prefix
and trust policy. Do not silently normalize workspace paths, disable checks or
activate the host to work around missing outputs. The unresolved legacy-source
licensing issue, operator provisioning, persistent history and guest boot/model
qualification remain release blockers. PR22 remains draft. No PR metadata retry.
