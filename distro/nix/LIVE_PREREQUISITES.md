# Read-only live-image prerequisite audit

No PR description update was retried; approval for that action remains pending.
These independent checks issue only derivation-show and eval commands, offline
with IFD disabled. No build, package copy, installation, activation or boot occurs.

The union recursive graph has6819 declared derivations. From the headless ISO,
3790 derivations are reachable and3977 requested output pairs are absent locally;
from COSMIC,6764 derivations and7064 requested output pairs are absent. The audit
follows inputDrvs output selectors rather than count every unused debug/dev output.
This is a SOURCE-BUILD graph including bootstrap/fetch derivations, not a runtime
package count, required download size or realized closure. No binary substituters
were queried. A trusted cache could satisfy build inputs in an appropriate store;
its availability/signatures and logical store-prefix compatibility remain untested.
Do not rewrite paths or disable signature checks to accommodate this workspace.

Raw graph metadata (39,533,717 bytes) stays in the workspace; its SHA256 and command
are committed with bounded summary receipts. `audit_derivation_graph.py` repeats
the read-only analysis on that JSON plus the resolved image identities. Tests
verify requested-output counting, explicit incomplete metadata and refusal to
overwrite an existing report. The OS suite passes104 tests after this addition.

Resolved configuration observations (not runtime tests):
- Kernel version6.18.62, EFI/BIOS image options enabled, ISO volume ROKO_LIVE_EVAL.
- Initrd declares AHCI/NVMe/USB/ISO/squashfs/overlay support. Actual boot media
  attachment, virtual/physical driver coverage and firmware still require boots.
- Root is tmpfs; store uses squashfs/overlay; no persistent /home mount is declared.
  User/history data is therefore not qualified durable. Do not copy real data into
  this candidate expecting persistence, and do not attach a host disk as a shortcut.
- Redistributable firmware policy is disabled. COSMIC enables graphics and
  NetworkManager; headless does not enable NetworkManager. DHCP flag is false.
  This does not prove Intel iGPU, network access, audio/input or device compatibility.
- Root and normal-user password login, SSH and sudo are disabled. Fixture public
  keys satisfy one assertion, not a usable secure administration channel. Actual
  provisioning/maintenance/recovery remains a release gate.
- The first query of boot.initrd.systemd.enable failed because that option was
  removed in the pinned source. The corrected read-only query omits it; no system
  option or lockout safeguard was changed to force evaluation success.

Next prerequisites: a disposable strict-sandbox-capable executor; verified cache
or source/toolchain realization with correct store prefix; independently repeated
ISO build, boot/health/recovery; explicit persistent-volume and guest-native
bubble/Omega/model contracts; physical hardware qualification and licensing review.
The current namespace blocker, denied historical ISO transfer and unresolved
legacy-source licensing remain unchanged. No readiness or redistribution clearance.
