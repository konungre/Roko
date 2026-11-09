# Parent coordination: conversational guest binding

Observed conversation-owner commit: `b017853` on `dev/ai-openai`.
Read its `components/conversation/PARENT_HANDOFF.md` at that immutable commit.
No other workspace was edited, no endpoint was switched and no host-native
qualification is relabeled as a guest result.

The currently qualified endpoint is `recovered_server.py`, not baseline `run.py`.
It is a foreground, persistent JSON-lines process owned by its desktop parent.
Request: `{"text":"...","context":[]}`. Response has exactly `text`,
`context_ids`, `executed_actions`; `executed_actions` must be zero. Replies remain
unverified model text. Startup/runtime error or cancellation ends the session;
no silent replay, history truncation or background restart is allowed. The owner
states four exchanges per session, 64 generated tokens, a 180-second desktop
budget and no durable history/CAS/idempotency.

Parent decision/input required before activation in the guest:

1. Supply a guest-qualified immutable closure for matched SWI/Janus/Python 3.12,
   Omega/PeTTa, ECAN, native model supervisor and model assets. The preserved
   COSMIC capsule uses Python 3.13 and the older bounded Granite provider; paths
   and ABIs cannot be substituted. The host endpoint contains external workspace
   paths and verifies its own fixed host manifest.
2. Keep the foreground process under the unprivileged companion identity and
   owned lifecycle/cgroup, or define a reviewed per-user IPC broker to a dedicated
   model account. The inactive `roko-model.service` is not compatible with the
   current parent-watched stdio endpoint as-is. It must not be enabled as a shortcut.
3. Preserve no-network enforcement, source/model hashes, bounded cancellation
   and cleanup. Adopt a guest-specific memory budget justified by the selected
   closure; the host profile requires 7 GiB free at startup and its own 4 GiB
   running floor. The current 3 GiB desktop persistence VM cannot run that profile.
4. The new persistent XDG-state mount stores only a qualification checkpoint.
   Do not persist/replay the four-turn in-memory history and call it durable
   conversation. Durable history, migration, request IDs and CAS remain with the
   conversational/memory owners and need an explicit shared schema.

Foundation side ready for integration: non-root COSMIC identity/evidence checks,
read-only application/model closure, private per-user XDG state, descriptor-bound
regular-file test storage, and fresh bounded VM/evidence paths. Actual results
and failed attempts are recorded separately in SESSION_VALIDATION.json when run.
