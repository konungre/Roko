"""Contract doubles are not proof of live Hyperon compatibility."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from omega_pm.backends import SimulationBackend
from omega_pm.core import Error, Snapshot, state_atoms
from omega_pm.metta import (DESIRED_MARKER, DESIRED_QUERY, OmegaAwareness,
                            desired_from_metta, new_runtime, plan_from_metta)

P = '/nix/store/' + '0' * 32 + '-hello'


class RuntimeDouble:
    def __init__(self, marker=None, packages=None):
        self.marker = ['True'] if marker is None else marker
        self.packages = [] if packages is None else packages
        self.atoms = []
        self.queries = []

    def run(self, query):
        self.queries.append(query)
        if query == DESIRED_MARKER:
            return [self.marker]
        if query == DESIRED_QUERY:
            return [self.packages]
        raise AssertionError('Unexpected executable query')

    def parse_all(self, source):
        return [line for line in source.splitlines() if not line.startswith(';')]

    def space(self):
        return self

    def add_atom(self, atom):
        self.atoms.append(atom)


class BridgeContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = SimulationBackend(Path(self.tmp.name))

    def test_intent_plans_without_applying(self):
        runtime = RuntimeDouble(packages=[f'(package hello "{P}")'])
        plan = plan_from_metta(self.backend, runtime)
        self.assertEqual(plan['desired'], {'hello': P})
        self.assertEqual(self.backend.observe().packages, {})
        self.assertEqual(runtime.queries, [DESIRED_MARKER, DESIRED_QUERY])

    def test_explicit_empty_intent(self):
        self.assertEqual(desired_from_metta(RuntimeDouble()), {})

    def test_missing_ambiguous_or_invalid_marker(self):
        for marker in ([], ['True', 'True'], ['False'], ['(Error x)']):
            with self.subTest(marker=marker), self.assertRaises(Error):
                desired_from_metta(RuntimeDouble(marker=marker))

    def test_invalid_query_output_and_duplicates(self):
        package = f'(package hello "{P}")'
        for atoms in ([package, package], ['(package $x $y)'],
                      ['(Error x)'], ['!(exec "sh")'],
                      ['(package hello "nixpkgs#hello")']):
            with self.subTest(atoms=atoms), self.assertRaises(Error):
                desired_from_metta(RuntimeDouble(packages=atoms))

    def test_malformed_runtime_result(self):
        class Broken(RuntimeDouble):
            def run(self, query):
                return []
        with self.assertRaisesRegex(Error, 'result shape'):
            desired_from_metta(Broken())

    def test_refresh_replaces_removed_facts(self):
        awareness = OmegaAwareness(self.backend, RuntimeDouble)
        self.backend.install('hello', P)
        before = awareness.refresh()
        self.backend.remove('hello')
        after = awareness.refresh()
        self.assertIsNot(before.runtime, after.runtime)
        self.assertTrue(any('(installed hello ' in a for a in before.runtime.atoms))
        self.assertFalse(any('(installed ' in a for a in after.runtime.atoms))
        self.assertIs(awareness.current, after)
        self.assertEqual(after.runtime.queries, [])

    def test_failed_refresh_preserves_last_complete_snapshot(self):
        awareness = OmegaAwareness(self.backend, RuntimeDouble)
        before = awareness.refresh()
        def broken():
            raise RuntimeError('fixture failure')
        awareness.runtime_factory = broken
        with self.assertRaisesRegex(Error, 'fixture failure'):
            awareness.refresh()
        self.assertIs(awareness.current, before)

    def test_revision_is_escaped_data(self):
        revision = '\") !(exec "bad")\n'
        source = state_atoms(Snapshot({}, revision))
        self.assertIn('(state-revision ' + json.dumps(revision) + ')', source)
        self.assertEqual(len(source.splitlines()), 3)


@unittest.skipUnless(importlib.util.find_spec('hyperon'), 'Hyperon not installed; live integration not verified')
class LiveHyperonTests(unittest.TestCase):
    def test_native_intent_query_and_observation_refresh(self):
        runtime = new_runtime()
        for atom in runtime.parse_all(f'(omega-desired 1) (package hello "{P}")'):
            runtime.space().add_atom(atom)
        self.assertEqual(desired_from_metta(runtime), {'hello': P})
        with tempfile.TemporaryDirectory() as root:
            backend = SimulationBackend(Path(root))
            backend.install('hello', P)
            awareness = OmegaAwareness(backend)
            before = awareness.refresh()
            query = '!(match &self (installed $name $path) (installed $name $path))'
            self.assertEqual(len(before.runtime.run(query)[0]), 1)
            backend.remove('hello')
            after = awareness.refresh()
            self.assertEqual(after.runtime.run(query), [[]])


if __name__ == '__main__':
    unittest.main()
