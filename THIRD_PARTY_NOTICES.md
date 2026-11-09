# Third-party attribution and license status

This source checkpoint integrates with, references, or adapts interfaces from:

- [PeTTa](https://github.com/trueagi-io/PeTTa), including pinned release source
  `7037f4c2ad378c52fc328004fe216d5118b674f0` for current symbolic gates.
- [Omega](https://github.com/trueagi-io/Omega), Apache-2.0. Original LICENSE and
  NOTICE are retained under `omega-baseline/vendor/PeTTa/repos/Omega/`; the
  upstream source tree itself is omitted. Roko controller/provider integrations
  are authored adaptations and are not represented as untouched upstream code.
- [MetaMo](https://github.com/iCog-Labs-Dev/MetaMo), MIT at
  `bf97e50a68aa5059457092dfbe70699b7dd1dbe2`. Original scoring modules are external.
- [MeTTa-NARS](https://github.com/patham9/metta-nars), MIT at
  `945e2f83711b143e3f6e2eb112cc40c4f531c6f2`. The historical PeTTa adapter's
  modules are external. The development `components/nars_hyperon/upstream`
  directory retains exact `nal1.metta`, `truthfunctions.metta`, and the original
  MIT license, copyright Patrick Hammer (2023).
- [Hyperon](https://github.com/trueagi-io/hyperon-experimental), MIT, version
  0.2.10, is an external runtime dependency for the development NAL-1 adapter.
  Its wheel and native libraries are not redistributed in this repository.
- [MORK](https://github.com/trueagi-io/MORK) and
  [mork_ffi](https://github.com/patham9/mork_ffi). No redistribution license was
  found at the inspected source pins. Their source and binaries are excluded.
- [PathMap](https://github.com/Adam-Vandervorst/PathMap), MIT at the accepted
  `5f2118c1d61d782a7590bac8874dcb3c94c1e0fb`; Git gxhash is MIT and Git
  tracking-allocator is MPL-2.0 at the pins documented by the MORK slice.
- COSMIC/System76 components, Linux, BusyBox, glibc, SWI-Prolog/Janus, Python,
  llama.cpp and Granite model infrastructure, referenced by build recipes and
  source/model locks. Their binaries, models and complete sources are not
  distributed by this repository.

Build recipes are not a determination that a future assembled binary/image
fulfills all applicable source-delivery, relinking, notice or license obligations.
Confirmed project-owned/generated artwork is included at the owner's request;
see `docs/ARTWORK_PROVENANCE.json`. No new artwork or project-wide reuse
license has been selected. Third-party artwork with unverified origin is not included.

## NACE derived function slice

`components/nace/source/nace_slice.py` retains seven exact function blocks from
[patham9/NACE](https://github.com/patham9/NACE) commit
`361fddf5f6885a60b6d5e0d179e0394da876df4c`, MIT. Both source module notices
credit Patrick Hammer and Peter Isaev (2024) and are retained in the derived
file. The upstream repository license is `components/nace/LICENSE.upstream`.
The adapter, deterministic rule-group composition and bounded fixture bindings
are authored integration code, not a claim of full upstream execution.

## AIRIS transition-learning wrapper

`components/airis` calls externally pinned [singnet/AIRIS-general](https://github.com/singnet/AIRIS-general),
commit `db19ad4e2cea33e6129c8bf03e85797da8cf7625`, Apache-2.0. Original
LICENSE and NOTICE are retained under `components/airis/upstream/`. Original
`airis.py` and runtime binaries are not included.

## Conversation Hyperon release audit

Hyperon v0.2.10 resolves to `3f76dc460da6961f57f69f6c3e550c59c74ada83`.
Its exact source LICENSE is MIT, copyright SingularityNET Foundation (2021),
retained at `components/nars_hyperon/licenses/hyperon-0.2.10-LICENSE`.
The observed wheel metadata independently declares MIT. No LICENSE/NOTICE files
were embedded in that wheel, which also bundles native libraries. Root NOTICE
and Cargo.lock returned HTTP404 at the inspected release commit. These are
observations, not proof that no component-specific notices or lockfiles exist.
See `components/nars_hyperon/LICENSE_AUDIT.json` for the wheel digest and native
library inventory. Their individual redistribution obligations remain unaudited;
the wheel/native closure remains external. Existing exact MIT MeTTa-NARS source
and license are reused. No universal Apache-2.0 attribution is applied.

## Package-manager prototype status (unresolved)

The pre-existing `omega-baseline/components/omega-pm` implementation matches the
user-supplied omega-metta-pm-0.2.0.zip. No license grant or rights-holder evidence
was identified in the archive. The matching source remains in the baseline and
its read-only planner imports are still active; it must not be described as
removed from the repository or covered by another project's Apache license.
See `distro/state/provenance/repository-prototype-audit.json` for exact hashes,
introduction commit and consumers. The duplicate imported under distro/state was
removed, but that does not resolve baseline/history redistribution rights.
