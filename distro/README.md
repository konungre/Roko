# Roko distribution foundation v1

This additive foundation is based on live-system commit `9990714`. It does not
change historical boot recipes or certify the current live USB. No deployable
kernel/root filesystem/model closure is supplied. No host installation, disk
write, network download, service enablement or boot selection is performed.

## Offline release bundles

Run `python3 -B distro/release.py LOCK ABSOLUTE_ASSET_DIRECTORY NEW_OUTPUT.tar`.
The input directory and output parent must be trusted, operator-owned build
locations. The input path must be canonical and symlink-free. Output publication
is exclusive and fsynced; existing checkpoints are never overwritten. Failed
verification removes temporary output. If publication succeeds but directory
fsync fails, an output can remain: inspect it before retrying with a new name.

The strict JSON lock has exactly these fields:

```json
{
  "schema": "roko-release-v1",
  "architecture": "x86_64",
  "release": "candidate-001",
  "assets": [
    {"name": "vmlinuz", "role": "kernel", "bytes": 1, "sha256": "REPLACE_WITH_VERIFIED_DIGEST"},
    {"name": "initramfs", "role": "initramfs", "bytes": 1, "sha256": "REPLACE_WITH_VERIFIED_DIGEST"},
    {"name": "rootfs", "role": "rootfs", "bytes": 1, "sha256": "REPLACE_WITH_VERIFIED_DIGEST"}
  ]
}
```

This illustrative lock deliberately fails validation. Supply actual sizes and
reviewed SHA256 values; do not generate a lock from untrusted downloads and call
that authentication. Exactly one kernel, initramfs and rootfs are required;
optional `model` and `firmware` entries allow multiple flat files. Each file is
limited to 64 GiB, with at most 128 files. Budget free output space explicitly.
Checksums establish correspondence to the lock, not origin, licensing, format,
bootability or signature trust. The packer streams bytes and forbids links,
devices, FIFOs, traversal, duplicate keys and incomplete core role sets.

Output is an uncompressed USTAR archive with canonical `release.json` and
`assets/NAME`, sorted entries, fixed ownership/mode/time and no host paths. Equal
locks and equal bytes produce identical bundles regardless of source mtimes,
modes and input ordering. This is **reproducible packaging**, not proof that the
upstream toolchain, COSMIC, kernel or root filesystem builds reproducibly.
The printed report explicitly leaves boot, hardware and signature checks false.

## Runtime interface proposal for other workspaces

- Desktop/avatar: launch COSMIC through the distribution's normal authenticated
  user session. Never run the compositor, avatar or terminal as root. Retain the
  existing `XDG_STATE_HOME/roko` convention (default `$HOME/.local/state/roko`),
  user ownership, mode 0700 and atomic durable state writes. Do not hard-code UID
  1000 into a production image; existing guest fixtures may keep their UID.
- AI/model: immutable versioned executable closure at `/opt/roko`, reviewed model
  manifest at `/opt/roko/models/manifest.json`, dedicated `roko-model` system user,
  writable private state `/var/lib/roko-model`, runtime `/run/roko-model`.
  The included systemd unit is an **inactive contract**: the named worker is not
  yet implemented by this foundation. It has no installation target and does not
  auto-enable. CPU inference is capped at 20 GiB with a 16 GiB soft boundary,
  leaving headroom on a 32 GiB target; these are initial budgets, not benchmarks.
- AI integration owner must supply a foreground `roko-model-worker`, handle TERM,
  obey the manifest, remain offline, and use `ROKO_SOCKET`. That socket is private
  to the model account; desktop IPC requires a separately reviewed broker or
  peer-credential-checked access design before integration. Do not widen the
  directory to world-readable or bridge it through a root model process.
- Intel graphics: normal logind/seat access for COSMIC. Model worker currently has
  `PrivateDevices=yes`: no GPU access. GPU inference requires a separately tested
  render-node policy, firmware/driver closure and memory budget.
- Live-system owner retains native-context transport/semantic proof interfaces.
  This bundle format does not change their schemas or turn synthetic tests into
  native qualification. Other worktrees remain untouched.

The service/sysusers files are image composition inputs only. Do not copy them
onto the development host. Their syntax check does not verify runtime isolation.
No desktop service is invented here: PAM/logind/session/lock behavior must be
qualified with the chosen COSMIC base.

## Persistent state, updates and recovery contract

The eventual installer must separate immutable system slots from mutable user and
model state. Select a base distribution, filesystem layout, stable partition
identifiers, encryption/recovery policy and signed boot chain before implementing
writes. This foundation intentionally contains no arbitrary-device writer.

A candidate update must authenticate its release manifest against an enrolled
trust root, enforce version/rollback policy, verify the complete offline closure,
check available space and hardware prerequisites, and write only the inactive
slot. Keep a verified last-known-good kernel, initramfs and rootfs together.
Commit boot selection only after durable staging. Trial boot with bounded retry;
mark successful only after non-root COSMIC login, local model health, state
reopening and storage checks. Failed trial must return to the good slot without
network. State-schema migration needs a separately recoverable snapshot and a
backwards-compatible plan: system rollback alone cannot undo data migration.

Before installing, implement and test power-loss faults at every transition,
full disk, corrupted/unsigned assets, downgrade rejection, failed login/model,
missing state partition, interrupted migration, and recovery from USB. Tar bundles
are transport artifacts, **not an implemented atomic updater or installer**.

## Qualification matrix and commands

Portable checks (no model/VM/network required):

```sh
python3 -B -m unittest discover -s distro/tests -v
```

Required evidence still missing for a release:

| Area | Required gate |
| --- | --- |
| Build | Authenticated source/toolchain/package locks; licenses; independent clean rebuild comparison |
| Boot | UEFI and legacy decision, Secure Boot policy, real kernel/initramfs/rootfs boot, offline cold boot |
| Identity | Non-root desktop and model process observations; login/lock isolation; sandbox enforcement |
| Persistence | Two physical cold boots, abrupt power loss, full disk, owned state reopening and migrations |
| Updates | Signed manifest admission, A/B trial and rollback, interrupted writes, offline rescue |
| Devices | Intel i915/xe generation matrix, firmware, Wi-Fi, audio, touchpad, USB, NVMe, suspend/resume |
| Resources | 32 GiB host pressure, model OOM recovery without desktop loss, CPU/GPU latency and thermals |

Tests use explicitly synthetic fixture bytes, not executable kernels or real
models. QEMU is not installed in this environment. Hardware and production claims
remain blocked on actual inputs, integration and target-device testing.
