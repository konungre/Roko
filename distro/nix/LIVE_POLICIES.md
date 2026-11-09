# Explicit live firmware, network and operator-access policies

These parameters change candidate definitions only. No host networking, firmware,
accounts, SSH service or sudo policy is changed by evaluation. All package-source
licensing and strict-sandbox build blockers remain open. No PR metadata retry.

Defaults are firmwarePolicy=none, networkPolicy=offline, adminAccess=locked.
The offline policy disables NetworkManager and DHCP configuration even for COSMIC;
it is NOT a network-denial sandbox or proof that all possible traffic is blocked.
The managed policy explicitly selects NetworkManager, not a tested connection.
No Wi-Fi credentials, persistent connections or host network settings are imported.

firmwarePolicy=redistributable explicitly selects the pinned upstream NixOS
redistributable-firmware policy; enableAllFirmware remains false and unrestricted
'all' is rejected. The aggregate firmware derivation resolves, but firmware packages
have not been realized or tested on Intel hardware. Upstream metadata/policy is not
our own redistribution/license audit; this does not settle legacy-source licensing.

adminAccess choices:
- locked: root/user password locks and disabled SSH/sudo remain. A supplied public
  key can satisfy the upstream provisioning assertion but provides no active
  access channel here. No credential means the lockout assertion remains.
- console-password: requires an operator-provided salted hash (supported prefixes
  y/6), enables password-required sudo for the normal wheel user, and keeps SSH
  disabled. No root password login or autologin is introduced.
- ssh-key-and-password: requires managed networking, an Ed25519 public-key shape
  and a salted hash. SSH is explicitly publickey-only for roko, with root, empty
  password, password and keyboard-interactive authentication disabled. The password
  is for console/sudo; this is NOT a claim of two-factor SSH authentication.

No default password/hash/key is supplied. Qualification generates a strong random
throwaway password, hashes it with the local OpenSSL fixture tool, and generates
a fresh SSH fixture key. No plaintext, hash or private key is committed; error
context is redacted before retention. Real hashes may appear in Nix stores/media,
so secure secret provisioning, strength/format review and actual PAM/SSH/sudo
login tests are still required before deployment. Prefix checks are not password
strength or complete crypt-format validation. Never deploy a fixture credential.

The 11-case live-policy-003 gate passed four valid configuration modes and seven
rejections (missing hash, SSH while offline, plaintext, missing/malformed key,
unrestricted firmware and unknown network). The first audit query expected a list
but pinned hardware.firmware is an aggregate derivation; it was corrected, not
worked around by relaxing source/unfree policy. Actual authorization, device
operation, network service and firmware loading have NOT run or been qualified.

These parameters change image derivation identities and dependency graphs. Prior
closure counts/identities remain historical receipts for their old definitions;
refresh the graph before a future build. Persistent /home/history, full model
closure, secure operator provisioning, strict sandbox build and boot tests remain
separate gates. Keep PR22 draft; no release/redistribution readiness is claimed.
