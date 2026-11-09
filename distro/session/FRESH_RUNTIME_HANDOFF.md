# Fresh executor integration handoff

The authorized transfer was verified against all 60 CHECKSUMS.json entries and
Git commit `209ec3cab14b13a2bc06764dfa170614ed26fc80`, then merged without losing
fresh build work. Recovered capsules and state snapshots remain unchanged.
This document records available inputs and concrete requests through the parent.

## QEMU and kernel restoration

The complete runtime lock is available in the recovered transfer at
`locks/qemu-runtime-files.lock.json`, SHA256
`fe48b5a9d308be97501d0833a63cc86175958e1b066cf5785e2d2ce4aba3a230`.
It covers 7,759 entries. The runtime itself is not in the transfer.
Required selected file identities are:

| Path | SHA256 |
| --- | --- |
| `usr/bin/qemu-system-x86_64` | `d3c1a558ad220e77a4412048c8d96b44f8c2b41c7ad2a4ecfe522a4b122fe067` |
| `usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2` | `c8438e4fde1934e61c88311633f00949ff645d5c04cdb8671fa3d78164d2f307` |
| `boot/vmlinuz-6.12.115+deb13.1-amd64` | `96758c40859c94163e5cf81399a107d679e984e251cb4e13aba4e7d92f5d14f2` |
| `usr/share/seabios/bios-256k.bin` | `fc6d2ea888862e6b26d53fb877ab712324726eb8f44eb6baf076c64a31f1c3fb` |

The repository's `omega-baseline/boot/acquire-tooling.py` names official Debian
and Debian-security snapshot `20261103T013555Z`, but its required
`tooling-packages.lock.json` is omitted. Package documentation names in the file
lock identify Debian runtime families, not exact package versions or URLs.
Do not regenerate a different lock and call that restoration. Request the original
package lock and archive set, or the complete extracted runtime matching the
existing inventory. Verify every entry before launching the recorded runner.
A newer separately qualified runtime would need its own evidence lineage.

ISO004 identity is known: 7,516,768,256 bytes, SHA256
`a3cc3cb741f50b2bd1846080bb1995067f22a27fc79091fc3e63ef4162c31253`.
All twelve matching parts, manifest and reassembler were located in Library.
The prescribed download helper returned HTTP401 before downloads. That operation
has stopped; no alternate access route or ISO reconstruction was attempted.

## Conversation owner request through parent

Please provide an immutable source/runtime handoff for the currently selected
conversation endpoint, identifying its commit, entrypoint, input/output schema,
exact dependency/model hashes, and guest qualification status. The inherited
interface names `recovered_server.py` at `b017853`; it must not be assumed current
without the owner's handoff. Required runtime closure includes matched
Python3.12/SWI/Janus, PeTTa/Omega, ECAN, model supervisor and model assets.
Guest source inspection confirms the existing supervisor launches its fixed
roles via `/usr/bin/python3.13`; it cannot load a Python3.12 extension by changing
an import path. External host absolute paths are not guest bindings.

Proposed foundation binding remains foreground stdio under the existing
unprivileged companion lifecycle, with no autonomous actions, no network, bounded
output/cancellation, and no retry/replay after failure. The inactive dedicated
model service is not enabled. A changed IPC/broker architecture must be reconciled
with both owners before implementation. Preserve the endpoint's four-exchange,
64-token, 180-second contract until superseded by an explicit owner revision.
The 3 GiB desktop VM budget cannot support the inherited 7 GiB free-at-start
model contract; provide a tested guest memory budget and closure before inference.

The persistent XDG fixture is not conversation history. Durable history schema,
CAS/idempotency and migration remain explicit interfaces with the memory owner.

## Independent new checks

The fresh suite additionally exercises the inherited PipeWire peer checker using
actual non-root UID/GID1000 Unix sockets and kernel SO_PEERCRED. It accepts the
owned process and rejects another same-user process, a dead listener and a
symlink. Only the guest socket path is relocated for these tests. This is a host
boundary test, not a PipeWire daemon or desktop boot qualification.

## Conversation checkpoint received

Commit `55bebd8d79454c765b258b27471ad54a971700e5` and its complete bundle were
verified against the supplied transfer manifest, along with all 51 handoff files.
The component was merged without altering its sources. Current fresh-host
endpoint is `fresh_server.py`, selected by `ROKO_FRESH_PROFILE`; this supersedes
the inherited `recovered_server.py` recommendation for a newly rebuilt profile.
The fresh profile supports empty context only; nonempty ECAN context remains
explicitly unavailable. See `components/conversation/FRESH_HOST.md` for lifecycle,
resource and transport limits. Producer absolute paths and profiles are retained
as provenance and are not admitted as consumer runtime bindings.

A new local symbolic rebuild uses the supplied unmodified recipe and historical
source lock, with a consumer-local root. It verifies 208 PeTTa and 330 Omega source
files before building SWI10.0.2/Janus against Python3.12. A new local profile and
native import probe are required after compilation; neither inventory generation
nor source merge is a model/guest result.

Local rebuild completed and qualified at
`/workspace/scratch/roko-symbolic-local-001`: SWI10.0.2, embedded Python3.12.14,
538 matching source files and 1,140 locally generated runtime inventory entries.
Normal and child-seccomp-network-denied probes passed actual PeTTa arithmetic,
Omega utility/loop/provider imports and creation of an Omega message object.
A separate socket probe confirmed network denial. All26 conversation tests now
pass without skips, including the real Prolog bounded reader. The profile remains
an inventory-only artifact; `LOCAL_SYMBOLIC_VALIDATION.json` separately records
native probe outcomes and evidence hashes. No model inference, autonomous loop,
ECAN context or guest integration was executed by this qualification.
