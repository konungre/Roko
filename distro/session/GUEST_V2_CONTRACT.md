# Guest bubble/Omega v2 integration contract (proposed, not guest-qualified)

The authoritative wire schema is components/conversation/DURABLE_API.md.
The parent must supply the bubble handoff commit, endpoint commit, runtime file
manifest, model hash and guest-native probe receipts before binding a desktop.
Do not reuse an old v1 or Python3.13 profile for the Python3.12 Janus closure.

## Fixed guest bindings

- Immutable generation: /opt/roko/runtime and /opt/roko/source, root-owned,
  read-only. Guest-specific trusted profile: /etc/roko/conversation-profile.json.
- Read-only model volume: /opt/roko/models; exact pinned model/closure hashes.
- Private persistent user volume: /home/roko/.local/state, UID/GID1000 mode0700,
  mounted nodev,nosuid,noexec before launching any user process.
- Trusted history binding: ROKO_HISTORY_DB=/home/roko/.local/state/roko/history.sqlite.
  Parent directory UID1000 mode0700; retain SQLite database/WAL/SHM together.
  No caller-selected path and no two independent writers outside the v2 owner protocol.
- Trusted runtime binding: ROKO_FRESH_PROFILE=/etc/roko/conversation-profile.json.
  Profile paths must name guest files whose bytes and ABI have been checked.
- Bubble and foreground durable_server.py run UID/GID1000 with no supplementary
  groups, no_new_privs and inherited no-network enforcement. Transport is owned
  stdin/stdout JSON-lines; diagnostics go to bounded stderr. No shared public socket.

## Lifecycle and qualification

Keep parent lifetime binding and descendant cleanup. Serialize requests; adopt
API2 session/request IDs, expected_revision and exact saved replay semantics.
Use the documented 180-second client per-turn budget plus separately measured
initial verification, preserving the native 150-second deadline. Admission must
measure guest available memory and disk against the endpoint's current limits;
the old 3GiB desktop VM is insufficient. No hidden timeout expansion or retry.
Explicit recovery requires the old owner dead; cancellation cannot auto-replay.

Required real guest sequence: launch COSMIC and bubble; complete a native v2
turn; stop the endpoint; restart it against the same persistent history; replay
the same request without a new model call; continue at the saved revision; reboot
and repeat the snapshot/replay check; test cancellation/recovery and generation
rollback with history schema compatibility. Record source/model/profile digests,
UIDs, process cleanup, CAS revisions and native call counts. No new response or
history may be synthesized to pass this sequence.

Current blockers: COSMIC executable/runtime absent from the transferred capsule;
ISO access remains denied. Earlier minimal model guest exceeded its deadline.
The bubble handoff is on another executor and has not been supplied here. The
native v2 MORK/ECAN/NARS runtime closure is not yet bound to guest-local paths.
OS package-state facts and conversational history are separate schemas; no
AtomSpace fact grants permission to activate a generation or execute model text.

## Relayed bubble handoff requirements

The parent relayed endpoint commit0493700, GTK3/PyGObject/cairo GI bridge,
GTK layer-shell and COSMIC layer-shell. Preserve that pin as a requested handoff,
not proof of compatibility with the newer integrated conversation endpoint in
current main. Confirm exact bubble/source/profile digests and jointly selected
endpoint before building the image. ROKO_FRESH_PROFILE must be guest-qualified
for the selected PeTTa/ECAN/Granite closure; ROKO_HISTORY_DB stays private and
persistent. Use SQLite's backup API for history transfer, not a live database
file copy. Persist XDG_STATE_HOME or supply --session-selection-file; omit
--conversation-session on normal restart so saved selection is recovered.

Before preflight, the parent must provide a shared image build ID and SHA256,
complete runtime inventory, selected endpoint/bubble commits, and state schema.
Then qualify actual guest recall/replay and cancellation/recovery. No image
identity is assigned here because the complete image inputs are not available.
