# Omega MeTTa Package Manager

A small, readable **prototype**, not a finished Linux distribution package manager.
It gives Omega an explicit desired/observed package-state boundary. Python 3.10+
standard library only; Linux is the primary target.

## What works now

- Strict declarative MeTTa-compatible data atoms for desired package state.
- Separate persistent simulation and Nix user-profile backends.
- Actual-state observation, deterministic diff and checksum-tagged JSON plans.
- Explicit apply confirmation, stale-plan detection, per-profile application lock,
  preflight checks and post-apply verification.
- Export of observed state as MeTTa data atoms for Omega to ingest.
- Fully offline simulation, with no external runtime dependencies.
- Nix adapter that passes `--offline` on every call and accepts only exact store
  paths. No package downloads, privileged commands or daemon changes.

**Verified here:** 30 passing unit/fixture/CLI tests with Python 3.12.14;
1 live Hyperon test skipped because Hyperon is absent.
**Not verified here:** live Nix operation or compatibility with a real MeTTa runtime.
Neither Nix nor Hyperon was installed in the development environment. Nix command
fixtures verify our adapter contract, not the real executable's behavior.

## Try it now, without installing anything

From this directory:

```sh
python -m omega_pm --state-dir .demo-state plan examples/workstation.metta --output plan.json
cat plan.json
python -m omega_pm --state-dir .demo-state apply plan.json --yes
python -m omega_pm --state-dir .demo-state observe --metta
python -m omega_pm --state-dir .demo-state check examples/workstation.metta
```

The default backend is deliberately **simulation**. The example paths are fake,
clearly labeled placeholders. This demo does not install any real software.
Running `plan` again after applying it produces an empty operations list. To try
removal, plan and apply `examples/minimal.metta` using the same state directory.

`check` exits 0 for an exact match, 2 for drift, and 1 for an error. Other commands
exit 0 on success and 1 on an operational error. Global flags precede subcommands.
`plan --output` writes a file and also prints the plan; otherwise stdout is enough.

Optional installation into an existing environment:

```sh
python -m pip install --no-build-isolation --no-deps .
omega-pm --help
```

This optional packaging route needs an already installed compatible setuptools
(>=68). Running from the unpacked directory requires no pip or network.

## Configuration contract

```metta
(omega-config 1)
; Use an actual output path from your own Nix store:
(package hello "/nix/store/00000000000000000000000000000000-demo-hello")
```

The first atom is the version marker. Remaining atoms are `(package name "path")`.
Names are lowercase ASCII symbols, start with a letter, and may contain digits
and hyphens (maximum 64 characters). Store paths must be exact top-level Nix store
entries. Duplicate names, unknown atoms, nested expressions and executable forms
are rejected. An empty configuration means no packages in Omega's managed profile.
Package ordering has no semantic effect. Comments begin with `;`.

This is **not a MeTTa evaluator**. It consumes a deliberately constrained data-only
subset of MeTTa syntax. It does not support MeTTa rules, reductions, grounded atoms,
imports or queries. JSON-compatible string escapes are accepted. There is no claim
of full Hyperon parser equivalence. The optional Python bridge below can query a live Hyperon
space and produce the same validated `dict[name, store_path]` without changing the
planner or backend contract. Its live compatibility remains unverified here.

Likewise, observed output is data, not a bidirectional evaluator integration:

```metta
(omega-state 1)
(installed hello "/nix/store/00000000000000000000000000000000-demo-hello")
(state-revision "1")
```

Use `observe --metta` whenever Omega needs fresh facts. Replace previous
`installed` facts with this snapshot; do not keep appending them or removed
packages will appear present. `state-revision` is a backend-specific opaque token,
not a timestamp or shared sequence across machines. Desired and actual snapshots
use different predicates to avoid conflating intent and observation.

## Real Nix use (adapter, needs live validation)

Target: Nix **2.24+** with the named-elements `nix profile list --json` format and
`nix profile install --name`. Versions vary; test on your Nix installation before
relying on it. The adapter temporarily enables `nix-command flakes` in its command
arguments, not in system settings.

