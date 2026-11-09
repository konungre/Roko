# Pinned live-image definition (resolved only)

`live-image-eval.nix` imports the pinned upstream ISO module, not the permissive
installation-CD account defaults. It composes `system-eval.nix` in liveMedia mode,
so installed-system root/home disk labels are not attached. The ISO root is tmpfs,
with upstream squashfs/read-write overlay store layout. EFI/BIOS/USB image flags
are declared; host EFI-variable writes and console/display auto-login stay disabled.

The evaluator's --live-image mode checks unprovisioned lockout and fixture-key
provisioned headless/COSMIC module cases with import-from-derivation disabled.
All option/assertion checks passed. No assertion or sandbox requirement was
weakened. The original installed-system evaluation also passes after refactoring.

`qualify_live_derivation.py NIX_BASE MODULE_EVALUATIONS NEW_OUTPUT` forces only
system/ISO derivation identities, with 4GiB address-space and 120-second limits.
Both headless and COSMIC derivations resolve offline without IFD. Repeating the
same headless input must return identical identities. These are not outputs:
no closure was realized, ISO file produced, VM started or compositor/model run.
A stable derivation identity is not evidence of bit-reproducible built media.

The source pin is the existing nixpkgs candidate, not a production channel policy.
The generated public-key input is a local fixture; its private key is excluded
from committed receipts. Never deploy that key. Root/user password login, SSH and
sudo remain disabled: actual secure operator access/provisioning still needs
review. No unattended unlocked live session is provided as a shortcut.

Missing image/closure work:
- Strict sandbox-capable executor and pinned dependency realization, then actual
  repeated image builds with complete closure and source/binary trust evidence.
- Actual image format, bootloader/kernel/initramfs and non-root COSMIC boots,
  Intel iGPU/firmware, input/audio/network and consumer hardware tests.
- Guest-local matched Omega/PeTTa/Janus/ECAN/model/bubble runtime, persistent user
  and history volume provisioning, schema compatibility and v2 replay/cancellation.
  Current live metadata marks model absent and persistent history unqualified.
- Signed release installation/trial confirmation/recovery and a secure maintenance
  workflow. There is no installer or host activation function in these definitions.
- Resolution/migration of the active legacy package source licensing issue.

Strict sandboxing remains blocked here by missing kernel namespaces; see
SANDBOX_QUALIFICATION.md. No host settings changed and no fallback build was used
for these results. PR22 remains draft; no readiness/redistribution clearance claim.

A subsequent read-only [prerequisite audit](LIVE_PREREQUISITES.md) measures declared
build-output availability and the resolved network/firmware/storage/access gaps.
Those graph counts must not be presented as a realized runtime closure.

[Explicit policies](LIVE_POLICIES.md) now make firmware, networking and operator
access choices parameters, with conservative defaults and negative evaluations.
Earlier graph identities/counts are historical snapshots, not the new policy
combinations. No credential or host service is activated by these definitions.

The [offline closure preflight](OFFLINE_CLOSURE.md) refreshed current identities
and found all four image/system outputs missing; verification/export were skipped.
A separate small fixture successfully tested ordinary local cache export only.
