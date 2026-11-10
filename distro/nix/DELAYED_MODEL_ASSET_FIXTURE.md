# Delayed actual model asset availability

The executor returned after its disconnect. Before retrying any work, the surviving
initramfs and all 675 staged file hashes were verified against the completed
manifest. No build or VM process remained. A private tar checkpoint preserved both
uncommitted source files, init source, manifest and image. The obsolete terminal
session could not be resumed, but the assembly had completed: **no rebuild or
uncertain external action was repeated**. The existing image was then tested for
the first time. Preservation hashes are in
`../integration/evidence/delayed-model-001/preservation.json`.

The real 4,230,976,352-byte model asset was already present in an existing private
5GiB ext4 regular-file guest disk. The runner opened that disk read-only with
O_NOFOLLOW/O_NONBLOCK, required a single-link regular file, hashed the held
file descriptor against the prior model-guest manifest and passed that descriptor
to QEMU with readonly=on. This is a disposable fixture disk, not a host block
device. Its hash after the trial still matched admission. No model download,
replacement, host mount, host service activation or global-state mutation occurred.

Actual Debian systemd PID1 in the adapted guest passed this sequence in 27.92
seconds, then powered off normally; the controller reaped QEMU:

1. Startup diagnostics completed without a visible model path and with no NIC.
   Existing invalid-policy failure/OnFailure/recovery tests still passed.
2. The fixture-only model probe's ConditionPathExists failed, so it was skipped
   without starting an inference process or publishing an asset report. Diagnostic
   startup was never blocked on this optional model service.
3. The guest controller verified the expected ext4 UUID and mounted the admitted
   disk at the model path with ro/nodev/nosuid/noexec and noload. This delays path
   visibility after startup; it is not physical device hotplug. The manually
   started model probe ran as UID64168 and observed a regular file of the exact
   expected size, GGUFv3, 666 tensors and 42 metadata entries. Its start timestamp
   was later than the startup diagnostic's exit timestamp.
4. Stopping the asset probe removed its ephemeral report. Unmounting and starting
   again skipped it without publishing stale availability. Remounting and explicitly
   starting it recovered the same observed asset and ordering.
5. Restarting the policy diagnostic still yielded unqualified/model-not-qualified.
   File visibility never promoted policy or system readiness, granted action
   authority or supplied a fictitious inference-health result.

This is **asset observation, not completed model loading or inference**. The probe
reads the GGUF header only; it does not validate every tensor, execute model code,
or hash the entire model inside the guest. Its report explicitly says
model_sha256_verified_in_guest=false and inference_qualified=false. The host
controller separately binds the complete disk hash to the existing model receipt.
The earlier full real-model TCG conversation attempt hit its 480-second inference
deadline (504.74 seconds including cleanup), and was not repeated here. Completed
non-root guest inference remains a blocker requiring an appropriately performant
qualified runtime, rather than being inferred from file availability.

The optional probe unit is confined to this guest fixture. It has After ordering
on the diagnostic, but neither a startup Wants/Requires edge nor an implicit mount,
network, download or automatic retry. It retains DynamicUser, PrivateNetwork,
strict system protection, no capabilities and a 15-second start limit. The guest
controller is guarded against host execution. Only the guest root fixture mounts
or unmounts its held read-only disk. No production model-manager policy, AtomSpace
authority or Nix image service was added.

Reproduce from trusted existing inputs using fresh directories:

```
python3 distro/integration/build_delayed_model_guest.py <verified-service-manager-guest> <prior-model-guest> <kernel-package-root> <new-guest-directory>
python3 distro/integration/run_startup_manager_guest.py <minimal-runtime> <runtime-lock.json> <guest-directory> <new-evidence-directory> --model-disk <admitted-regular-file-model.img>
```

The base service-manager stage is hash-verified before extension. The model disk
is not copied into the initramfs. The existing 512MiB/one-vCPU TCG, 110-second,
2MiB-output and child-cleanup limits still apply. The full OS suite passes 122
tests, including missing/symlink/FIFO/bad-size/bad-header asset rejection and
serial-contract rejection of false inference/readiness, root execution, wrong
asset size, writable mount claims or reversed startup ordering. Those error tests
are fixtures, distinct from the actual model-disk/systemd trial.

No full Nix/COSMIC image, persistent conversation, native model inference or
production readiness is established. Prototype licensing and Hyperon dependency
notice gates remain unresolved. Legacy defaults, draft PR #22 and pending metadata
approval hold remain unchanged.