1. Install/configure Nix separately as an ordinary user. Omega does not install Nix.
2. Acquire the intended outputs and their dependency closures while online. For
   reproducibility, resolve package expressions from a pinned revision and keep
   that source lock/provenance alongside your configuration. This prototype does
   not resolve versions, maintain a registry, or generate a source lock.
3. Substitute real output paths in your `.metta` configuration. A store path pins
   the resolved artifact identity but is not, by itself, its source provenance.
4. Run with an explicit Nix backend and a new dedicated state directory:

```sh
python -m omega_pm --backend nix --state-dir "$HOME/.local/state/omega-nix" \
  plan your-config.metta --output nix-plan.json
cat nix-plan.json
python -m omega_pm --backend nix --state-dir "$HOME/.local/state/omega-nix" \
  apply nix-plan.json --yes
python -m omega_pm --backend nix --state-dir "$HOME/.local/state/omega-nix" observe
```

The profile is `$HOME/.local/state/omega-nix/profile`. If desired, explicitly put
that profile's `bin` directory on your shell PATH. The program does not edit your
shell configuration. Never point other tools at Omega's private profile.
The program prefixes profile element names with `omega-` and rejects foreign,
inactive, multi-output or unsupported manifest elements rather than guessing.

This manages a **user profile only**. It does not change NixOS system generations,
services, kernel, bootloader, system libraries or non-Nix packages. The actual state
is what is installed in that dedicated profile, not an inventory of the whole OS
or every object in `/nix/store`.

### Offline transfer

After acquisition, export/import complete closures with Nix's own tools (for
example, `nix copy --to file:///path/to/cache /nix/store/<real-output>` and
`nix copy --from file:///path/to/cache /nix/store/<real-output>`). Keep Nix's normal
signature/trust checks enabled; configure trusted transfer sources yourself rather
than disabling verification. The destination must have compatible platform outputs.
For the first version, also retain any Nix tools/environment required for profile
operations. Test the exact operation disconnected before declaring an image ready.

No acquisition commands are run by this prototype. Every adapter call passes
`--offline`; missing closures cause failure rather than a deliberate network fetch.
Preflight runs `nix path-info --recursive` for every desired output before removal.
This checks availability, not integrity or software safety. Nix store verification
and package audit are outside this prototype. Offline mode is not a network sandbox
for an independently configured Nix daemon or unrelated host processes.

## Safety and recovery

- Only `apply --yes` changes package state; the default demo cannot change Nix.
- Nix apply refuses to run as root, requires a user-owned state directory, and uses
  fixed argv arrays without a shell. No sudo and no automatic fetching.
- Treat the state directory, config and plan as trusted user-controlled files.
  A SHA-256 plan checksum catches accidental changes; it is **not a signature** or
  protection from an attacker able to rewrite the plan and recalculate its checksum.
- Plans bind the backend/profile identity, observed generation, full desired state
  and exact operations. Changed state invalidates a saved plan.
- The application lock serializes Omega apply commands, not arbitrary Nix clients.
  Do not mutate the profile outside Omega while reconciliation is running.
- Apply is **not atomic across all operations**. Each Nix command may create a new
  profile generation. Replacement removes the old element before installing its
  successor; if install fails, the old element may remain absent. Binary collisions,
  unavailable dependencies, store failures or interruption can stop an apply.
- Preflight and final observation limit mistakes; they do not implement a transaction.
  On failure, inspect `observe`, fix the cause, then generate and review a fresh plan.
  Nix's native profile history/rollback can help recover a previous generation;
  Omega does not auto-rollback or delete generations. Never delete an old profile
  generation you may need. There is no garbage collection in this tool.
- Applying a no-op plan is harmless. Replaying a plan that changed state is rejected.
- The default state directory is `$XDG_STATE_HOME/omega-pm` or
  `$HOME/.local/state/omega-pm`. Simulation and Nix have separate files and locks.

## Architecture

```
MeTTa data → parser/validator → desired mapping
                                  ↓
backend.observe() → snapshot → deterministic planner → reviewed JSON plan
                                                       ↓
                       lock → freshness/preflight → backend operations
                                                       ↓
                                  observed postcondition → state atoms/JSON
```

