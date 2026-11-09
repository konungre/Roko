# Nix bootstrap rescue derivation

`rescue.nix` declares the existing public freestanding serial rescue build as a
Nix derivation. It asserts supplied SHA256 identities for init.c/build.py, imports
only the boot-source subset, and declares x86_64-linux and fixed environment
metadata. It produces static init, deterministic initramfs and the build manifest.
No kernel, root filesystem generation, desktop or model is included.

Run `python3 distro/integration/qualify_nix_rescue.py REPOSITORY NIX_BASE NEW_OUTPUT`
with the previously qualified workspace Nix runtime/store. It records input hashes,
first build, forced `--rebuild`, output hashes and a rejected wrong-source-hash
evaluation. Gate004 passed all checks. The initial layout/filter failures are
retained separately; the standalone rescue builder was not weakened or changed.
A cached first build is permitted, but the second command forces a rebuild.

IMPORTANT: this is a bootstrap development derivation, not a hermetic package.
bootstrapPython and bootstrapPath are explicit HOST paths. Python/GCC executable
hashes are recorded, but their full interpreter/compiler/linker/library closure
is not pinned into Nix. Sandbox was disabled in the disposable workspace store.
Thus successful repeated local outputs do not prove cross-machine/toolchain
reproduction or trusted upstream origin. No nixpkgs, channel or OS image is fetched.
No host store/profile/system is activated, and no VM is booted by this gate.

To reach a declarative system image, replace host tools with a reviewed pinned
Nix toolchain closure, bind kernel/root/service/COSMIC/Omega/model inputs and
persistent-state schema, then qualify builds and actual isolated boots/rollback.
The package-manager prototype licensing issue remains unresolved independently.
Keep PR22 draft; no daily-driver or redistribution clearance follows from this.

References: [Nix derivations](https://nix.dev/manual/nix/2.26/language/derivations)
and [nix build](https://nix.dev/manual/nix/2.26/command-ref/new-cli/nix3-build).

## Pinned toolchain-input evaluation prototype

`rescue-pinned.nix` replaces explicit host Python/GCC paths with Python and stdenv
from an immutable nixpkgs tree. `nixpkgs-candidate.json` records upstream revision,
archive SHA256 and extracted source NAR hash. The source came from NixOS/nixpkgs
at f4a03c008967841f2a0b3cb7c436fc6fc31671f6, captured from nixos-unstable once;
this is a candidate input, not a selected production channel or update policy.
No upstream source archive is committed in this repository.

Run `qualify_pinned_rescue.py REPOSITORY NIX_BASE EXTRACTED_NIXPKGS NEW_OUTPUT`
to evaluate it offline. The definition verifies the source NAR pin and rescue
source hashes. Evaluation resolved x86_64-linux output and derivation identities
and a Nix-store bash builder with three direct derivation inputs. Wrong source NAR
pin was rejected. These are RESOLVED inputs only; dependencies have not been
realized and this pinned definition has not built or booted here. Source identity
is not a package-source/license audit or proof of reproducibility/trust.

## Strict sandbox blocker (do not infer isolation from fallback)

A rescue `--rebuild` requesting sandbox=true returned success with default
fallback behavior; that is not isolation evidence. A FRESH canary derivation with
sandbox=true AND sandbox-fallback=false failed before build: Nix reports that the
required kernel namespaces are unsupported. No host canary visibility result was
obtained, and sandbox isolation is explicitly false. Raw commands/receipts are in
integration/evidence/nix-sandbox-001 and nix-sandbox-probe-001.
The strict sandbox attempt stopped; no kernel/host permission changes or fallback
were used to turn it into a pass. The older unsandboxed bootstrap result remains
separate. Building pinned toolchain closures in an executor supporting the required
namespaces, verifying repeat outputs/closure and then actual guest boots are still
required. No hermeticity, NixOS image, daily-driver readiness or licensing clearance
is claimed. The existing legacy package-source issue remains unresolved.

Sandbox behavior reference: [Nix configuration](https://nix.dev/manual/nix/2.26/command-ref/conf-file#conf-sandbox).

## Evaluation-only NixOS base definition

`system-eval.nix` uses the NAR-pinned source to define headless and optional COSMIC
modules, EFI boot layout labels and a separate /home volume. It configures normal
users, password locks and disabled host EFI-variable writes. SSH and sudo remain
disabled. No filesystem is formatted and no boot variable or host profile changed.
These partition labels are declarative placeholders, not discovered host devices.

`qualify_system_eval.py REPOSITORY NIX_BASE SOURCE NEW_OUTPUT` evaluates module
options/assertions offline with import-from-derivation disabled. It tests an
unprovisioned negative case and two fixture-key provisioned cases. A fresh local
SSH key is used only to exercise the provisioning assertion; its private half is
not committed and must never be deployed. Supplying a public key satisfies one
module assertion, not an operational login/admin path: SSH, sudo and password
login are still disabled, and real provisioning/recovery policy remains required.

The initial query had a Nix lambda-spacing error; then evaluation exposed the real
locked-out-admin assertion. Those diagnostics are retained. No assertion was
removed or disabled. Final headless/COSMIC cases have no failed module assertions;
COSMIC and greeter flags match the selected mode. Neither a system toplevel closure
nor image was built, and no compositor/model ran. Model and authority metadata
are explicitly false. This is a definition/evaluation prototype only.

See [strict sandbox qualification](SANDBOX_QUALIFICATION.md) for exact next gates.
