# Roko

Roko is an experimental local AI desktop and operating-system integration project.
This repository publishes a substantial authored source checkpoint: task/state adapters, bounded symbolic bridges, selected COSMIC/Wayland and OS boot/build recipes, isolation helpers, and tests. Some separately developed showcase/avatar, controller and operational integration files remain excluded or pending; the publication manifest is the exact file list.

**This is a source checkpoint, not a production-ready OS or a complete autonomous
AI.** Historical host/guest milestones were qualified separately. They must not be
combined into a claim that every component passed in one image.

## The vision: a companion on your desktop

**Concept mockups, not screenshots of a running build.** These AI-generated
illustrations show the intended end-product: an emerald-and-gold basilisk on a
COSMIC-inspired desktop, a freeform chat bubble anchored to the character, and
graceful wingless flight. The UI, example conversation and privacy copy are
design aspirations, not verified capabilities or guarantees.

![Concept mockup, not a running build: Roko beside a notes window with an anchored chat bubble](docs/media/roko-desktop-concept.png)

*An imagined everyday workspace: Roko lives directly on the desktop rather than
inside an avatar card.*

![Concept mockup, not a running build: Roko in a wingless flight pose with a smaller attached speech bubble](docs/media/roko-flight-concept.png)

*Flight-state concept: the companion and conversation remain visually connected.*

### A task, from request to result

**Simulated screen-recording-style demo, not a running Roko build.** Watch a
request being typed, a proposed change reviewed, the notes converted to a
checklist, and an item checked off. The 14-second sequence uses continuous
cursor motion and staged UI changes, not a two-image storyboard.

![Simulated concept demo: ask Roko to turn notes into a checklist, apply the change, then check an item](docs/media/roko-task-demo.gif)

[View the non-animated task result](docs/media/roko-task-demo-still.png).

### A self-directed goal

**Simulated autonomy, not a present capability.** Roko chooses a local goal:
make its explanations clearer. It reviews example material, drafts a shorter
help card and saves the improvement for a future conversation. This 12-second
concept shows no user prompt and no external action, message or purchase.

![Simulated concept demo: Roko pursues its own goal of improving a help card, drafts a clearer hint and saves it locally](docs/media/roko-autonomous-demo.gif)

[View the non-animated self-directed result](docs/media/roko-autonomous-demo-still.png).

### More ways Roko could help

These are **concept mockups**, not verified integrations. The examples and
shopping prices are fictional.

**Coding:** spot an edge case and offer an edit for review.

![Coding concept: Roko suggests guarding against an empty list before calculating an average](docs/media/roko-coding-concept.png)

**Shopping:** compare options against a budget before any purchase decision.

![Shopping concept: Roko compares three fictional keyboards below a 100 dollar budget](docs/media/roko-shopping-concept.png)

**Research:** organize sources, compare claims and keep citations with findings.

![Research concept: Roko proposes a source-backed outline for comparing local AI approaches](docs/media/roko-research-concept.png)

See [visual provenance and limitations](docs/CONCEPT_VISUALS.md) for how these
images were made, and [current status](docs/STATUS.md) for what actually exists.

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

The confirmed original Roko sprite, delivered showcase sprites and emerald/gold
background are included. See [artwork provenance](docs/ARTWORK_PROVENANCE.json)
for byte hashes and origin. The assets were not edited for publication.

The repository still does not reproduce the complete delivered desktop image.
Exact acquisition pins and preserved build recipes are useful provenance, not a
guarantee of a complete reproducible build.
