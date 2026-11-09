"""Optional Hyperon boundary. Importing this module never requires Hyperon.

Only fixed queries execute. Config files are not evaluated and this bridge has no
apply operation. The embedding Omega process owns its MeTTa runtime and rules.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import shutil

from .core import Backend, Error, Snapshot, make_plan, parse_config, state_atoms


DESIRED_MARKER = '!(match &self (omega-desired 1) True)'
DESIRED_QUERY = '!(match &self (package $name $path) (package $name $path))'


def capabilities() -> dict:
    """Availability is not compatibility or a successful live integration test."""
    return {
        'simulation': {'available': True},
        'hyperon': {'available': importlib.util.find_spec('hyperon') is not None,
                    'live_compatibility_verified': False},
        'nix': {'available': shutil.which('nix') is not None,
                'live_compatibility_verified': False},
    }


def new_runtime():
    try:
        from hyperon import MeTTa
    except ImportError as exc:
        raise Error('Hyperon is unavailable. Use an environment with the hyperon Python package; '
                    'omega-pm will not download or install it automatically') from exc
    return MeTTa()


def _results(runtime, query: str) -> list:
    try:
        groups = runtime.run(query)
    except Exception as exc:
        raise Error(f'MeTTa query failed: {exc}') from exc
    if not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], list):
        raise Error('Unsupported Hyperon result shape; expected one query result list')
    return groups[0]


def desired_from_metta(runtime) -> dict[str, str]:
    """Read explicit intent from an existing runtime, never infer it from absence.

    The caller's runtime must contain exactly one (omega-desired 1) marker. Query
    output is passed through the same strict parser as file input. Duplicate or
    conflicting declarations fail closed, including identical duplicates.
    """
    marker = _results(runtime, DESIRED_MARKER)
    if len(marker) != 1 or str(marker[0]) != 'True':
        raise Error('MeTTa space must contain exactly one (omega-desired 1) marker')
    atoms = _results(runtime, DESIRED_QUERY)
    return parse_config('(omega-config 1)\n' + '\n'.join(str(atom) for atom in atoms))


def plan_from_metta(backend: Backend, runtime) -> dict:
    """Return a normal reviewable plan; do not install or remove anything."""
    return make_plan(backend, desired_from_metta(runtime))


@dataclass(frozen=True)
class Observation:
    backend: str
    snapshot: Snapshot
    runtime: object


class OmegaAwareness:
    """Publish each complete observation into a fresh, dedicated MeTTa space.

    Refresh returns a replacement, not a set of appended facts. Consumers must
    use the returned runtime (or current.runtime), not hold on to an old snapshot.
    Existing Omega spaces/rules are untouched. Failed refresh keeps current intact.
    """
    def __init__(self, backend: Backend, runtime_factory=None):
        self.backend = backend
        self.runtime_factory = runtime_factory or new_runtime
        self.current: Observation | None = None

    def refresh(self) -> Observation:
        snapshot = self.backend.observe()
        source = state_atoms(snapshot)
        try:
            runtime = self.runtime_factory()
            atoms = list(runtime.parse_all(source))
            space = runtime.space()
            for atom in atoms:
                space.add_atom(atom)
        except Error:
            raise
        except Exception as exc:
            raise Error(f'Could not publish MeTTa observation: {exc}') from exc
        observation = Observation(self.backend.identity, snapshot, runtime)
        self.current = observation
        return observation
