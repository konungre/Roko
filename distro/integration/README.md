# Independent minimal guest qualification

This path does not use or replace the inaccessible ISO. It uses a freshly acquired
Debian kernel and QEMU/SeaBIOS in a workspace directory. No package installation,
maintainer script, host disk, network adapter, KVM or firmware-variable write is
performed. The historical ISO runtime lock stays unchanged.

Official package URLs, versions, sizes and SHA256 values are recorded in
`TEST_RUNTIME_PACKAGES.json`. APT verified the Debian InRelease/package metadata
using the installed Debian archive keyring, then downloaded29 packages (125 MB)
in download-only mode. Each downloaded hash was checked again against APT's URI
metadata. Packages were extracted with `dpkg-deb -x`, without installation.
The test QEMU is10.0.13; the kernel is6.12.116+deb13-amd64.

`prepare_test_runtime.py DIRECTORY` assembles a minimal runtime from trusted
`DIRECTORY/root` package extraction and `DIRECTORY/packages.json` acquisition
receipt. It copies QEMU's resolved host shared libraries, records their provenance,
and locks every resulting file/symlink. This is a measured local runtime, not a
hermetic cross-host reproduction. The original execution verified131 entries
before every VM. Retain the file lock and package receipt with the evidence.

## Trial/fallback test

```sh
python3 distro/build_probe.py NEW_GOOD_PROBE
python3 distro/build_probe.py NEW_BAD_PROBE --fail-trial
python3 distro/update/run_boot_trials.py NEW_GOOD_PROBE NEW_BAD_PROBE RUNTIME_ROOT RUNTIME_LOCK NEW_RESULTS
```

The injected-failure init still verifies the actual guest's UID/GID1000,
empty supplementary groups, no_new_privs and denied root regain, then reports an
intentional unhealthy result and powers off. Three actual failed-health boots
consume the journal's budget. The fourth actual boot selects the good initramfs
and passes. A separate healthy trial boots and is confirmed with its current
nonce. All QEMU children are reaped. This exercises a host-side userspace journal
selecting real initramfs bytes; it does not qualify firmware A/B boot selection,
signed installation, boot-health IPC security or physical power-loss recovery.

## Non-root symbolic guest

```sh
python3 distro/integration/build_symbolic_guest.py LOCAL_SYMBOLIC_ROOT NEW_SYMBOLIC_GUEST
python3 distro/run_probe.py NEW_SYMBOLIC_GUEST RUNTIME_ROOT RUNTIME_LOCK NEW_RESULTS --memory-mib 2048
```

The builder verifies the local symbolic inventory, copies a headless Python3.12
stdlib, SWI/Janus, YAML and pinned PeTTa/Omega sources, resolves trusted native
libraries, and builds a fresh initramfs. GUI Tk, site-packages other than YAML,
tests and caches are omitted. Every archive entry is inventoried. Guest immutable
runtime files are root-owned readable/executable; runtime directories are
traversable by UID1000. `/home/roko` is UID/GID1000 mode0700 and `/tmp` mode1777.
No model weights, inference binary, COSMIC or disk persistence are included.

Guest PID1 drops all saved UIDs/GIDs, supplementary groups and privilege gain,
verifies root regain fails, and execs Python's child-only seccomp network-denial
wrapper before SWI. The actual Prolog/Janus probe verifies UID/GID1000 again,
evaluates PeTTa arithmetic, imports Omega utility/loop/provider code, and creates
an Omega message object. It does not start the autonomous loop or call a model.
A successful symbolic gate additionally requires exactly one native import marker,
the matching build completion marker, normal poweroff and a reaped QEMU child.
The2 GiB guest budget has an additional2 GiB host headroom check and60-second
outer deadline. This small guest is not a memory qualification for model inference.

## Actual attempts

- Baseline minimal non-root boot passed (6.33 seconds).
- Five trial/fallback boots passed their expected outcomes: three injected health
  failures, good fallback, and a confirmed healthy trial.
- Symbolic build001 refused an unresolved Tk dependency; no VM launched.
- Symbolic boot002 failed to exec Python after the non-root drop because private
  host staging modes had become guest root-owned0700 directories. Evidence retained.
- Build003 corrected guest modes. Symbolic boots003 and004 passed actual native
  execution (24.30 and26.21 seconds);004 also used the explicit symbolic marker gate.
- The100-test distro suite passed after the changes.

See `VM_VALIDATION.json` and the checkpoint archive for hashes and raw receipts.
No inference, full conversation exchange, COSMIC session or production firmware
recovery is claimed by these minimal tests. Those integrations remain open.
