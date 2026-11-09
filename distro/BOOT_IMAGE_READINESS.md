# Daily-driver boot image requirements and current gaps

Initial assessment against main0f3117c found no NixOS/Guix system configuration
or source lock. Subsequent evaluation-only definitions and candidate input pin
are described below; they do not supply a realized system image. The checked-in Nix expressions are local
profile/build fixtures; they do not declare an operating system. The existing
Debian extracted kernel/QEMU path is bootstrap qualification infrastructure.

## Required reproducible system inputs

- A reviewed immutable nixpkgs/Guix source identity and complete dependency lock,
  selected platform and retained source/closure provenance. A store output path
  or JSON digest alone does not prove source origin or a hermetic build.
- Declarative kernel, initramfs, root generation, non-root user/session, COSMIC
  and graphics/audio/input/network services. Production identity allocation must
  not assume the fixture UID1000. Keep host-specific hardware discovery outside
  a generic image and explicitly bind supported firmware inputs/licenses.
- Complete guest-local Python/Janus/SWI/PeTTa/Omega/model and bubble closure with
  matching ABI, selected v2 endpoint, hash inventory and immutable image build ID.
  Do not substitute the host runtime or combine different endpoint/profile pins.
- A defined partition/boot artifact layout and installation contract, signed
  release identity/trust, retained generations and bounded confirmation/fallback.
  Virtual UEFI fallback evidence does not establish a Secure Boot chain or
  production installation/recovery. Never auto-activate from an AtomSpace fact.
- Private persistent user/model/history volumes with schema migration/rollback
  rules, backup/restore and compatibility across retained OS generations. Existing
  cold-boot/crash fixtures validate one private ext4 fixture, not arbitrary history.

## Evidence and blockers

`integration/qualify_boot_repro.py REPOSITORY NEW_OUTPUT` makes two copied-source
minimal rescue builds with different paths, timestamps, TZ and SOURCE_DATE_EPOCH.
The executed boot-repro-001 gate found equal init/initramfs bytes and manifests,
fixed gzip/archive metadata and unchanged source. Nine boot/build tests pass.
This contains no kernel, COSMIC or model and does not boot a VM. Same local GCC
is used; cross-host/toolchain reproduction and upstream builds remain unqualified.

Existing proofs remain separately scoped: minimal non-root QEMU boots, symbolic
native checks, virtual systemd-boot trial exhaustion, ext4 persistence/recovery,
private Nix profile state and actual PeTTa/Omega receipt projection. None produce
an installable declarative system image. A minimum image milestone needs locked
system sources and a complete root generation, then independent boots and health
receipts before normal user installation can be considered.

Blockers: transferred COSMIC capsule lacks desktop executable/runtime; ISO download
returned HTTP401 and remains stopped. /dev/kvm is unavailable; model guest started
native inference but failed its deadline. Intel iGPU, sleep/resume, disk install,
real hardware network/audio/input and Secure Boot have not been qualified. The
legacy package-planner source licensing remains unresolved and still supports
active defaults/direct consumers; this is a release blocker, not a solved issue.

## Non-destructive next gates

Build a source-locked disposable NixOS/Guix generation without host activation;
compare independent outputs and retain toolchain/closure inputs. Boot it with no
host disks, verify actual non-root COSMIC/bubble/model recall and cancellation,
and bind independent health facts to the exact generation. Exercise retained
rollback and persistent-history compatibility before provisioning a disposable
installation target. Physical consumer-device tests need a separate explicit
hardware target and test evidence. Keep PR22 draft pending review/provenance.

A subsequent [Nix bootstrap rescue definition](nix/README.md) now builds and forces
rebuild of the minimal rescue artifacts in the disposable store. Gate004 outputs
match and rejects wrong source hashes. It deliberately uses unpinned host tool
closure inputs and does not supply a declarative system image, kernel or desktop.

Pinned-source follow-up: rescue-pinned.nix now resolves a NAR-verified nixpkgs
candidate and Nix toolchain derivation identities. It has NOT built: strict
sandboxing with fallback disabled is blocked by unavailable kernel namespaces.
This does not satisfy the locked system-generation, actual build, boot or health
gates above. The bootstrap rescue remains a separate unsandboxed local result.

Subsequent system-eval.nix now checks headless and optional COSMIC NixOS modules
against the pinned candidate source with import-from-derivation disabled. The
unprovisioned case intentionally retains its lockout assertion; fresh fixture-key
provisioned cases have no failed assertions. Nix is enabled, users remain normal
and password-locked, SSH/sudo and EFI-variable writes are disabled. No toplevel
closure, disk image or compositor/model process was realized. Real provisioning,
strict sandbox build and boot/health/recovery gates remain required. See
nix/SANDBOX_QUALIFICATION.md. Licensing remains unresolved.
