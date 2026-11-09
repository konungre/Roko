# Future strict sandbox qualification requirements

Current executor: fresh Nix build with sandbox=true and sandbox-fallback=false
reports required kernel namespaces unsupported. This attempt is stopped. Do not
weaken host settings, add privileges or disable isolation to convert it into a pass.
The earlier unsandboxed rescue and successful option evaluation remain separate.

Use a disposable executor/VM whose managed policy already supports the Linux
user/mount/PID namespace operations required by its reviewed Nix configuration.
No host disks or production profiles should be attached. Record kernel/Nix
versions, capabilities, store layout, exact options and source/toolchain closure.
Use the pinned candidate NAR hash and reviewed source hashes; verify source and
binary-cache provenance/trust separately. No insecure signature bypass is allowed.
Evaluation must keep import-from-derivation disabled unless separately reviewed.

Required evidence, in order:
1. Fresh sandboxed build with fallback=false. A declared Nix-store toolchain must
   run; an undeclared host canary must be inaccessible. Capture namespace/mount
   evidence and native result, rather than infer isolation from option acceptance.
2. Ordinary non-fetch builders must not obtain undeclared network/host inputs.
   Acquisition and fixed-output dependency trust are separate qualification paths.
3. Realize the pinned rescue closure, inventory dependencies and build logs, force
   rebuild, and compare NAR/output hashes. Repeat in a second clean environment
   with the same logical store prefix; workspace-prefix differences can alter
   derivation/output paths and are not evidence of nondeterminism by themselves.
4. Resolve and realize the complete system generation, preserving old roots and
   signatures. Boot it on disposable virtual storage, collect non-root/health
   receipts and exercise failed trials, persistent-state compatibility and recovery.
5. Add COSMIC, bubble and guest-native Omega/model closure only when its exact
   ABI, source/model/profile hashes and resource limits are available. Test actual
   conversation replay/cancellation across restart/reboot before a readiness claim.

None of these build/boot/isolation gates is satisfied by system-eval.nix. The
system module evaluator does not force system.build.toplevel or realize packages.
Current legacy package-source licensing and model/desktop guest gaps remain open.
