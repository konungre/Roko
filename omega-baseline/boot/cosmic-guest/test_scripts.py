#!/usr/bin/env python3
"""Cheap, synthetic tests. No staged guest binaries execute and no VM starts."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import hashlib

spec = importlib.util.spec_from_file_location('guest_build', Path(__file__).with_name('build.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class ClosureTests(unittest.TestCase):
    def test_absolute_link_stays_guest_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'usr/lib').mkdir(parents=True)
            (root / 'lib').symlink_to('/usr/lib')
            (root / 'usr/lib/x').write_bytes(b'guest bytes')
            (root / 'usr/lib/x').chmod(0o644)
            lock = {'files': [dict(path='lib', kind='symlink', target='/usr/lib'),
                              dict(path='usr/lib/x', kind='file', mode=0o644, sha256=hashlib.sha256(b'guest bytes').hexdigest())]}
            closure = b.Closure(root, lock)
            closure.add('lib/x')
            self.assertEqual(closure.files['lib/x'][0], b'guest bytes')
            (root / 'usr/lib/x').write_bytes(b'tamper')
            with self.assertRaisesRegex(ValueError, 'changed'):
                closure.add('lib/x')
            with self.assertRaisesRegex(ValueError, 'escapes'):
                closure.resolve('../../etc/passwd')
    def test_unlocked_link_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'evil').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'Unpinned'):
                b.Closure(root, {'files': []}).add('evil')
    def test_cycle_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'loop').symlink_to('loop')
            lock = {'files': [dict(path='loop', kind='symlink', target='loop')]}
            with self.assertRaisesRegex(ValueError, 'loop'):
                b.Closure(root, lock).resolve('loop')
    def test_guest_init_refuses_host(self):
        import subprocess
        result = subprocess.run(['sh', str(Path(__file__).with_name('init.sh'))])
        self.assertEqual(result.returncode, 90)

class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('guest_run', Path(__file__).with_name('run.py'))
        cls.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.runner)

    def test_preserve_complete_attempt_twice(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            current, attempts = root / 'latest', root / 'attempts'
            current.mkdir()
            contents = {'serial.txt': b'failed boot', 'qmp.json': b'[]',
                        'frame-0.ppm': b'pixels', 'qemu-stderr.txt': b'error',
                        'validation.json': b'{"passed":false}', 'extra/raw': b'other'}
            for name, data in contents.items():
                path = current / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            first = self.runner.preserve_previous(current, attempts)
            self.assertEqual(list(current.iterdir()), [])
            for name, data in contents.items():
                self.assertEqual((first / name).read_bytes(), data)
            (current / 'serial.txt').write_bytes(b'second attempt')
            second = self.runner.preserve_previous(current, attempts)
            self.assertNotEqual(first, second)
            self.assertEqual((second / 'serial.txt').read_bytes(), b'second attempt')
            self.assertEqual((first / 'serial.txt').read_bytes(), b'failed boot')
            self.assertIsNone(self.runner.preserve_previous(current, attempts))

    def test_frame_markers_are_exact(self):
        self.assertTrue(self.runner.has_frame('ROKO_WAYLAND_FRAME count=3 state=1 time=120\r\n', 1))
        for text in ['prefix ROKO_WAYLAND_FRAME count=1 state=0 time=0',
                     'ROKO_WAYLAND_FRAME count=1 state=01 time=0',
                     'ROKO_WAYLAND_FRAME count=0 state=0 time=0',
                     'ROKO_WAYLAND_FRAME count=1 state=0 time=0 suffix',
                     'ROKO_WAYLAND_FRAME count=1 state=0 time=',
                     'ROKO_WAYLAND_FRAME count=1 state=1 time=0']:
            self.assertFalse(self.runner.has_frame(text, 0), text)

class EGLValidationTests(unittest.TestCase):
    def test_pass_and_fail_closed(self):
        spec = importlib.util.spec_from_file_location('egl_test', Path(__file__).with_name('egl_probe.py'))
        egl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(egl)
        log = '\n'.join(['ROKO_EGL_BUILD test', 'ROKO_EGL_SOFTWARE_DEVICE index=0',
            'ROKO_EGL_RENDERER llvmpipe (LLVM 19.1.7, 128 bits)',
            'ROKO_EGL_PIXELS_PASSED pixels=64 rgba=17,34,51,255',
            'ROKO_EGL_CLEANUP_DONE', 'ROKO_EGL_EXIT 0', 'ROKO_EGL_POWER_OFF', 'reboot: Power down'])
        self.assertTrue(egl.passed(log, 'test', 0))
        self.assertFalse(egl.passed(log, 'test', 0, True))
        self.assertFalse(egl.passed(log, 'test', 1))
        self.assertFalse(egl.passed(log, 'different', 0))
        self.assertFalse(egl.passed(log.replace('pixels=64', 'pixels=63'), 'test', 0))
        self.assertFalse(egl.passed(log.replace('llvmpipe', 'hardware'), 'test', 0))
        self.assertFalse(egl.passed(log + '\nROKO_EGL_GUEST_FAILED watchdog', 'test', 0))

if __name__ == '__main__':
    unittest.main()
