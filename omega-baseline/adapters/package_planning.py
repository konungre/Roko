"""Read-only, snapshot-based bridge to the preserved omega-pm planner.

No Nix backend is instantiated, no simulation is applied, and no package state
is observed implicitly. The caller supplies a labelled historical snapshot.
Plans use a snapshot-only identity and are not executable Nix profile plans.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'components/omega-pm'))
from omega_pm.core import Error, Snapshot, make_plan, parse_config, validate_packages

MAX_INPUT_BYTES = 1024 * 1024


def _json_object(source: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Error(f'Duplicate snapshot key: {key}')
            result[key] = value
        return result
    if not isinstance(source, str) or len(source.encode()) > MAX_INPUT_BYTES:
        raise Error('Snapshot must be bounded JSON text')
    try:
        value = json.loads(source, object_pairs_hook=unique)
    except ValueError as exc:
        raise Error('Invalid snapshot JSON') from exc
    if not isinstance(value, dict):
        raise Error('Snapshot must be an object')
    return value


class SnapshotOnly:
    """Implements only the observation required by make_plan, no apply methods."""
    def __init__(self, source: str):
        value = _json_object(source)
        if set(value) != {'packages', 'revision', 'source'}:
            raise Error('Snapshot requires packages, revision and source')
        for key in ('revision', 'source'):
            if not isinstance(value[key], str) or not value[key] or len(value[key]) > 4096:
                raise Error(f'Snapshot {key} must be nonempty bounded text')
        self.identity = 'snapshot-only:' + value['source']
        self.snapshot = Snapshot(validate_packages(value['packages']), value['revision'])

    def observe(self):
        return Snapshot(dict(self.snapshot.packages), self.snapshot.revision)


def plan_source(desired_source: str, snapshot_json: str) -> dict:
    if not isinstance(desired_source, str) or len(desired_source.encode()) > MAX_INPUT_BYTES:
        raise Error('Desired configuration must be bounded text')
    plan = make_plan(SnapshotOnly(snapshot_json), parse_config(desired_source))
    return {
        'schema': 1,
        'mode': 'read-only-snapshot-planning',
        'authorizes_actions': False,
        'package_changes_executed': 0,
        'live_nix_observed': False,
        'limitations': 'Caller-supplied snapshot only; no closure, profile, version, or installation verification.',
        'plan': plan,
    }


def plan_single(name: str, path: str, snapshot_json: str) -> str:
    """Janus-safe scalar interface for one materialized MeTTa desired-package fact."""
    validate_packages({name: path})
    source = f'(omega-config 1)\n(package {name} {json.dumps(path)})'
    return json.dumps(plan_source(source, snapshot_json), sort_keys=True)


def operation_count(report_json: str) -> int:
    return len(json.loads(report_json)['plan']['operations'])


def planned_path(report_json: str, name: str) -> str:
    return json.loads(report_json)['plan']['desired'][name]


def authorizes_actions(report_json: str) -> bool:
    return json.loads(report_json)['authorizes_actions']


def has_planned_package(report_json: str, name: str, path: str) -> bool:
    return json.loads(report_json)['plan']['desired'].get(name) == path
