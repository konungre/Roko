# Userspace boot-trial journal

This is a durable protocol prototype for a future boot adapter. It does not write
slot images, boot entries, firmware variables or a TPM counter. Tests use private
regular files and synthetic slot descriptors; none boot a machine.

`Journal` requires a canonical owned mode0700 directory and a private singly-linked
mode0600 lock/state file. Its exclusive flock serializes writers; expected revisions
reject stale requests. Transactions write a unique temporary file, fsync it,
atomically replace state.json and fsync the directory before returning. An orphan
transaction is ignored; a corrupt committed journal fails closed and cannot be
reinitialized. Preserve interrupted files for inspection.

States retain one confirmed `good` descriptor and at most one `trial` on the other
slot, with a strictly greater release sequence. Arming grants three attempts.
Selecting a trial durably decrements its budget and assigns a fresh nonce before
returning its descriptor. Confirmation must present the active nonce; older
attempts cannot confirm a newer boot. After three unconfirmed selections the next
selection clears the trial and returns the unchanged good descriptor. Abort also
preserves good. Only successful confirmation advances the confirmed sequence.

`arm_staged.arm(journal_directory, staging_directory, trusted_public_key,
expected_revision)` connects the previous signed staging gate to this protocol.
It holds the journal lock while reauthenticating staging, derives the minimum
sequence from the confirmed release, and selects the inactive slot itself.
Corrupt staging, replay, existing trials and stale revisions are rejected.
The candidate digest identifies the signed release archive, not an installed slot.

The lower-level journal methods are trusted controller primitives. They do not
independently authenticate candidate payloads or prove health. A production boot
adapter must protect this journal from model/user writes, authenticate installed
slot contents, bind a nonce to the actual boot, independently establish health,
provide durable authenticated rollback policy, and test interruption around all
slot/bootloader writes. It must not treat the returned `selected` descriptor as
proof that installation or boot occurred. No automatic cleanup/reset or implicit
first-boot trust is provided.

Validation: three-attempt fallback, current/stale confirmation nonces, wrong slots,
downgrades, stale revisions, exclusive writers, corrupt state, and interrupted
transactions. A subprocess really exits after state publication; reopening sees
one consumed trial attempt and the original good slot. Signed integration tests
use actual Ed25519 signatures and reject modified candidates. Process crashes on
this host are not evidence of physical power-loss atomicity or firmware recovery.
