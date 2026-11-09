# COSMIC session and private XDG-state qualification

This opt-in derivative uses the actual preserved non-root guest034 capsule,
SHA256 `1b969946ea941564b91dd8438d4b870586675ab9a479bc06c99094f0de180116`.
The unchanged ISO/root/model remain read-only. No existing workspace or image is
updated, no host disk is attached, no NIC is enabled, and no model request is sent.
This is a development qualification harness, not an installer or production init.

## What changes inside the guest

The builder patches four precisely anchored source files and adds one fixed
helper. It preserves all other archived file contents and metadata, compiles the
changed Python sources for syntax checking, and reads back the complete derived
archive. A mismatched capsule or non-unique source anchor fails closed.

Guest PID1 validates a fixed test ext4 UUID on `/dev/vda`, mounts it under `/run`,
and binds a private UID1000 directory at `/home/roko/.local/state`. Both mounts
must be nodev,nosuid,noexec. This mapping is for the harness's single virtual disk
only; it is not a physical-device discovery policy. The existing request-working
state at `/var/lib/roko/live-requests` remains volatile. Home/config/cache remain
volatile. User production account allocation and encrypted storage are unresolved.

The existing UID1000 evidence process performs the fixed checkpoint write/read
only after the full inherited process/device/mount/IPC snapshot succeeds. Writing
uses an exclusive, non-following open, fsync(file) and fsync(directory). Reading
checks exact bytes, regular-file type, UID/GID1000, mode0600 and a single link.
PID1 independently checks the result and emits a bounded receipt. No model answer,
conversation history or arbitrary user path is used as a storage fixture.

The original immutable-root/model protection, zero-capability/non-root checks,
private directories, cgroup ownership, seatd exception and two-sided IPC identity
checks remain in force. The extra mounts are added to the exact mount schema,
and both guest and host validators require their restrictive flags. Startup
failures remain failures. The diagnostic successor emits only bounded tails of
four fixed role logs; it does not restart roles or weaken startup checks.

## Host safety and resource bounds

`state_image.py` creates only a new 64 MiB mode0600 singly-linked regular file in
a private canonical directory. It verifies all 403 preserved filesystem-tool
entries before formatting through a held FD; initial read-only e2fsck must pass.
Attachment holds an exclusive flock for the full VM lifetime. Symlinks, hardlinks,
nonprivate locations, wrong sizes and existing create targets are rejected.

`run_session.py` verifies all 7,759 restored QEMU/kernel entries and the exact ISO
and capsule hashes. ISO and capsule are held read-only; the state image is the
only writable guest disk. The explicit desktop-only budget is 3 GiB/4 TCG CPUs,
6 GiB host prelaunch availability, 2 GiB running host floor, 4 GiB QEMU RSS ceiling,
390 seconds, 2 MiB serial output, and at least 4 GiB free disk plus evidence reserve.
The earlier 4 GiB plan refused launch when its 7 GiB headroom was unavailable.
This smaller gate is not a model-memory qualification or the 32 GiB hardware target.

The runner checks startup/state evidence independently and captures at 30, 60, 90 and 120 seconds after readiness,
within the same outer deadline.
An image must be visually inspected separately. A ready marker is not a screenshot
pass. QMP Quit then deliberately stops the VM: there is **no clean guest-unmount
claim**. This tests cold restart after committed user writes and possible journal
recovery, not exhaustive power-loss behavior. The runner owns/reaps its QEMU child.
No production shutdown, lockscreen, input interaction or lifecycle retry is proved.

## Reproduction

```sh
python3 -B -m unittest discover -s distro/tests -v
python3 -B distro/session/derive_session.py PRESERVED_GUEST034 NEW_CAPSULE_DIRECTORY
# Create state with state_image.create(NEW_PRIVATE_DIRECTORY, FORMATTER_ROOT,
#                                 ORIGINAL_FORMATTER_FILE_LOCK).
python3 -B distro/session/run_session.py CAPSULE_DIRECTORY QEMU_ROOT QEMU_LOCK ISO STATE_DIRECTORY NEW_WRITE_EVIDENCE write
# Preserve a verified post-write image snapshot after the owned QEMU exits.
python3 -B distro/session/run_session.py CAPSULE_DIRECTORY QEMU_ROOT QEMU_LOCK ISO STATE_DIRECTORY NEW_READ_EVIDENCE read
```

External ISO, native/model/artwork bytes and original runtime inventories are not
published by this source commit. Their preserved local copies are required.
Locks are reviewed local provenance, not a new signed update trust chain.
Runtime files and locks must remain trusted and unchanged throughout execution.

## Measured results and interface ownership

See `SESSION_VALIDATION.json` for current outcomes, including failed attempts.
The first write gate passed actual non-root startup and committed the checkpoint;
its immediate screenshot showed only boot console. The first read gate mounted
and recovered the ext4 journal but stopped on WirePlumber exit69 before complete
startup. Read-only debugfs subsequently verified the exact checkpoint bytes,
UID/GID1000, mode0600 and one link. A diagnostic successor preserves those facts
and uses an independently restored copy of the post-write image.

See [CONVERSATION_INTERFACE.md](CONVERSATION_INTERFACE.md) for the parent handoff.
The new host-qualified conversation endpoint requires a new matched guest closure;
it is not silently copied into the Python3.13 guest. Durable conversation history
and model activation remain separate integration work.

## PipeWire ordering correction

The diagnostic read005 boot reproduced WirePlumber exit69 and retained its actual
`Failed to connect to PipeWire` diagnostic. The inherited supervisor launched
PipeWire, WirePlumber and COSMIC back-to-back. The successor starts PipeWire first
and waits at most30 seconds for its real Unix socket, requiring UID/GID1000 and
SO_PEERCRED matching the owned PipeWire PID. It continues draining the original
control/evidence loop, aborts on lifecycle transitions or child exit, and starts
WirePlumber/COSMIC only after readiness. Wrong credentials fail immediately. No
role is retried, realtime privilege granted, or host/service setting changed.
Five pure tests cover transient absence, wrong peer, dead role, control transition
and timeout. Actual successor results are separate in SESSION_VALIDATION.json.

A successful serial startup/state result never certifies the complete visible
desktop. The read004 capture showed only a dark compositor surface and cursor.
The extended render attempt read005 failed before capturing. Both observations
remain preserved. The final readiness-fix run must be evaluated on its own evidence.
