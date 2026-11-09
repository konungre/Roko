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