- `omega_pm/core.py`: declarations, validation, stable diffs, plans and reconciliation.
- `omega_pm/backends.py`: persistence, locks, simulation and Nix command adapter.
- `omega_pm/__main__.py`: CLI boundary and machine-readable output.
- `tests/test_pm.py`: parser, reconciliation, safety and adapter contract tests.

A Guix backend can implement `identity`, `observe`, `preflight`, `install` and
`remove`. Generalizing the path validator is also necessary because the current
contract intentionally permits Nix store paths only. A full MeTTa runtime can be
added as a separate frontend. Keep reasoning separate from effectful application:
Omega can propose a new desired mapping, but reviewed plans remain the mutation
boundary.

## Tests and next steps

```sh
python -m unittest discover -s tests -v
python -m compileall -q omega_pm tests
```

Coverage includes strict parsing, invalid paths, duplicate declarations, deterministic
ordering, stale/replayed/tampered plans, wrong target, preflight-before-removal,
partial failures, postcondition checking, idempotence, drift exit codes, state atoms,
Nix JSON variants and command arguments. No tests install a package.

Before production use: live Nix matrix tests, real Hyperon ingestion/query tests,
crash-recovery journaling, atomic profile convergence, closure availability/integrity
verification, signed provenance, stronger local-file hardening, multi-output policy,
package collision policy and a privilege-separated whole-system integration.


## 0.2 milestone: optional native MeTTa/Omega bridge

`omega_pm.metta` adds a Python embedding boundary for an Omega host that already
uses Hyperon. No runtime is bundled, fetched or installed automatically. The CLI
still accepts data-only configuration files; it does not execute `.metta` files.

```sh
python -m omega_pm doctor
python -m unittest discover -s tests -v
```

`doctor` reports import/executable availability, not version compatibility or a
successful integration test. The test suite contains an actual Hyperon test; it
is visibly **skipped** when Hyperon is missing. No live Nix integration was run.

Example for an environment that already has Hyperon installed:

```python
from pathlib import Path
from hyperon import MeTTa
from omega_pm.backends import SimulationBackend, atomic_json
from omega_pm.metta import OmegaAwareness, plan_from_metta

backend = SimulationBackend(Path('.demo-state'))
intent = MeTTa()
# In Omega, use its existing intent space instead. This example path is fake.
for atom in intent.parse_all('''
(omega-desired 1)
(package hello "/nix/store/00000000000000000000000000000000-demo-hello")
'''):
    intent.space().add_atom(atom)

plan = plan_from_metta(backend, intent)
atomic_json(Path('plan.json'), plan)  # Review, then use CLI apply --yes.

awareness = OmegaAwareness(backend)
observed = awareness.refresh()
print(observed.runtime.run(
    '!(match &self (installed $name $path) (installed $name $path))'))
# Refresh after apply or before making a new decision:
observed = awareness.refresh()
```

The bridge runs only two fixed `match` queries on the supplied intent runtime.
An explicit `(omega-desired 1)` marker is required before even an empty desired
set is accepted, avoiding accidental remove-all from the wrong/empty space.
Output must pass the existing strict package parser. Rules in the host may
compute intent, but the host must materialize resulting `package` atoms before
planning. This milestone does not interpret arbitrary rules as package intent,
register mutation-capable grounded operations, or add a daemon.

Observed facts go into a **new dedicated MeTTa runtime on every refresh**, rather
than accumulating stale `installed` facts in Omega's reasoning space. Use
`awareness.current.runtime` or the returned observation; old references remain
historical snapshots. A failed refresh retains the last complete observation.
The observation includes its backend identity and revision in Python. Refresh
is explicit, not a subscription; callers must check errors and freshness.

The bridge never applies plans. Existing confirmation, stale-plan detection and
profile locking remain in the CLI apply path. The in-process Hyperon runtime is
not an OS sandbox; an embedding host is responsible for its own extensions,
network access and trusted code. This package itself adds no networking.

**Verification boundary:** bridge behavior is covered by contract doubles plus
an opt-in live test. Until that live test passes with a specified Hyperon version,
this is an implemented but unverified runtime adapter, not a claim that Omega
or a particular MeTTa distribution has been integrated successfully. The next
acceptance step is to run the included live test in the actual Omega environment,
then test a dedicated Nix >= 2.24 profile using real pre-existing store paths.
