# Pinned COSMIC startup and offline session diagnostics

Source inspection used nixpkgs `f4a03c008967841f2a0b3cb7c436fc6fc31671f6` and
COSMIC session epoch-1.11.0, resolved from its annotated tag to
`4b0a0a24e98b9e755b6a7146e4cb29539cacda0a`. Selected source hashes/immutable URLs
are in `../integration/evidence/cosmic-ordering-001/source-audit.json`. The full
COSMIC archive NAR was not verified against the nixpkgs fetch hash this turn;
selected-file inspection is not source-closure or build qualification. Upstream
raw code was not copied into this repository.

## Actual source-level dependency findings

The pinned [COSMIC NixOS module](https://github.com/NixOS/nixpkgs/blob/f4a03c008967841f2a0b3cb7c436fc6fc31671f6/nixos/modules/services/desktop-managers/cosmic.nix)
provides the session package and enables local graphical dependencies including
D-Bus-related services, dconf, accounts, polkit/rtkit, portals, input and power
services. Graphical-desktop defaults include PipeWire. Its optional defaults also
enable NetworkManager, Avahi and GeoClue. Removing core COSMIC packages is not a
supported way to create an offline desktop; this change preserves them.

The pinned greeter module enables greetd; greetd aliases display-manager.service
and follows systemd-user-sessions/getty/Plymouth ordering. The existing system
boot-policy diagnostic already orders before that alias; it now also names
greetd.service explicitly. This is not a new login or authentication mechanism.

The upstream [session target](https://github.com/pop-os/cosmic-session/blob/4b0a0a24e98b9e755b6a7146e4cb29539cacda0a/data/cosmic-session.target)
binds to graphical-session.target, orders before it, and includes graphical-pre
and XDG-autostart target relationships. The [session manager source](https://github.com/pop-os/cosmic-session/blob/4b0a0a24e98b9e755b6a7146e4cb29539cacda0a/src/main.rs)
receives compositor environment and starts the settings daemon before requesting
its systemd target. The helper uses a nonblocking target start and stops it on
session teardown. This is a source-level launch contract, not measured compositor,
settings-daemon, portal or interactive readiness. Complete Wayland/D-Bus environment
availability in the user manager is not assumed or repaired by importing all env.

## Opt-in declarative configuration

When enableCosmic=true, the live candidate adds a **user** diagnostic service via
`cosmic-session-ordering.nix`. It is wanted by and runs after cosmic-session.target,
with PartOf on that target so old diagnostic lifetime follows session teardown.
DefaultDependencies=false avoids complementing the wanted diagnostic into an
unintended target readiness barrier. There is no Requires/Wants dependency on AI,
models, network-online or history, and no model restart/activation in the program.
Restart=no and a 10-second limit prevent retry storms. These declarations do not
prove runtime job transactions in the real graphical session.

`offline-startup.nix` now explicitly disables Avahi discovery and GeoClue in the
offline policy, overriding COSMIC's optional defaults. It retains the prior
channel/registry/substituter and network-online-waiter restrictions. NetworkManager
and DHCP remain controlled by the existing live policy. Managed mode does not
apply this offline override. Local desktop/audio/authentication/portal dependencies
are not removed. This is offline-first configuration, **not** a firewall or proof
that all desktop apps/autostarts cannot make network requests.

## Read-only, private user diagnostics

`cosmic_session_report.py` observes only environment labels, canonical private
UID-owned XDG_RUNTIME_DIR and non-symlink socket inode ownership/type. It accepts
only a basename Wayland socket and the local runtime bus path. It never connects
to either socket, queries a bus, starts a compositor/provider or executes input.
Missing labels/sockets produce incomplete, not a fallback session. Raw environment
values and bus addresses are not logged. Owned fake sockets still yield
inputs-observed-unqualified, never interactive_ready or inference_qualified.

The packaged program includes the existing startup and memory helpers. It writes
0600 JSON under the user's 0700 runtime directory, samples the conservative memory
budget and attaches kernel boot and validated systemd invocation identity. Missing
identity remains incomplete. Journal stdout/stderr use roko-cosmic-diagnostic;
write/start failure is a unit failure, not silent success. Preserved old diagnostic
files are not live evidence: consumers must compare current boot/invocation and
current unit state. User-owned metadata is not authenticated authority or an
AtomSpace activation receipt.

The proposed unit uses no-new-privileges, private networking, strict system/read-only
home protection, AF_UNIX-only socket families, group cleanup and the same provisional
64M/96M memory pressure limits. The user-namespace/seccomp/cgroup behavior and
package closure are unqualified. Failure of these settings must not be turned into
a privileged fallback or weaker automatic configuration.

## Checks actually completed

All **138 OS tests passed**. Socket-metadata fixtures cover owned fake sockets,
removal, missing/untrusted paths, symlink rejection, unsupported transport, private
0600 CLI output and no raw-value disclosure. These are not real Wayland/D-Bus/COSMIC
services. No IPC connections or host service activation occurred.

Bounded native Nix evaluation (192MiB address-space/5 CPU seconds/10 wall seconds)
read the actual service fragment using lightweight executable-path arguments. A
mini-schema with the pinned Nix library also evaluated the actual offline override:
Avahi/GeoClue defaults were forced off while fixture accounts/D-Bus/PipeWire/polkit
values stayed enabled. This is **not full NixOS module evaluation**. Native syntax
parsing of live-image-eval.nix also passed against the existing workspace store.
No derivation/image was built or activated.

Native systemd 257 static verification accepted the diagnostic alongside the actual
selected upstream COSMIC target, installed graphical-session target files and
explicit basic/shutdown boundary stubs. The simulated WantedBy link was present.
An intentionally contradictory Before+After target edge was rejected as an ordering
cycle. That negative case tests cycle rejection, not all implicit/default ordering
rules. No user manager or systemd unit was started. An initial static attempt
lacked basic.target; completing the declared graph fixture fixed that prerequisite.

The full policy/startup evaluators are extended to check the new settings on an
appropriately provisioned builder, but those full evaluations have not run for this
revision. Actual manager environment delivery, target progress, journal/JSON output,
COSMIC login/teardown, namespace protection and image realization remain future
gates. Passive admission still rejects a VM and no VM was launched. Guest model
inference and the full Nix/COSMIC image remain unqualified. Preserve legacy defaults,
unresolved licensing/notice gates, draft PR #22 and the metadata approval hold.
