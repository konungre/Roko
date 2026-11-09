# Native memory vendoring audit

User authorization permits Hyperon source vendoring where useful, subject to
verification of each pinned repository/dependency and retention of its notices.
The ecosystem name is not a license declaration.

| Input | Pinned revision | Local license evidence | Decision |
| --- | --- | --- | --- |
| trueagi-io/MORK | 1c44f70f34db6305c3ba7bdb2e1434db3387778b | No LICENSE/COPYING/NOTICE in the complete tracked tree; no license field in root/kernel Cargo manifests | Do not vendor until a grant covering this revision is verified |
| patham9/mork_ffi | f6553aa4559142895c5547f56e490d29e29469f1 | Prior source inventory found no license declaration; materialized subtree has no LICENSE and Cargo has no license field | Unresolved; do not vendor |
| Adam-Vandervorst/PathMap | 5f2118c1d61d782a7590bac8874dcb3c94c1e0fb | LICENSE: MIT, copyright 2025 Adam Vandervorst | Eligible with full notice; no copy added merely to duplicate the private dependency checkout |
| luketpeterson/gxhash | 55bde471dc2e395dd17eb4e7055f323c0c29c19d | LICENSE: MIT, copyright 2023 Olivier Giniaux | Eligible with full notice; no redundant copy added |
| tobz/tracking-allocator | 8d1e79b025011e5b8d445856eb51ab98ee915b6c | LICENSE: Mozilla Public License Version 2.0 | Requires its actual MPL terms; do not label Apache 2.0 |

The MORK and three dependency entries were independently checked against local
pinned Git objects. License bytes match their tracked versions; hashes and
tracked license paths are in VENDORING_EVIDENCE.json. The mork_ffi entry has
weaker evidence: a materialized build subtree and prior pin inventory, without
an independently verified complete upstream tree. It remains unresolved. Public GitHub tree verification for MORK and mork_ffi was attempted
but the browser fetch returned a restricted-URL failure; no alternate fetch was
attempted in this audit. That failed check does not establish a license or change
the local evidence. Missing declarations remain unresolved rather than a claim
that upstream can never be licensed.

No upstream source was newly redistributed by this audit. Existing authored
adapters and privately built runtimes remain separate. Any future vendoring must
include a pinned source inventory, dependency license audit, complete LICENSE and
NOTICE files where present, attribution, and a build that actually consumes the
vendored source. It must retain the PathMap known-defect qualification boundary.
