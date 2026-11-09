#!/usr/bin/env python3
"""Pure source/data tests. No kernel/ELF execution, mounts, VM or model launch."""
import gzip
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

source = load('showcase_source', 'source.py')
supervisor = load('showcase_supervisor', 'supervisor.py')

class PureTests(unittest.TestCase):
    def test_dependency_order(self):
        info = {'a': {'depends': ['b']}, 'b': {'depends': ['builtin']}}
        self.assertEqual(source.module_closure(['a', 'b'], info, {'builtin'}, info.__getitem__), ['b', 'a'])

    def test_dependency_cycle(self):
        info = {'a': {'depends': ['b']}, 'b': {'depends': ['a']}}
        with self.assertRaisesRegex(ValueError, 'cycle'):
            source.module_closure(['a'], info, set(), info.__getitem__)

    def test_missing_module(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            source.module_closure(['missing'], {}, set(), lambda _: {})

    def test_module_data(self):
        data = b'\0depends=drm,i2c-algo-bit\0vermagic=release SMP\0firmware=i915/a.bin\0'
        result = source.module_info(data)
        self.assertEqual(result['depends'], ['drm', 'i2c_algo_bit'])
        self.assertEqual(result['firmware'], ['i915/a.bin'])

    def test_unsafe_destinations(self):
        for path in ['/etc/passwd', '../escape', 'a/../b', '', '.', 'a//b']:
            with self.assertRaises(ValueError):
                source.relative(path)

    def test_read_hash_and_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'file'; p.write_bytes(b'data')
            self.assertEqual(source.read(p, source.sha(b'data')), b'data')
            with self.assertRaises(ValueError): source.read(p, '0' * 64)
            q = Path(folder) / 'link'; q.symlink_to(p)
            with self.assertRaises(ValueError): source.read(q)

    def test_independent_archive_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'fixture.gz'
            mode = stat.S_IFREG | 0o444
            p.write_bytes(gzip.compress(source.entry('file', b'data', mode, 1) + source.entry('TRAILER!!!', b'', 0, 2)))
            expected = {'file': {'bytes': 4, 'sha256': source.sha(b'data'), 'mode': mode}}
            self.assertEqual(source.inspect_archive(p, expected), 1)
            with self.assertRaises(ValueError): source.inspect_archive(p, {})

    def test_no_implicit_execution(self):
        with patch.object(supervisor.os, 'getpid', return_value=4000), patch.object(supervisor.subprocess, 'Popen', side_effect=AssertionError('No process')):
            with self.assertRaises(SystemExit) as caught: supervisor.main()
            self.assertEqual(caught.exception.code, 90)

    def test_memory(self):
        self.assertEqual(supervisor.available_kib('MemTotal: 999 kB\nMemAvailable: 123 kB\n'), 123)
        with self.assertRaises(ValueError): supervisor.available_kib('MemTotal: 999 kB')

    def test_pid1_orphan_reaping_preserves_known_status(self):
        known = Mock(pid=7)
        statuses = [SimpleNamespace(si_pid=7), SimpleNamespace(si_pid=8), None]
        with patch.object(supervisor.os, 'waitid', side_effect=statuses), patch.object(supervisor.os, 'waitpid') as wait:
            supervisor.reap_children({'session': known})
        known.poll.assert_called_once_with()
        wait.assert_called_once_with(8, supervisor.os.WNOHANG)

    def test_pid1_no_children(self):
        with patch.object(supervisor.os, 'waitid', side_effect=ChildProcessError):
            supervisor.reap_children({})

    def test_bounded_log(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'log'
            log = supervisor.BoundedLog(path, 10)
            log.write(b'123456'); log.write(b'abcdef'); log.write(b'X' * 40); log.close()
            self.assertEqual(path.read_bytes(), b'X' * 10)

    def test_boot_contract(self):
        script = (HERE / 'init.sh').read_text()
        self.assertIn('loop,ro,noload,nodev,nosuid', script)
        self.assertIn('mount -t iso9660 -o ro,nodev,nosuid,noexec', script)
        self.assertIn('mount -o move /run /newroot/run', script)
        self.assertNotIn('/dev/vda', script)
        self.assertNotIn('roko-granite-model', script)
        self.assertNotIn('data.ext4', script)
        self.assertIn('media-manifest.sha256', script)
        self.assertNotIn('$BB blkid', script)
        self.assertIn('skip=32768 count=7', script)
        self.assertIn('01434430303101', script)
        self.assertIn('skip=32808 count=32', script)
        self.assertIn('[ ! -f "$entry/partition" ] || continue', script)

    def test_no_fixture_lifecycle(self):
        script = (HERE / 'session.sh').read_text() + (HERE / 'supervisor.py').read_text()
        for forbidden in ['roko-session-test', 'roko-session-finish', 'guest-watchdog', 'roko-storage-mount']:
            self.assertNotIn(forbidden, script)
        self.assertIn("['/usr/bin/cosmic-session', 'cosmic-comp', '--no-xwayland']", script)
        self.assertIn("['/usr/bin/roko-companion']", script)
        self.assertNotIn("['/usr/bin/cosmic-greeter']", script)

    def test_wallpaper_schema(self):
        evidence = json.loads((HERE / 'evidence/schema-provenance.json').read_text())['wallpaper']
        text = (HERE / 'background.ron').read_text()
        for key in evidence['fields']:
            self.assertIn(key + ':', text)
        self.assertIn('source: Path("/usr/share/backgrounds/roko/roko-emerald.png")', text)

    def test_real_plan_stays_source_only(self):
        with patch('subprocess.Popen', side_effect=AssertionError('No native subprocess permitted')):
            plan = source.plan()
        self.assertTrue(plan['source_only'])
        self.assertFalse(plan['native_executed'])
        self.assertFalse(plan['boot_tested'])
        self.assertEqual(plan['firmware_names_unavailable'], [])
        self.assertLess(plan['early_modules'].index('crc32c_generic'), plan['early_modules'].index('ext4'))
        self.assertLess(plan['early_modules'].index('crc32c_generic'), plan['early_modules'].index('jbd2'))
        for driver in ['ohci_pci', 'uhci_hcd']:
            self.assertLess(plan['early_modules'].index('ehci_pci'), plan['early_modules'].index(driver))
        self.assertTrue(all(plan['system_runtime_readback_matches'].values()))
        self.assertLess(plan['source_payload_bytes'], source.CAP)
        self.assertEqual(plan['media_manifest']['model']['path'], '/roko/model/granite-4.0-h-tiny-Q4_K_M.gguf')
        self.assertNotIn('payload/root/usr/share/applications/roko.desktop', plan['entries'])
        self.assertIn('payload/root/usr/share/doc/firmware-intel-graphics/copyright', plan['entries'])
        self.assertIn('payload/root/opt/roko/desktop/live-request/cli.py', plan['entries'])
        self.assertIn('payload/run/roko-guest-cognition/model/adapters/media_transport.py', plan['entries'])
        self.assertEqual(plan['input_locks']['basilisk'], '77d8916d3752751431b63523b4d9785bccc8a945ec3cdc746818635b486fd5d3')
        self.assertIn('payload/root/usr/share/roko/showcase/ui_layout.py', plan['entries'])
        self.assertIn('payload/root/usr/share/roko/showcase/animation.py', plan['entries'])
        self.assertTrue(plan['entries']['payload/root/usr/share/roko/showcase/companion.py']['source'].startswith('roko-showcase-stage-v4/'))

    def test_bad_review_cannot_assemble(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'must-not-exist'
            with self.assertRaises(ValueError): source.assemble({}, '0' * 64, out)
            self.assertFalse(out.exists())

if __name__ == '__main__':
    unittest.main(verbosity=2)
