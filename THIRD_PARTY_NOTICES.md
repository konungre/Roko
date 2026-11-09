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
  `945e2f83711b143e3f6e2eb112cc40c4f531c6f2`. Original NAL-1 modules are external.
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
Artwork rights and newly authored project-wide distribution terms remain open.

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
