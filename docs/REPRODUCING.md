# Reproduction and lightweight checks

This repository is not a complete runtime closure. No dependency installation,
native compilation, VM boot, privileged action, or model download is automatic.

Python 3.12 was used for the publication's selected authored tests. The CLI expects a local virtual environment; creating one below uses the installed Python and downloads nothing. The virtual environment is not published. From the root:

```sh
python3 -B -m unittest discover -s mork-recovery-v1/tests -v
```

Other staged checks referenced in the validation summary were run locally before
publication, but not every baseline test file is included in the initial public
subset. The exact manifest controls file availability.

The MORK tests exercise validation, fail-closed behavior and authored helper
processes, not the native engine. The audit itself needs separately restored
private source bytes and will not claim native readiness.

Other tests may intentionally require omitted exact source, native libraries,
artwork or artifact manifests. A failure due to those missing inputs must not be
reclassified as a native pass. Public redactions of private artifact bindings
also intentionally prevent those development admissions from being replayed.

## External inputs

Private/development runtime inventories and detailed host file/hash locks are
not published. Source code retains necessary validation interfaces, but real
admission requires a separately reviewed exact dependency closure.

Public source references:

- PeTTa: https://github.com/trueagi-io/PeTTa at
  7037f4c2ad378c52fc328004fe216d5118b674f0.
- MeTTa-NARS: https://github.com/patham9/metta-nars at
  945e2f83711b143e3f6e2eb112cc40c4f531c6f2 (MIT).
- MetaMo: https://github.com/iCog-Labs-Dev/MetaMo at
  bf97e50a68aa5059457092dfbe70699b7dd1dbe2 (MIT).
- MORK: https://github.com/trueagi-io/MORK at
  1c44f70f34db6305c3ba7bdb2e1434db3387778b.
- mork_ffi: https://github.com/patham9/mork_ffi at
  f6553aa4559142895c5547f56e490d29e29469f1.

MORK/FFI redistribution permission remains unverified; their source and binaries
are excluded. The historical frozen Cargo dependency closure has not been
recovered. Review upstream rights before acquisition or redistribution.

Missing metadata/native-source tests may fail deliberately. Do not weaken hash,
resource, ownership or authorization checks to force a pass. Native process
limits are not a general filesystem/process sandbox.

## Public serial rescue foundation

A dependency-free (apart from Python and the x86-64 GCC toolchain) rescue build
and adversarial archive/ELF checks are described in
[the fresh Linux foundation checkpoint](LINUX_FOUNDATION_FRESH.md). The explicit
`--minimal` build needs none of the omitted historical profile or asset locks.
It has no desktop or model and does not boot a VM automatically.
