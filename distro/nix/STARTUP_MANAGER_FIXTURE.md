# Actual service-manager diagnostic fixture

Two bounded QEMU TCG boots passed the startup diagnostic sequence under actual
Debian systemd 257.13 PID1. The final run completed in 19.19 seconds, powered off
normally, returned zero and was reaped. No network device, host disks, KVM, GUI or
host services were used. The existing minimal kernel/QEMU runtime's 131-entry
lock was verified before launch. Source, initramfs, runtime-lock, manifest and
serial hashes are preserved in `../integration/evidence/startup-manager-001/`.
The guest image and full runtime inventory remain local, not redistributed.

This is an **adapted service-manager fixture**, not the pinned Nix image or its
systemd 262 package. The fixture copies trusted existing host systemd/native
libraries and a local Python runtime into an initramfs. It uses the evaluated
headless/offline unit text, preserves diagnostic hardening settings, replaces
unrealized Nix executable paths with fixture-local binaries, removes unavailable
Nix environment paths and adds guest Python/console output configuration. Minimal
fixture targets replace the full boot target graph. Early proc/sys/dev/run/cgroup
mounts exist only inside the VM. No host sandbox, mount, sysctl or service settings
were changed. No image closure, full boot ordering or systemd-version parity is
established by this adapted runtime.

The guest controller exercised real systemctl jobs over the guest PID1 private
bus, not mocked subprocess responses:

1. With no model asset and no usable external connection in a VM with no NIC, the
   diagnostic service completed active/exited. The report stayed `unqualified`,
   listed absent model/history qualification and unprovisioned credentials, and
   retained `system_ready=false`, `execution_authorized=false`. Requested offline
   isolation still explicitly remained unproven.
2. Invalid policy made the diagnostic service fail and write `status=failed`.
   Its configured OnFailure service actually ran: the controller checked the
   failure service's nonzero execution timestamp and successful result without
   manually starting it. Serial output retains the diagnostic message.
3. Restoring valid policy, resetting the failed unit and starting it again
   recovered to `unqualified` with the same boot identity. Recovery never claimed
   model readiness, persistence health or activation authority.

Systemd debug observations show diagnostic UID/GID 63914 on all three starts,
not UID0. The configured DynamicUser, private-network namespace, strict system
protection and other hardening directives were retained. The guest logged missing
optional libbpf/cgroup BPF facilities; no comprehensive confinement or network
isolation proof is claimed. Absence of a network device is separately bound by the
controller's QEMU command. No real model service, network outage/reconnection,
COSMIC display manager, durable history or package operation was tested.

Initial attempts remain evidence, not successes: the isolated host user manager
refused because the executor was not booted with systemd; the first guest manager
failed initialization; a debug guest then identified the missing systemd-executor
helper and was terminated/reaped. Completing that fixture dependency and early
API-filesystem setup enabled the successful boots. The helper source guard now
refuses ordinary host execution before any systemctl/poweroff action (exit77);
a test actually verifies that refusal. Guest poweroff remains inside QEMU.

Reproduction uses trusted local inputs only and fresh private output directories:

```
python3 distro/integration/build_startup_manager_guest.py <symbolic-runtime> <evaluated-headless-offline.json> <new-guest-directory>
python3 distro/integration/run_startup_manager_guest.py <minimal-runtime> <runtime-lock.json> <guest-directory> <new-evidence-directory>
```

The builder never executes its init or guest controller. The runner verifies the
image/runtime identities before launch, provides 512MiB/one TCG vCPU, limits serial
to 2MiB and elapsed time to 110 seconds, terminates then kills if necessary, and
reaps the child. `startup_manager_evidence.parse` only checks serial consistency;
its fixture tests do not establish native execution. The final actual run binds
that parsed contract to the measured image, runtime and child lifecycle.

The full OS suite passed 118 tests, including host-controller refusal and rejection
of misleading serial status/identity/authority claims. Full declarative image
realization and boot, systemd 262 execution, actual desktop target progress,
physical hardware, model/history integration and daily-driver readiness remain
unqualified. Licensing/notice limitations, draft PR #22 and pending metadata
approval remain unchanged; legacy defaults are untouched.
