import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from omega_pm.__main__ import main
from omega_pm.backends import NixBackend, SimulationBackend
from omega_pm.core import Error, apply_plan, digest, make_plan, parse_config, state_atoms, verify_plan

P = '/nix/store/' + '0' * 32 + '-hello'
Q = '/nix/store/' + '1' * 32 + '-editor'
R = '/nix/store/' + '2' * 32 + '-hello-new'


class ParserTests(unittest.TestCase):
    def test_comments_and_order(self):
        self.assertEqual(parse_config(f'; hi\n(omega-config 1)\n(package z "{Q}") (package a "{P}")'), {'a': P, 'z': Q})

    def test_empty(self):
        self.assertEqual(parse_config('(omega-config 1)'), {})

    def test_reject_unsafe_and_unsupported(self):
        bad = ['', '(omega-config 2)', '(omega-config 1) (evil x y)',
               '(omega-config 1) !(exec "sh")', '(omega-config 1) (package a (exec x))',
               '(omega-config 1) (package ../foo "' + P + '")',
               '(omega-config 1) (package a "nixpkgs#hello")',
               '(omega-config 1) (package a "' + P + '/bin/sh")',
               '(omega-config 1) (package a "' + P + '") (package a "' + P + '")',
               '(omega-config 1) (package a "unterminated)', '(omega-config 1))',
               '(omega-config 1) (package a ' + P + ')', '(omega-config 1']
        for source in bad:
            with self.subTest(source=source), self.assertRaises(Error):
                parse_config(source)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = SimulationBackend(Path(self.tmp.name))

    def test_deterministic(self):
        a = make_plan(self.backend, {'z': Q, 'a': P})
        b = make_plan(self.backend, {'a': P, 'z': Q})
        self.assertEqual(a, b)
        self.assertEqual([op['name'] for op in a['operations']], ['a', 'z'])

    def test_apply_idempotence_and_removal(self):
        apply_plan(self.backend, make_plan(self.backend, {'hello': P, 'editor': Q}))
        self.assertEqual(make_plan(self.backend, {'hello': P, 'editor': Q})['operations'], [])
        apply_plan(self.backend, make_plan(self.backend, {'hello': R}))
        self.assertEqual(self.backend.observe().packages, {'hello': R})
        apply_plan(self.backend, make_plan(self.backend, {}))
        self.assertEqual(self.backend.observe().packages, {})

    def test_stale_plan(self):
        plan = make_plan(self.backend, {'hello': P})
        self.backend.install('editor', Q)
        with self.assertRaisesRegex(Error, 'State changed'):
            apply_plan(self.backend, plan)

    def test_replayed_mutating_plan_rejected(self):
        plan = make_plan(self.backend, {'hello': P})
        apply_plan(self.backend, plan)
        with self.assertRaisesRegex(Error, 'State changed'):
            apply_plan(self.backend, plan)

    def test_tamper_and_recomputed_checksum(self):
        plan = make_plan(self.backend, {'hello': P})
        plan['operations'] = []
        with self.assertRaisesRegex(Error, 'checksum'):
            verify_plan(plan, self.backend)
        plan['id'] = digest({k: v for k, v in plan.items() if k != 'id'})
        with self.assertRaisesRegex(Error, 'operations'):
            verify_plan(plan, self.backend)

    def test_wrong_backend(self):
        plan = make_plan(self.backend, {})
        other = SimulationBackend(Path(self.tmp.name) / 'other')
        with self.assertRaisesRegex(Error, 'different backend'):
            apply_plan(other, plan)

    def test_preflight_before_destructive_steps(self):
        self.backend.install('hello', P)
        plan = make_plan(self.backend, {'hello': R})
        with patch.object(self.backend, 'preflight', side_effect=Error('unavailable')):
            with self.assertRaisesRegex(Error, 'unavailable'):
                apply_plan(self.backend, plan)
        self.assertEqual(self.backend.observe().packages, {'hello': P})

    def test_partial_failure_is_reported_and_recoverable(self):
        self.backend.install('hello', P)
        plan = make_plan(self.backend, {'hello': R})
        with patch.object(self.backend, 'install', side_effect=Error('injected')):
            with self.assertRaisesRegex(Error, 'after 1 operation'):
                apply_plan(self.backend, plan)
        self.assertEqual(self.backend.observe().packages, {})
        apply_plan(self.backend, make_plan(self.backend, {'hello': R}))
        self.assertEqual(self.backend.observe().packages, {'hello': R})

    def test_postcheck(self):
        plan = make_plan(self.backend, {'hello': P})
        with patch.object(self.backend, 'install', return_value=None):
            with self.assertRaisesRegex(Error, 'does not match'):
                apply_plan(self.backend, plan)

    def test_metta_state(self):
        self.backend.install('hello', P)
        atoms = state_atoms(self.backend.observe())
        self.assertIn(f'(installed hello "{P}")', atoms)
        self.assertIn('(omega-state 1)', atoms)


class NixAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []
        self.response = {'version': 3, 'elements': {'omega-hello': {'active': True, 'storePaths': [P]}}}
        def runner(command, **kwargs):
            self.calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, json.dumps(self.response), '')
        self.backend = NixBackend(Path(self.tmp.name), runner)

    def profile(self):
        self.backend.profile.touch()

    def test_absent(self):
        self.assertEqual(self.backend.observe().packages, {})
        self.assertEqual(self.calls, [])

    def test_actual_named_elements(self):
        self.profile()
        self.assertEqual(self.backend.observe().packages, {'hello': P})

    def test_foreign_and_multi_output_rejected(self):
        self.profile()
        for elements in [{'foreign': {'storePaths': [P]}}, {'omega-hello': {'storePaths': [P, Q]}},
                         {'omega-hello': {'storePaths': [P], 'active': False}}]:
            self.response['elements'] = elements
            with self.subTest(elements=elements), self.assertRaises(Error):
                self.backend.observe()

    def test_old_json_rejected(self):
        self.profile()
        self.response = [{'storePaths': [P]}]
        with self.assertRaisesRegex(Error, 'Unsupported'):
            self.backend.observe()

    def test_commands_are_offline_without_shell(self):
        self.backend.install('hello', P)
        self.backend.remove('hello')
        for command, kwargs in self.calls:
            self.assertIn('--offline', command)
            self.assertNotIn('shell', kwargs)
            self.assertNotIn('sudo', command)
        self.assertIn('--name', self.calls[0][0])
        self.assertIn('omega-hello', self.calls[0][0])

    def test_root_apply_rejected(self):
        with patch('os.geteuid', return_value=0), self.assertRaisesRegex(Error, 'not root'):
            self.backend.preflight({})

    def test_preflight_checks_entire_closure(self):
        owner = self.backend.root.stat().st_uid
        if owner == 0:
            self.skipTest('Fixture requires ordinary-user-owned temporary directory')
        self.backend.preflight({'hello': P})
        self.assertIn('--recursive', self.calls[0][0])

    def test_nix_failure_is_not_success(self):
        self.backend.runner = lambda command, **kwargs: subprocess.CompletedProcess(command, 1, '', 'not in store')
        with self.assertRaisesRegex(Error, 'not in store'):
            self.backend.install('hello', P)


class CLITests(unittest.TestCase):
    def test_complete_offline_simulation(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(directory)
            config, plan = root / 'config.metta', root / 'plan.json'
            config.write_text(f'(omega-config 1) (package hello "{P}")')
            base = ['--state-dir', str(root / 'state')]
            self.assertEqual(main(base + ['check', str(config)]), 2)
            self.assertEqual(main(base + ['plan', str(config), '--output', str(plan)]), 0)
            self.assertEqual(main(base + ['apply', str(plan)]), 1)
            self.assertEqual(main(base + ['apply', str(plan), '--yes']), 0)
            self.assertEqual(main(base + ['check', str(config)]), 0)
            self.assertEqual(main(base + ['observe', '--metta']), 0)


if __name__ == '__main__':
    unittest.main()
