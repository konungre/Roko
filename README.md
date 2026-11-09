# Roko

Roko is an experimental local AI desktop and operating-system integration project.
This repository publishes a substantial authored source checkpoint: task/state adapters, bounded symbolic bridges, selected COSMIC/Wayland and OS boot/build recipes, isolation helpers, and tests. Some separately developed showcase/avatar, controller and operational integration files remain excluded or pending; the publication manifest is the exact file list.

**This is a source checkpoint, not a production-ready OS or a complete autonomous
AI.** Historical host/guest milestones were qualified separately. They must not be
combined into a claim that every component passed in one image.

## Start here

- [Current status](docs/STATUS.md): what actually ran, what is experimental, and
  which requested AI components remain pending.
- [Repository map](docs/REPOSITORY_MAP.md): source directories and intended scope.
- [Reproduction and tests](docs/REPRODUCING.md): lightweight checks and missing
  external dependencies.
- [Attribution and licensing](THIRD_PARTY_NOTICES.md): upstream projects and
  redistribution exclusions.
- [Publication scope](docs/PUBLICATION_SCOPE.md): what was deliberately omitted.

The historical baseline documentation is preserved under
[omega-baseline](omega-baseline/README.md). Its earlier milestone and native-test
statements describe those historical builds, not a fresh all-components result.

## Safety boundary

The included controller and symbolic integrations keep model results as bounded
data for independent checking. The reported integration gates executed zero
external actions. Advisory inference, tests, and resource checks do not grant
authority to install software, run arbitrary generated commands, or send data.

Do not run VM, disk, installation, privilege, or native-build recipes without
reviewing their paths, prerequisites, resource budgets, and confirmation needs.
Experimental production-hardening sources are not a supported deployment.

## Missing from this repository

No model weights, compiled executables/shared libraries, VM/root/data images,
private state, credentials, runtime captures, or private artifact identities are
included. Upstream MORK/FFI and private ECAN source remain excluded because
redistribution permission has not been established. Other upstream runtimes are
referenced through source pins rather than copied wholesale.

Avatar artwork and backgrounds are also omitted while redistribution rights are
unresolved. The source alone therefore cannot reproduce the identical artwork or
the delivered desktop image. Exact acquisition pins and preserved build recipes
are useful provenance, not a guarantee of a complete reproducible build.
