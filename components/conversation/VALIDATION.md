# Fresh host validation — 2026-11-09

- 16 source contract tests pass. All conversation Python sources parse.
- Native attempt 001 failed before model inference because PeTTa compiled the step
  before provider definitions were imported. Empty history and unchanged model
  were preserved; the failed receipt was not replaced.
- Native attempt 002: two real free-form turns through the native Omega step and
  actual provider registry. Generic Granite inference took 43.720s and 60.024s.
  Follow-up correctly recalled the lighthouse setting. Both child cleanups passed.
- Native attempt 003: actual native ECAN followed by actual Granite conversation;
  ECAN 0.431s, model 41.044s. ECAN process group empty, native inputs postverified,
  and model verified before assistant history commit.
- Native attempt 004: five symbolic records, four native focus selections; the
  unrelated shopping-list record was excluded. Code-like user text remained text.
  The 64-token reply was incomplete; this is recorded as a quality/budget limitation.
- Actual desktop chat-bubble-v3 headless transport: first attempt exposed a
  parent-thread death binding bug after one reply. A process-identity watcher fixed
  it. Successor completed two replies in one session, including “You mentioned a
  lighthouse.” No GUI test is implied.
- Cancellation through that same desktop transport during native inference: callback
  returned no answer and `Turn cancelled; session ended`. Before cancellation the
  owned native group contained supervisor and inference processes; afterward the
  observed group was empty. This establishes that observed cancellation case, not
  transactional rollback or exhaustive crash containment.

Native runs used inherited network denial, matched restored SWI/Janus/Python,
verified native library resolution, fixed runtime token/resource caps, unchanged
model hash/identity and the existing cleanup supervisor. Original assets were not
modified. The symbolic gateway verified the original 1,722-input manifest before
and after completed native proofs. All 29 saved host-profile source hashes matched.

`NATIVE_SUMMARY.json` contains compact counts and receipt hashes. Full private/local
proofs are retained outside Git in the `conversation-native-recovery-*` directories.
The final desktop response is exactly text/context_ids/executed_actions, compatible
with the desktop transport. Replies are unverified model output, not verified facts.

Remaining: four-exchange in-memory sessions only; no CAS/idempotent durable store,
MORK projection, MetaMo/learning integration, guest deployment, graphical UI tests,
or broader quality qualification. The unchanged full autonomous `(omega)` loop is
not executed. No network service, external action, installation or push occurred.
