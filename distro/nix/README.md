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
