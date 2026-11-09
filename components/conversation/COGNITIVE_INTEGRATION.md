# Qualified NAL-1 conversation integration

The final local test executed **actual MeTTa-NARS inference, Omega provider
dispatch through PeTTa, and local Granite inference** in one two-turn session.
The final attempt passed in 51.860 seconds. It returned:

1. “A robin is an animal.”
2. “You mentioned a robin, which belongs to the kinds of bird and animal.”

The input was “A robin is a bird. A bird is an animal. What follows?” followed
by “What creature did I mention, and what two kinds does it belong to?”

See [final native summary](COGNITIVE_NATIVE_003_SUMMARY.json). This establishes
the bounded path below, not general semantic correctness or autonomous reasoning.

## Actual path

1. The existing JSON-lines endpoint admits `{"text":"...","context":[]}`.
2. A deliberately narrow grammar recognizes exactly two leading affirmative
   `X is a Y.` sentences, optionally followed by one question. They must form a
   distinct-symbol inheritance chain. Unsupported or ambiguous text does not
   trigger NARS; it continues through ordinary conversation.
3. The controller attaches exact text-hash/span provenance. Its explicit premise
   policy is frequency 1 and confidence 0.9, not measured truth or corroboration.
4. A fresh bounded Hyperon 0.2.10 process executes the original pinned MeTTa-NARS
   truth functions and NAL-1 rules. A separate Fraction checker validates the
   actual deduction and exemplification rows. No reference result is a fallback.
5. A compact uncertain-belief observation enters Omega's actual LLMRequest system
   message. The complete original user message remains in its normal history.
   Native prompt hashes verify the observation reached Granite's input.
6. Successful history commit also commits the cognitive observation to the
   session-local ledger. The second turn's native prompt hash verifies both the
   original conversation history and the retained observation. Failed turns
   leave committed history and the cognitive ledger unchanged.

The response schema remains exactly `text`, `context_ids`, `executed_actions`.
External context is still empty, `context_ids` stays empty for this path, and
executed actions remain zero. Internal derived observations do not impersonate
ECAN-selected records. Model prose remains unverified output.

## Qualification and preservation

The conversation transfer bundle and all 51 handoff files were checked against
their recorded hashes. PeTTa, Omega, SWI-Prolog, and llama.cpp were rebuilt on
this executor; the producer's binary paths and identities were not reused.
The source verification matched 208 PeTTa and 330 Omega files. The 4,230,976,352
byte Granite GGUF matched SHA-256
`5a38b08c441ae1adbafb1d2b8a7167e0d48734d83af68b268cefea1eec553dcd`.

The native NARS parent-lifetime successor passed all six standalone cases.
Four child-lifetime tests include a real harmless child killed automatically
after its calling parent dies. The final combined run then passed all ten checks:
response schema, two real model calls, actual NARS rows, premise provenance,
snapshot binding, NARS inclusion in the native prompt, session history,
follow-up prompt binding, exact-term recall, and sentence completion.
Thirty-three conversation unit/lifecycle tests passed, including both actual
Prolog bounded-reader tests and rollback of staged cognitive memory.

The first combined attempt passed data-flow checks but exposed a truncated
answer and unsupported follow-up classifications. Its original outputs and a
separate failed quality audit are preserved. The successor retained committed
observations and constrained relationship replies; it passed with complete
answers. A final run requalified that behavior after adding NARS parent-death
binding. Earlier attempts and profiles were not overwritten or relabeled.

The native probe is `tests/probe_nars_native.py`; it is never run by ordinary
unit-test discovery. Raw diagnostics, complete profiles, source/build provenance,
and manifests remain in the private handoff. Repository summaries exclude the
private machine file inventories. Rebuild and prepare a new profile on another
executor; do not copy the observed machine paths into an old admission.

## Enabling a locally qualified profile

`qualify_fresh.py` now accepts `--nars-manifest`, `--nars-admission`, and
`--nars-evidence-root` together. It verifies and includes that NARS closure in
the fresh profile. `fresh_server.py` creates one bounded reasoner per session
when this trusted profile setting exists. Requests cannot supply runtime paths,
source code, executables, manifests, or policy settings.

Existing limits remain: four exchanges, session-local memory, 4,000-character
user messages, 512 input tokens, and 64 output tokens. Cognitive observations
consume the same prompt budget; oversized prompts fail instead of silently
dropping history. The native test only demonstrates the two-turn case above.

Not established: arbitrary language-to-logic extraction, general factual
verification, full NARS memory/control, MetaMo ranking in this turn loop, NACE or
AIRIS conversational learning, ECAN in the fresh profile, durable MORK memory,
graphical/guest integration, or a full autonomous Omega architecture.

## Expanded controlled language

`assertions.py` accepts two affirmative inheritance clauses joined by punctuation
or “and”, optionally reversed, with bounded labels of up to three words.
“All robins are birds. All birds are animals” and “Every mammal is an animal.
A red fox is a mammal” now reach real native inference. Exact source spans and
original assertion IDs survive reordering. Hypotheticals are labelled as such.
Hedges, negation, conditionals, quotes, identifier collisions, extra assertions,
and unmatched chains decline cognitive inference. No stemming or synonym
resolution is inferred. This finite grammar is not general language understanding.

Six expanded forms passed standalone native NARS in 1.909842 seconds. The new
`tests/probe_language_native.py` passed 14 checks over two actual model calls in
59.615610 seconds, including both NARS receipts, exact snapshot and prompt hashes,
and committed history. Replies were “All robins are animals.” and “A red fox is
an animal.” See `LANGUAGE_NATIVE_001_SUMMARY.json`. Conversation suite: 39 tests,
including the two native SWI request-reader tests. These examples do not prove
reliable grounding of arbitrary model responses.

The callable cognitive observer still receives `(text, history)`. Durable v2
integration is pending the conversation owner's verified API; history length
must not silently become a durable revision identifier after truncation/reload.
