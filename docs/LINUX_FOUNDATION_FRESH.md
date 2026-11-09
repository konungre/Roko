# Fresh Linux foundation checkpoint

This work starts from public commit `7548663`. The prior computer's unpushed
`dev/openai-linux-foundation` commit `0e4b60c` is not available in this checkout.
Do not treat this branch as containing that work. Transfer a Git bundle or patch
from that computer, verify its commit and base, and review overlap in
`omega-baseline/boot/build.py` before integrating. Nothing here is pushed.

## Reproducible public rescue build

From the repository root, with Python 3 and an x86-64 GCC toolchain:

```sh
python3 omega-baseline/boot/build.py --minimal --output /tmp/roko-rescue
python3 -B -m unittest discover -s omega-baseline/boot/tests -v
python3 omega-baseline/boot/foundation/hardware_preflight.py
```

`--minimal` deliberately selects a freestanding serial rescue image with no
BusyBox, COSMIC, model, disks, network setup, or external asset lock. It does not
silently replace the historical default build. The output contains `init`,
`roko-initramfs.cpio.gz`, and `build-manifest.json`. Two fresh output directories
produce identical binaries, compressed archives and manifests with the tested
compiler. Cross-toolchain and cross-host reproducibility remain unverified.
The manifest records the compiler, flags and hashes; the build ID is a source
identity, not a signature or a complete toolchain identity.

The newc validator rejects noncanonical paths, duplicates, truncation, invalid
file types/payloads, and nonzero data after the trailer. It does not extract
archives or establish safe extraction of arbitrary symlinks. ELF admission
requires a complete static x86-64 executable and bounded program headers and
segments; it is format validation, not trust or signature verification.

## Evidence from the fresh environment

Nine unittest cases passed on 2026-11-09. They exercise actual GCC compilation,
byte-for-byte repeated builds, execution of the compiled init's non-PID-1
refusal (exit 77), all truncations of the fixture archive, malformed paths,
duplicate records, invalid ELF inputs, and mixed-CPU/missing hardware evidence.
Compiler: `gcc (Debian 14.2.0-19) 14.2.0`.

No VM boot was executed. This environment has no installed QEMU system binary
or boot kernel in `/boot`; the public checkout omits the original verified
kernel/tooling lock. The observed cloud host is x86-64 with approximately
17.6 GiB visible memory, no observed PCI display controller, and no DRM cards.
The hardware collector is read-only and emits `qualification: unverified`.
These observations do not qualify a consumer 32 GB Intel iGPU computer.

## Integration gates still open

- Recover and inspect `0e4b60c` before duplicating its foundation interfaces.
- Restore a reviewed exact kernel/QEMU closure and run the serial-rescue VM
  gate against this initramfs; preserve serial logs and asset hashes.
- Build the full pinned COSMIC/runtime closure, including corresponding source
  and licenses. The public rescue image contains neither desktop nor Omega.
- Run the compositor/session and model under distinct unprivileged identities;
  test actual UID, filesystem, network, IPC, device and resource boundaries.
  The historical desktop profile still reports `runs_as_root: true`.
- Prove private persistent state ownership and recovery after interrupted
  writes and abrupt shutdowns. A clean two-boot test is insufficient evidence
  for power-loss safety.
- Implement authenticated updates and a recoverable boot selection protocol;
  test interrupted installation, corrupt payloads, rollback and exhausted disk.
  Never overwrite the only known-good boot slot during a trial update.
- Qualify UEFI boot/recovery, Intel graphics acceleration, display hotplug,
  suspend/resume, audio, Wi-Fi/Bluetooth and offline inference memory pressure
  on real target hardware. Record exact hardware, firmware and kernel versions.

The minimal rescue and its tests are a build/security checkpoint, not a
production-ready OS or evidence that the desktop has been made non-root.

## Reconciliation update

The prior foundation was subsequently recovered from the authorized private
Library transfer. All 60 entries in its checksum manifest passed; its complete
Git bundle verified at `209ec3cab14b13a2bc06764dfa170614ed26fc80` and merged at
`ac33690e1fddc23b27876c17f78ef1ab0ed6d1c4`. Both histories and published artwork
remain intact. The earlier transfer blocker above is resolved. The recovered
61-test distro suite passed in this fresh executor. Its historical COSMIC and
state results remain documented separately in `distro/session/SESSION_VALIDATION.json`.

The exact ISO004 parts were found in Library, but the current download helper
failed with HTTP 401 before downloading them. No ISO reconstruction or new VM
boot has occurred. The restored external QEMU closure remains unavailable.
The source-only merge does not recreate those external dependencies or qualify
the Python3.12 conversation closure inside the Python3.13 desktop.

Further work added [signed offline release admission](../distro/SIGNED_RELEASES.md)
with real Ed25519 tests. This authenticates bytes and checks an externally trusted
rollback floor; it does not implement installation or boot recovery.

The next checkpoint adds interruption-safe authenticated staging (no boot-slot
selection), actual process-death recovery tests, and real non-root Unix-peer
identity tests. The distro suite now passes 84 tests. See
`distro/session/FRESH_RUNTIME_HANDOFF.md` for exact missing runtime identities
and the conversation closure request to coordinate through the parent.
