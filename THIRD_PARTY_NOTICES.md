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
Confirmed project-owned/generated artwork is included at the owner's request;
see `docs/ARTWORK_PROVENANCE.json`. No new artwork or project-wide reuse
license has been selected. Third-party artwork with unverified origin is not included.
