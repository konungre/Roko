# Independent minimal guest qualification

This path does not use or replace the inaccessible ISO. It uses a freshly acquired
Debian kernel and QEMU/SeaBIOS in a workspace directory. No package installation, maintainer script, host disk, network adapter or KVM is used. The firmware test below writes only its private virtual NVRAM file. The historical ISO runtime lock stays unchanged.

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


## Virtual UEFI fallback

`distro/update/firmware_trials.py TOOLS RUNTIME LOCK GOOD BAD NEW_OUTPUT`
creates a disposable GPT/FAT32 ESP and private OVMF variable store. QEMU boots
OVMF and systemd-boot from those images, without direct kernel injection.
The trial entry starts with three attempts. Three deliberately unhealthy boots
rename it to `+2-1`, `+1-2`, then `+0-3`; the fourth boot actually executes the
known-good entry. The executed test passed all four boots and left the firmware
code image unchanged. This follows [systemd boot assessment](https://systemd.io/AUTOMATIC_BOOT_ASSESSMENT/).
The GPT test verifies both header CRCs, table CRC, bounds, private file mode and
refusal to overwrite an existing image. Firmware package pins accompany the
checkpoint. Secure Boot, production installation, successful trial blessing and
physical power loss remain untested.

## Bounded real model guest

The new `build_conversation_guest.py` and `run_conversation_guest.py` are explicit
integration tools. They require conversation checkpoint
`55bebd8d79454c765b258b27471ad54a971700e5` and the separately rebuilt symbolic and
inference runtime. No component source or weights are vendored by this branch.

The guest runs one empty-context request as UID/GID1000 through the existing
network-denial wrapper and conversation endpoint. A pinned Granite Q4 model and
source/profile are attached on separate read-only virtual disks, mounted with
`nodev,nosuid,noexec`; the executable runtime remains in the initramfs. Root
regain is denied. UUID and ext4 magic checks precede mounts. The builder includes
CRC32C's crypto driver explicitly because ext4 requests it dynamically and it is
absent from ext4's static module dependency list.

The runner admits 10 GiB guest RAM only with 12 GiB host availability, limits
QEMU RSS and output, uses a 600-second outer deadline, and reaps the VM. Existing
conversation/inference limits remain unchanged. A pass requires the actual native
receipt, zero action execution, unchanged model identity and normal guest shutdown;
booting alone cannot pass. No COSMIC session or conversational UI is exercised. The ext4 fixtures are measured local test images; their filesystem timestamps mean byte-for-byte disk reproduction is not yet qualified.
See `MODEL_GUEST_VALIDATION.json` for the actual result and retained failed attempts.

Actual model attempt002 mounted both read-only disks and reached UID/GID1000.
The genuine native inference supervisor started, but no completed conversation
receipt arrived before the driver's 480-second deadline. The guest reported
child failure; the outer runner reaped QEMU. The gate failed, and no model
conversation success is claimed. Attempt001's missing-CRC32C failure is retained.
The TCG-only environment does not establish consumer CPU performance; this test
needs repetition on an authorized accelerated guest before desktop integration.

## Private state across cold boots

`persistence_guest.py CAPSULE RUNTIME LOCK TOOLS NEW_OUTPUT` reuses the verified
model capsule's Python and kernel modules for a storage-only test. It creates a
new private 64 MiB ext4 image, attaches only that disposable disk, and boots twice.
The first boot writes and fsyncs a UID1000 mode0600 JSON file; the second verifies
its exact contents and ownership. Both cleanly unmount before poweroff.
Attempt001 caught the formatter's root-directory mode0755 after mounting.
Attempt002 explicitly sets mounted-root ownership and mode0700 and passes both
boots. Raw receipts are in `persistence-evidence/`. No COSMIC, model response,
crash consistency or physical power-loss claim follows from this test.

With `--crash-recovery`, five actual guest launches check an interrupted update
to this private state fixture. After the first committed value, the non-root
writer fsyncs a replacement temporary file and its directory. The host kills
QEMU at that marker, without guest shutdown. The next boot performs ext4 journal
recovery and verifies both the old committed bytes and the durable temporary
bytes. A fourth boot atomically renames and fsyncs the directory; a fifth checks
the new committed bytes and absence of the temporary file. All five expected
outcomes passed; raw crash evidence is preserved. The mount now also uses
`noexec`. This tests a stopped emulator against host-backed storage, not physical
cache power loss, production releases, or conversation history schema recovery.

Direct inspection of the transferred COSMIC capsule finds configuration assets
but no COSMIC executable. Its desktop depends on the unavailable ISO/runtime.
This independent storage test does not imply a fresh COSMIC session has run.

After all guests exit, the harness additionally opens the regular state image
read-only and runs bounded `e2fsck -f -n`. A run passes only if fsck exits zero
and the image hash stays unchanged. The retained crash-001 image passed all five
fsck passes with zero errors; its SHA256 still matches the guest recovery receipt.
See `persistence-evidence/crash-001-offline-fsck.json` for the actual checker output
and checker binary identity.
